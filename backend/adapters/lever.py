"""Lever job board adapter (public v0 API, per-company-slug)."""

import asyncio
import logging
import re
from datetime import UTC, datetime

import httpx
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.adapters.base import JobBoardAdapter
from backend.config import settings
from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria

logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on 5xx server errors and transport failures, not 4xx client errors."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


_BASE_URL = "https://api.lever.co/v0/postings/{company}"

_WORKPLACE_MAP: dict[str, RemoteStatus] = {
    "remote": RemoteStatus.remote,
    "hybrid": RemoteStatus.hybrid,
    "onsite": RemoteStatus.onsite,
}


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _parse_ms_timestamp(ms: int | None) -> str | None:
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%d")
    except ValueError, OSError:
        return None


def _location_matches(posting_location: str | None, criteria_location: str) -> bool:
    """Return True if the posting's location is within the searched location."""
    if not posting_location:
        return False
    return criteria_location.lower() in posting_location.lower()


def _matches_query(title: str, description: str, query: str) -> bool:
    if not query.strip():
        return True
    terms = query.lower().split()
    text = (title + " " + description).lower()
    return all(bool(re.search(r"\b" + re.escape(t) + r"\b", text)) for t in terms)


class LeverAdapter(JobBoardAdapter):
    source = "lever"

    def _get_slugs(self) -> list[str]:
        raw = settings.lever_companies.strip()
        if not raw:
            return []
        return [s.strip() for s in raw.split(",") if s.strip()]

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def _fetch_slug(self, slug: str) -> list[dict]:
        url = _BASE_URL.format(company=slug)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params={"mode": "json"})
            resp.raise_for_status()
            return resp.json() or []

    def _normalize(self, item: dict, slug: str) -> JobPosting | None:
        try:
            description = item.get("descriptionPlain") or _strip_html(item.get("description") or "")
            categories = item.get("categories") or {}
            workplace = (item.get("workplaceType") or "").lower()
            return JobPosting(
                source=self.source,
                source_job_id=str(item["id"]),
                title=item["text"],
                company=slug,
                location=categories.get("location"),
                remote_status=_WORKPLACE_MAP.get(workplace, RemoteStatus.unspecified),
                url=item["hostedUrl"],
                description=description,
                compensation=None,
                posted_date=_parse_ms_timestamp(item.get("createdAt")),
            )
        except (KeyError, TypeError) as exc:
            logger.warning("lever[%s]: failed to normalize item %s: %s", slug, item.get("id"), exc)
            return None

    async def _search_slug(self, slug: str, criteria: SearchCriteria) -> list[JobPosting]:
        try:
            raw = await self._fetch_slug(slug)
        except Exception as exc:
            cause = exc.last_attempt.exception() if isinstance(exc, RetryError) else exc
            if isinstance(cause, httpx.HTTPStatusError):
                logger.error(
                    "lever[%s]: HTTP %d — slug may not use Lever",
                    slug,
                    cause.response.status_code,
                )
            else:
                logger.error("lever[%s]: fetch failed: %s", slug, cause)
            return []

        postings: list[JobPosting] = []
        for item in self._safe_iter(raw):
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
            logger.debug("lever: no company slugs configured, skipping")
            return []

        results = await asyncio.gather(
            *[self._search_slug(slug, criteria) for slug in slugs],
            return_exceptions=True,
        )
        postings: list[JobPosting] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error("lever: slug search failed: %s", result)
                continue
            postings.extend(result)
        return postings
