"""Y Combinator jobs adapter (public landing-page feed — no auth required).

YC's jobs landing page (https://www.ycombinator.com/jobs) is a React-on-Rails
page that embeds its job data as a JSON blob inside a `data-page` attribute
(`props.jobPostings`). We parse that JSON rather than scraping HTML cards, which
is far more resilient to markup changes.

Scope/limitation: this landing page only exposes ~20 rotating *featured* jobs and
offers no server-side keyword/location filtering or pagination (the `/jobs/role/*`
and `/jobs/location/*` paths are client-side React routes that 404 for non-browser
clients, and `?page=` is ignored). The full searchable index lives on
workatastartup.com, which is login-gated. So this adapter is a small supplementary
YC feed: it fetches the featured set once and filters client-side against the
criteria. robots.txt allows `/jobs`; the endpoint is keyless and unauthenticated.

Remote mapping: there is no remote flag — remote status is inferred from the
`location` text (which contains "Remote (...)" for remote-eligible roles).

Descriptions: the feed carries no full JD (the canonical JD is login-gated), so a
short synthetic description is built from the one-liner, role, type, and skills;
`url` points at the real posting. `fetch_description()` stays the base no-op.
"""

import html as html_lib
import json
import logging
import re
from datetime import UTC, datetime, timedelta

import httpx
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.adapters.base import JobBoardAdapter
from backend.config import settings
from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria

logger = logging.getLogger(__name__)

_JOBS_URL = "https://www.ycombinator.com/jobs"
_BASE_URL = "https://www.ycombinator.com"

_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

_DATA_PAGE_RE = re.compile(r'data-page="([^"]+)"')
# "5 days", "about 1 month", "almost 2 years", "over 3 years", "10 days" ...
_AGE_RE = re.compile(r"(\d+)\s+(day|days|month|months|year|years)")
_UNIT_DAYS = {"day": 1, "days": 1, "month": 30, "months": 30, "year": 365, "years": 365}


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on 5xx server errors and transport failures, not 4xx."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _parse_relative_age(value: str | None) -> str | None:
    """Best-effort: convert a fuzzy relative age ("5 days", "about 1 month") to
    an absolute YYYY-MM-DD. Returns None when it can't be parsed."""
    if not value:
        return None
    match = _AGE_RE.search(value.lower())
    if not match:
        return None
    amount = int(match.group(1))
    days = amount * _UNIT_DAYS[match.group(2)]
    return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")


def _infer_remote(location: str | None) -> RemoteStatus:
    if location and "remote" in location.lower():
        return RemoteStatus.remote
    return RemoteStatus.unspecified


def _matches_query(text: str, query: str) -> bool:
    if not query.strip():
        return True
    terms = query.lower().split()
    haystack = text.lower()
    return all(bool(re.search(r"\b" + re.escape(t) + r"\b", haystack)) for t in terms)


def _location_matches(posting_location: str | None, criteria_location: str) -> bool:
    if not posting_location:
        return False
    return criteria_location.lower() in posting_location.lower()


class YCombinatorAdapter(JobBoardAdapter):
    source = "ycombinator"

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def _fetch(self) -> str:
        async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS) as client:
            resp = await client.get(_JOBS_URL)
            resp.raise_for_status()
            return resp.text

    def _extract_postings(self, page_html: str) -> list[dict]:
        """Pull props.jobPostings out of the embedded data-page JSON blob."""
        match = _DATA_PAGE_RE.search(page_html)
        if not match:
            logger.warning("ycombinator: no data-page blob found in response")
            return []
        try:
            data = json.loads(html_lib.unescape(match.group(1)))
            return data.get("props", {}).get("jobPostings", []) or []
        except (ValueError, AttributeError) as exc:
            logger.warning("ycombinator: failed to parse data-page JSON: %s", exc)
            return []

    def _normalize(self, item: dict) -> JobPosting | None:
        try:
            url = item["url"]
            if url.startswith("/"):
                url = _BASE_URL + url
            location = item.get("location")
            description_parts = [
                item.get("companyOneLiner"),
                item.get("prettyRole"),
                item.get("roleSpecificType"),
                item.get("type"),
                ", ".join(item.get("skills") or []) or None,
            ]
            description = " | ".join(part for part in description_parts if part)
            return JobPosting(
                source=self.source,
                source_job_id=str(item["id"]),
                title=item["title"],
                company=item.get("companyName"),
                location=location,
                remote_status=_infer_remote(location),
                url=url,
                description=description,
                compensation=item.get("salaryRange"),
                posted_date=_parse_relative_age(item.get("createdAt")),
            )
        except (KeyError, TypeError) as exc:
            logger.warning("ycombinator: failed to normalize item %s: %s", item.get("id"), exc)
            return None

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        if not settings.ycombinator_enabled:
            logger.debug("ycombinator: disabled via settings, skipping")
            return []

        try:
            page_html = await self._fetch()
        except Exception as exc:
            cause = exc.last_attempt.exception() if isinstance(exc, RetryError) else exc
            if isinstance(cause, httpx.HTTPStatusError):
                logger.error("ycombinator: HTTP %d", cause.response.status_code)
            else:
                logger.error("ycombinator: fetch failed: %s", cause)
            return []

        postings: list[JobPosting] = []
        for item in self._safe_iter(self._extract_postings(page_html)):
            posting = self._normalize(item)
            if posting is None:
                continue
            haystack = f"{posting.title} {posting.description}"
            if not _matches_query(haystack, criteria.query):
                continue
            if criteria.remote_only and posting.remote_status != RemoteStatus.remote:
                continue
            if (
                criteria.location
                and not criteria.remote_only
                and not _location_matches(posting.location, criteria.location)
            ):
                continue
            postings.append(posting)

        logger.info("ycombinator: query=%r → %d results", criteria.query, len(postings))
        return postings
