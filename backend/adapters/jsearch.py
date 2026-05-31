"""JSearch (RapidAPI) job board adapter.

Remote mapping: ``job_is_remote`` boolean field; ``work_from_home=true`` query
  param is also sent when ``remote_only=True``. A post-fetch filter removes any
  non-remote results the API returns despite the flag, ensuring the contract holds.

Rate limits: subject to the caller's RapidAPI plan; one request per search()
  call fetches up to _NUM_PAGES pages in a single API call.

Authentication: ``JSEARCH_API_KEY`` env var (RapidAPI key).
"""

import logging
from datetime import datetime

import httpx
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.adapters.base import JobBoardAdapter
from backend.config import settings
from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria

logger = logging.getLogger(__name__)

_BASE_URL = "https://jsearch.p.rapidapi.com/search-v2"
_HOST = "jsearch.p.rapidapi.com"
_NUM_PAGES = 3


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _parse_date(dt_str: str | None) -> str | None:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_compensation(item: dict) -> str | None:
    min_sal = item.get("job_min_salary")
    max_sal = item.get("job_max_salary")
    currency = item.get("job_salary_currency") or "USD"
    period = (item.get("job_salary_period") or "YEAR").lower()
    if min_sal is not None and max_sal is not None:
        return f"{currency} {int(min_sal):,}–{int(max_sal):,} / {period}"
    if min_sal is not None:
        return f"{currency} {int(min_sal):,}+ / {period}"
    return None


def _infer_remote(item: dict) -> RemoteStatus:
    if item.get("job_is_remote"):
        return RemoteStatus.remote
    city = item.get("job_city") or ""
    state = item.get("job_state") or ""
    country = item.get("job_country") or ""
    combined = f"{city} {state} {country}".lower()
    if "hybrid" in combined:
        return RemoteStatus.hybrid
    if city or state:
        return RemoteStatus.onsite
    return RemoteStatus.unspecified


def _build_location(item: dict) -> str | None:
    parts = [p for p in [item.get("job_city"), item.get("job_state"), item.get("job_country")] if p]
    return ", ".join(parts) if parts else None


def _map_date_posted(posted_within_days: int | None) -> str:
    if not posted_within_days:
        return "all"
    if posted_within_days <= 1:
        return "today"
    if posted_within_days <= 3:
        return "3days"
    if posted_within_days <= 7:
        return "week"
    if posted_within_days <= 30:
        return "month"
    return "all"


class JSearchAdapter(JobBoardAdapter):
    source = "jsearch"

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def _fetch(self, params: dict) -> object:
        headers = {
            "x-rapidapi-key": settings.jsearch_api_key.get_secret_value(),
            "x-rapidapi-host": _HOST,
        }
        logger.debug("jsearch: GET %s params=%s", _BASE_URL, params)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_BASE_URL, params=params, headers=headers)
            logger.debug(
                "jsearch: response status=%d content-type=%s body_preview=%.300s",
                resp.status_code,
                resp.headers.get("content-type", "?"),
                resp.text,
            )
            resp.raise_for_status()
            return resp.json()

    def _normalize(self, item: object) -> JobPosting | None:
        if not isinstance(item, dict):
            logger.warning(
                "jsearch: skipping non-dict item (type=%s, value=%.80s)",
                type(item).__name__,
                repr(item),
            )
            return None
        try:
            return JobPosting(
                source=self.source,
                source_job_id=item["job_id"],
                title=item["job_title"],
                company=item.get("employer_name"),
                location=_build_location(item),
                remote_status=_infer_remote(item),
                url=item["job_apply_link"],
                description=item.get("job_description") or "",
                compensation=_parse_compensation(item),
                posted_date=_parse_date(item.get("job_posted_at_datetime_utc")),
            )
        except (KeyError, TypeError) as exc:
            job_id = item.get("job_id") if isinstance(item, dict) else repr(item)[:80]
            logger.warning("jsearch: failed to normalize item %s: %s", job_id, exc)
            return None

    def _map_criteria(self, criteria: SearchCriteria) -> dict:
        query = criteria.query
        if criteria.location and not criteria.remote_only:
            query = f"{query} in {criteria.location}"

        params: dict = {
            "query": query,
            "num_pages": str(_NUM_PAGES),
            "date_posted": _map_date_posted(criteria.posted_within_days),
        }
        if criteria.remote_only:
            params["work_from_home"] = "true"
        if criteria.employment_type:
            params["employment_types"] = criteria.employment_type.upper()
        return params

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        if not settings.jsearch_api_key.get_secret_value():
            logger.warning("jsearch: JSEARCH_API_KEY not configured, skipping")
            return []

        params = self._map_criteria(criteria)
        logger.info("jsearch: searching query=%r params=%s", criteria.query, params)

        try:
            data = await self._fetch(params)
        except Exception as exc:
            cause = exc.last_attempt.exception() if isinstance(exc, RetryError) else exc
            if isinstance(cause, httpx.HTTPStatusError):
                logger.error(
                    "jsearch: HTTP %d — body: %.300s",
                    cause.response.status_code,
                    cause.response.text,
                )
            else:
                logger.error("jsearch: fetch failed: %s", cause)
            return []

        logger.debug("jsearch: raw response type=%s", type(data).__name__)

        if not isinstance(data, dict):
            logger.error(
                "jsearch: expected dict response, got %s — body: %.300s",
                type(data).__name__,
                repr(data),
            )
            return []

        status = data.get("status")
        if status and status != "OK":
            logger.error(
                "jsearch: API returned status=%r — full response: %.500s",
                status,
                repr(data),
            )
            return []

        data_field = data.get("data")
        # search-v2: data["data"]["jobs"]; plain search: data["data"] is the list directly
        raw_items = data_field.get("jobs") if isinstance(data_field, dict) else data_field

        if not isinstance(raw_items, list):
            logger.error(
                "jsearch: could not find jobs list — data['data'] type=%s — full response: %.500s",
                type(data_field).__name__,
                repr(data),
            )
            return []

        logger.debug("jsearch: received %d raw items", len(raw_items))

        postings: list[JobPosting] = []
        skipped_remote = 0
        for item in self._safe_iter(raw_items):
            posting = self._normalize(item)
            if posting is None:
                continue
            if criteria.remote_only and posting.remote_status != RemoteStatus.remote:
                skipped_remote += 1
                continue
            postings.append(posting)

        if skipped_remote:
            logger.debug(
                "jsearch: dropped %d non-remote results (remote_only=True)", skipped_remote
            )

        logger.info(
            "jsearch: query=%r → %d/%d results kept",
            criteria.query,
            len(postings),
            len(raw_items),
        )
        return postings
