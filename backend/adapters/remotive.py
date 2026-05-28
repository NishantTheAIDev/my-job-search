"""Remotive job board adapter (free public API — remote-only listings).

Remote mapping: every Remotive listing is remote by definition.
  candidate_required_location — where the *candidate* must be (e.g. "USA Only",
  "Worldwide", "India"). Empty or "Worldwide" means unrestricted.
  Location filter is applied against this field; remote_only is always satisfied.

Rate limit: Remotive asks for at most 4 requests per day. This adapter makes a
  single request per search() call.
"""

import logging
import re
from datetime import datetime

import httpx
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.adapters.base import JobBoardAdapter
from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria

logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on 5xx server errors and transport failures, not 4xx client errors."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


_BASE_URL = "https://remotive.com/api/remote-jobs"
_LIMIT = 100  # conservative; API max is 200


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _parse_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _location_matches(candidate_location: str, criteria_location: str) -> bool:
    """True if the posting's candidate location is compatible with the search location.

    "Worldwide", "Anywhere", or an empty value means no restriction — matches all.
    """
    if not candidate_location:
        return True
    cand = candidate_location.lower()
    if any(word in cand for word in ("worldwide", "anywhere", "global")):
        return True
    return criteria_location.lower() in cand


class RemotiveAdapter(JobBoardAdapter):
    source = "remotive"

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
            salary = (item.get("salary") or "").strip() or None
            return JobPosting(
                source=self.source,
                source_job_id=str(item["id"]),
                title=item["title"],
                company=item.get("company_name"),
                location=item.get("candidate_required_location") or None,
                remote_status=RemoteStatus.remote,
                url=item["url"],
                description=_strip_html(item.get("description") or ""),
                compensation=salary,
                posted_date=_parse_date(item.get("publication_date")),
            )
        except (KeyError, TypeError) as exc:
            logger.warning("remotive: failed to normalize item %s: %s", item.get("id"), exc)
            return None

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        params: dict = {"limit": _LIMIT}
        if criteria.query.strip():
            params["search"] = criteria.query

        try:
            data = await self._fetch(params)
        except Exception as exc:
            cause = exc.last_attempt.exception() if isinstance(exc, RetryError) else exc
            if isinstance(cause, httpx.HTTPStatusError):
                logger.error("remotive: HTTP %d", cause.response.status_code)
            else:
                logger.error("remotive: fetch failed: %s", cause)
            return []

        postings: list[JobPosting] = []
        for item in self._safe_iter(data.get("jobs") or []):
            posting = self._normalize(item)
            if posting is None:
                continue
            if criteria.location:
                cand_loc = item.get("candidate_required_location") or ""
                if not _location_matches(cand_loc, criteria.location):
                    continue
            postings.append(posting)

        logger.info("remotive: query=%r → %d results", criteria.query, len(postings))
        return postings
