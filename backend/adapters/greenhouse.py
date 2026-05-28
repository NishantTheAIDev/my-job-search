"""Greenhouse job board adapter (public board API, per-company-slug)."""

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


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on 5xx server errors and transport failures, not 4xx client errors."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


_BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _parse_date(iso_str: str | None) -> str | None:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _infer_remote(location_name: str) -> RemoteStatus:
    return RemoteStatus.remote if "remote" in location_name.lower() else RemoteStatus.unspecified


def _location_matches(posting_location: str | None, criteria_location: str) -> bool:
    """Return True if the posting's location is within the searched location."""
    if not posting_location:
        return False
    return criteria_location.lower() in posting_location.lower()


def _matches_query(job: dict, query: str) -> bool:
    if not query.strip():
        return True
    terms = query.lower().split()
    text = (job.get("title", "") + " " + _strip_html(job.get("content") or "")).lower()
    # Whole-word match prevents short terms like "ai" from hitting substrings
    # inside unrelated words (e.g. "available", "training", "email").
    return all(bool(re.search(r"\b" + re.escape(t) + r"\b", text)) for t in terms)


class GreenhouseAdapter(JobBoardAdapter):
    source = "greenhouse"

    def _get_slugs(self) -> list[str]:
        raw = settings.greenhouse_companies.strip()
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
            resp = await client.get(url, params={"content": "true"})
            resp.raise_for_status()
            return resp.json().get("jobs") or []

    def _normalize(self, item: dict, slug: str) -> JobPosting | None:
        try:
            location_name = (item.get("location") or {}).get("name") or ""
            return JobPosting(
                source=self.source,
                source_job_id=str(item["id"]),
                title=item["title"],
                company=slug,
                location=location_name or None,
                remote_status=_infer_remote(location_name),
                url=item["absolute_url"],
                description=_strip_html(item.get("content") or ""),
                compensation=None,
                posted_date=_parse_date(item.get("updated_at")),
            )
        except (KeyError, TypeError) as exc:
            logger.warning(
                "greenhouse[%s]: failed to normalize item %s: %s", slug, item.get("id"), exc
            )
            return None

    async def _search_slug(self, slug: str, criteria: SearchCriteria) -> list[JobPosting]:
        try:
            raw = await self._fetch_slug(slug)
        except Exception as exc:
            cause = exc.last_attempt.exception() if isinstance(exc, RetryError) else exc
            if isinstance(cause, httpx.HTTPStatusError):
                logger.error(
                    "greenhouse[%s]: HTTP %d — slug may not use Greenhouse",
                    slug,
                    cause.response.status_code,
                )
            else:
                logger.error("greenhouse[%s]: fetch failed: %s", slug, cause)
            return []

        postings: list[JobPosting] = []
        for item in self._safe_iter(raw):
            if not _matches_query(item, criteria.query):
                continue
            posting = self._normalize(item, slug)
            if posting is None:
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
            logger.debug("greenhouse: no company slugs configured, skipping")
            return []

        results = await asyncio.gather(
            *[self._search_slug(slug, criteria) for slug in slugs],
            return_exceptions=True,
        )
        postings: list[JobPosting] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error("greenhouse: slug search failed: %s", result)
                continue
            postings.extend(result)
        return postings
