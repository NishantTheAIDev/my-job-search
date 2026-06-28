"""Ashby job board adapter (public posting API, per-company-slug).

Ashby exposes a free, unauthenticated job-board API per company:
`https://api.ashbyhq.com/posting-api/job-board/{slug}` → `{"jobs": [...]}`.
Many YC startups host their postings here; configure slugs via ASHBY_COMPANIES
(comma-separated), the same pattern as Greenhouse and Lever.

Remote mapping: each job carries a `workplaceType` ("Remote"/"Hybrid"/"Onsite")
plus an `isRemote` boolean; `workplaceType` is mapped, with `isRemote` as a
fallback. Query filtering is whole-word (so "ai" doesn't match "available").
"""

import asyncio
import logging
import re
from datetime import datetime

import httpx
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.adapters.base import JobBoardAdapter
from backend.config import settings
from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"

_WORKPLACE_MAP: dict[str, RemoteStatus] = {
    "remote": RemoteStatus.remote,
    "hybrid": RemoteStatus.hybrid,
    "onsite": RemoteStatus.onsite,
    "on-site": RemoteStatus.onsite,
}


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on 5xx server errors and transport failures, not 4xx client errors."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _parse_date(iso_str: str | None) -> str | None:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _map_remote(item: dict) -> RemoteStatus:
    workplace = (item.get("workplaceType") or "").strip().lower()
    if workplace in _WORKPLACE_MAP:
        return _WORKPLACE_MAP[workplace]
    if item.get("isRemote"):
        return RemoteStatus.remote
    return RemoteStatus.unspecified


def _location_matches(posting_location: str | None, criteria_location: str) -> bool:
    if not posting_location:
        return False
    return criteria_location.lower() in posting_location.lower()


def _matches_query(title: str, description: str, query: str) -> bool:
    if not query.strip():
        return True
    terms = query.lower().split()
    text = (title + " " + description).lower()
    return all(bool(re.search(r"\b" + re.escape(t) + r"\b", text)) for t in terms)


class AshbyAdapter(JobBoardAdapter):
    source = "ashby"

    def _get_slugs(self) -> list[str]:
        raw = settings.ashby_companies.strip()
        if not raw:
            return []
        return [s.strip() for s in raw.split(",") if s.strip()]

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def _fetch_slug(self, slug: str) -> list[dict]:
        url = _BASE_URL.format(slug=slug)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json().get("jobs") or []

    def _normalize(self, item: dict, slug: str) -> JobPosting | None:
        try:
            description = item.get("descriptionPlain") or _strip_html(
                item.get("descriptionHtml") or ""
            )
            return JobPosting(
                source=self.source,
                source_job_id=str(item["id"]),
                title=item["title"],
                company=slug,
                location=item.get("location") or None,
                remote_status=_map_remote(item),
                url=item["jobUrl"],
                description=description,
                compensation=item.get("compensation"),
                posted_date=_parse_date(item.get("publishedAt")),
            )
        except (KeyError, TypeError) as exc:
            logger.warning("ashby[%s]: failed to normalize item %s: %s", slug, item.get("id"), exc)
            return None

    async def _search_slug(self, slug: str, criteria: SearchCriteria) -> list[JobPosting]:
        try:
            raw = await self._fetch_slug(slug)
        except Exception as exc:
            cause = exc.last_attempt.exception() if isinstance(exc, RetryError) else exc
            if isinstance(cause, httpx.HTTPStatusError):
                logger.error(
                    "ashby[%s]: HTTP %d — slug may not use Ashby",
                    slug,
                    cause.response.status_code,
                )
            else:
                logger.error("ashby[%s]: fetch failed: %s", slug, cause)
            return []

        postings: list[JobPosting] = []
        for item in self._safe_iter(raw):
            # Unlisted postings are hidden from the public board — skip them.
            if item.get("isListed") is False:
                continue
            posting = self._normalize(item, slug)
            if posting is None:
                continue
            if not _matches_query(posting.title, posting.description, criteria.query):
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
        return postings

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        slugs = self._get_slugs()
        if not slugs:
            logger.debug("ashby: no company slugs configured, skipping")
            return []

        results = await asyncio.gather(
            *[self._search_slug(slug, criteria) for slug in slugs],
            return_exceptions=True,
        )
        postings: list[JobPosting] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error("ashby: slug search failed: %s", result)
                continue
            postings.extend(result)
        return postings
