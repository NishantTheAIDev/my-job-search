"""Arbeitnow job board adapter (free public API — EU/international listings).

Remote mapping: Arbeitnow includes a boolean `remote` field on each posting.
  remote_only=True → post-fetch filter keeping only entries where remote==True.
  No native remote filter parameter exists; filtering is applied client-side.

Pagination: fetches _NUM_PAGES pages concurrently (10 results per page).
  Query and location matching are applied client-side after fetch.
"""

import asyncio
import logging
import re
from datetime import UTC, datetime

import httpx
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.adapters.base import JobBoardAdapter
from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.arbeitnow.com/api/job-board-api"
_NUM_PAGES = 3


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _parse_date(val: int | float | str | None) -> str | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(val, tz=UTC).strftime("%Y-%m-%d")
        except ValueError, OSError:
            return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _matches_query(title: str, description: str, query: str) -> bool:
    if not query.strip():
        return True
    terms = query.lower().split()
    text = (title + " " + description).lower()
    return all(bool(re.search(r"\b" + re.escape(t) + r"\b", text)) for t in terms)


class ArbeitnowAdapter(JobBoardAdapter):
    source = "arbeitnow"

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
            is_remote = bool(item.get("remote"))
            return JobPosting(
                source=self.source,
                source_job_id=item["slug"],
                title=item["title"],
                company=item.get("company_name") or None,
                location=item.get("location") or None,
                remote_status=RemoteStatus.remote if is_remote else RemoteStatus.unspecified,
                url=item["url"],
                description=_strip_html(item.get("description") or ""),
                compensation=item.get("salary") or None,
                posted_date=_parse_date(item.get("created_at")),
            )
        except (KeyError, TypeError) as exc:
            logger.warning("arbeitnow: failed to normalize item %s: %s", item.get("slug"), exc)
            return None

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        pages = await asyncio.gather(
            *[self._fetch_page({"page": p}) for p in range(1, _NUM_PAGES + 1)],
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
                    logger.error("arbeitnow: HTTP %d on page fetch", cause.response.status_code)
                else:
                    logger.error("arbeitnow: page fetch failed: %s", cause)
                continue

            for item in self._safe_iter(page_result.get("data") or []):
                posting = self._normalize(item)
                if posting is None:
                    continue
                if not _matches_query(posting.title, posting.description, criteria.query):
                    continue
                if criteria.remote_only and posting.remote_status != RemoteStatus.remote:
                    continue
                if criteria.location and not criteria.remote_only:
                    loc = (posting.location or "").lower()
                    if criteria.location.lower() not in loc:
                        continue
                postings.append(posting)

        logger.info("arbeitnow: query=%r → %d results", criteria.query, len(postings))
        return postings
