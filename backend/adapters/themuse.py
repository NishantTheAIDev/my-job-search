"""The Muse job board adapter (public v2 API — no auth required)."""

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


_BASE_URL = "https://www.themuse.com/api/public/jobs"
_MAX_PAGES = 3  # pages fetched concurrently per search (20 jobs each)


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _parse_date(iso_str: str | None) -> str | None:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _infer_remote(locations: list[dict]) -> RemoteStatus:
    for loc in locations:
        if "remote" in (loc.get("name") or "").lower():
            return RemoteStatus.remote
    return RemoteStatus.unspecified


def _matches_query(title: str, description: str, query: str) -> bool:
    if not query.strip():
        return True
    terms = query.lower().split()
    text = (title + " " + description).lower()
    return all(bool(re.search(r"\b" + re.escape(t) + r"\b", text)) for t in terms)


class TheMuseAdapter(JobBoardAdapter):
    source = "themuse"

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def _fetch_page(self, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            return resp.json()

    def _normalize(self, item: dict) -> JobPosting | None:
        try:
            locations = item.get("locations") or []
            location_name = locations[0].get("name") if locations else None
            description = _strip_html(item.get("contents") or "")
            return JobPosting(
                source=self.source,
                source_job_id=str(item["id"]),
                title=item["name"],
                company=(item.get("company") or {}).get("name"),
                location=location_name,
                remote_status=_infer_remote(locations),
                url=(item.get("refs") or {})["landing_page"],
                description=description,
                compensation=None,
                posted_date=_parse_date(item.get("publication_date")),
            )
        except (KeyError, TypeError) as exc:
            logger.warning("themuse: failed to normalize item %s: %s", item.get("id"), exc)
            return None

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        base_params: dict = {}
        if settings.themuse_api_key:
            base_params["api_key"] = settings.themuse_api_key

        pages = await asyncio.gather(
            *[self._fetch_page({**base_params, "page": p}) for p in range(_MAX_PAGES)],
            return_exceptions=True,
        )

        postings: list[JobPosting] = []
        for page_result in pages:
            if isinstance(page_result, Exception):
                cause = (
                    page_result.last_attempt.exception()
                    if isinstance(page_result, RetryError)
                    else page_result
                )
                if isinstance(cause, httpx.HTTPStatusError):
                    logger.error("themuse: HTTP %d on page fetch", cause.response.status_code)
                else:
                    logger.error("themuse: page fetch failed: %s", cause)
                continue
            for item in self._safe_iter(page_result.get("results") or []):
                posting = self._normalize(item)
                if posting is None:
                    continue
                if not _matches_query(posting.title, posting.description, criteria.query):
                    continue
                if criteria.remote_only and posting.remote_status != RemoteStatus.remote:
                    continue
                postings.append(posting)

        logger.info("themuse: query=%r → %d results", criteria.query, len(postings))
        return postings
