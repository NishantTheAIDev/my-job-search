"""Jobicy job board adapter (free public API — remote-only listings).

Remote mapping: every Jobicy listing is remote by definition.
  Location filter is applied client-side against the `jobGeo` field.
  "Worldwide", "Anywhere", or an empty geo matches any criteria location.

Rate limit: single request per search() call; API returns up to 50 results.
"""

import logging
import re
from datetime import datetime

import httpx
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.adapters.base import JobBoardAdapter
from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria

logger = logging.getLogger(__name__)

_BASE_URL = "https://jobicy.com/api/v2/remote-jobs"
_COUNT = 50


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _parse_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _build_compensation(item: dict) -> str | None:
    min_sal = item.get("annualSalaryMin")
    max_sal = item.get("annualSalaryMax")
    currency = (item.get("salaryCurrency") or "").strip()
    if not min_sal and not max_sal:
        return None
    if min_sal and max_sal:
        amount = f"{min_sal:,}–{max_sal:,}"
    elif min_sal:
        amount = f"{min_sal:,}+"
    else:
        amount = f"up to {max_sal:,}"
    return f"{currency} {amount}".strip() if currency else amount


def _matches_query(title: str, description: str, query: str) -> bool:
    if not query.strip():
        return True
    terms = query.lower().split()
    text = (title + " " + description).lower()
    return all(bool(re.search(r"\b" + re.escape(t) + r"\b", text)) for t in terms)


def _geo_matches(job_geo: str, criteria_location: str) -> bool:
    """True if the posting's geo field is compatible with the search location."""
    if not job_geo:
        return True
    geo = job_geo.lower()
    if any(word in geo for word in ("worldwide", "anywhere", "global")):
        return True
    return criteria_location.lower() in geo


class JobicyAdapter(JobBoardAdapter):
    source = "jobicy"

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def _fetch(self, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            return resp.json()

    def _normalize(self, item: dict) -> JobPosting | None:
        try:
            return JobPosting(
                source=self.source,
                source_job_id=str(item["id"]),
                title=item["jobTitle"],
                company=item.get("companyName") or None,
                location=item.get("jobGeo") or None,
                remote_status=RemoteStatus.remote,
                url=item["url"],
                description=_strip_html(item.get("jobDescription") or ""),
                compensation=_build_compensation(item),
                posted_date=_parse_date(item.get("pubDate")),
            )
        except (KeyError, TypeError) as exc:
            logger.warning("jobicy: failed to normalize item %s: %s", item.get("id"), exc)
            return None

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        try:
            data = await self._fetch({"count": _COUNT})
        except Exception as exc:
            cause = exc.last_attempt.exception() if isinstance(exc, RetryError) else exc
            if isinstance(cause, httpx.HTTPStatusError):
                logger.error("jobicy: HTTP %d", cause.response.status_code)
            else:
                logger.error("jobicy: fetch failed: %s", cause)
            return []

        postings: list[JobPosting] = []
        for item in self._safe_iter(data.get("jobs") or []):
            posting = self._normalize(item)
            if posting is None:
                continue
            if not _matches_query(posting.title, posting.description, criteria.query):
                continue
            if criteria.location:
                job_geo = item.get("jobGeo") or ""
                if not _geo_matches(job_geo, criteria.location):
                    continue
            postings.append(posting)

        logger.info("jobicy: query=%r → %d results", criteria.query, len(postings))
        return postings
