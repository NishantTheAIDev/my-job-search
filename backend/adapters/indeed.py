"""Indeed job board adapter (unofficial GraphQL API).

Remote mapping: filter via composite keyword filter using attribute key "DSQF7"
(Indeed's internal identifier for remote listings). Remote status is also inferred
client-side from location text and attribute labels.

Rate limit: cursor-based pagination, up to _MAX_PAGES pages per search.
"""

import asyncio
import logging
import random
import re
from datetime import UTC, datetime

import httpx
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.adapters.base import JobBoardAdapter
from backend.config import settings
from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria

logger = logging.getLogger(__name__)

_GRAPHQL_URL = "https://apis.indeed.com/graphql"
_MAX_PAGES = 3
_PAGE_DELAY = (2.0, 4.0)

_HEADERS = {
    "Host": "apis.indeed.com",
    "content-type": "application/json",
    "accept": "application/json",
    "indeed-locale": "en-US",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 like Mac OS X)"
        " AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Indeed App 193.1"
    ),
    "indeed-app-info": "appv=193.1; appid=com.indeed.jobsearch; osv=16.6.1; os=ios; dtype=phone",
}

_REMOTE_KEYWORDS = ("remote", "work from home", "wfh", "anywhere")

_GQL_QUERY = """
query GetJobData {{
    jobSearch(
        {what}
        {location}
        limit: 25
        {cursor}
        sort: RELEVANCE
        {filters}
    ) {{
        pageInfo {{ nextCursor }}
        results {{
            job {{
                key title datePublished
                description {{ html }}
                location {{ city admin1Code countryCode formatted {{ long }} }}
                compensation {{
                    baseSalary {{ unitOfWork range {{ ... on Range {{ min max }} }} }}
                    estimated {{
                        currencyCode
                        baseSalary {{ unitOfWork range {{ ... on Range {{ min max }} }} }}
                    }}
                    currencyCode
                }}
                attributes {{ key label }}
                employer {{ name relativeCompanyPageUrl }}
            }}
        }}
    }}
}}
"""


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on 5xx server errors and transport failures, not 4xx or 429."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _infer_remote(location_long: str, attributes: list[dict]) -> RemoteStatus:
    text = location_long.lower()
    attr_labels = " ".join(a.get("label", "") for a in attributes).lower()
    combined = f"{text} {attr_labels}"
    if any(kw in combined for kw in _REMOTE_KEYWORDS):
        return RemoteStatus.remote
    return RemoteStatus.unspecified


def _format_compensation(comp: dict | None) -> str | None:
    if not comp:
        return None
    currency = comp.get("currencyCode") or ""

    base = comp.get("baseSalary")
    if base and base.get("range"):
        r = base["range"]
        unit = (base.get("unitOfWork") or "").lower()
        mn = r.get("min")
        mx = r.get("max")
        if mn is not None and mx is not None:
            return f"{currency} {mn:,.0f}–{mx:,.0f} / {unit}"

    estimated = comp.get("estimated")
    if estimated and estimated.get("baseSalary"):
        eb = estimated["baseSalary"]
        if eb.get("range"):
            r = eb["range"]
            unit = (eb.get("unitOfWork") or "").lower()
            est_currency = estimated.get("currencyCode") or currency
            mn = r.get("min")
            mx = r.get("max")
            if mn is not None and mx is not None:
                return f"{est_currency} {mn:,.0f}–{mx:,.0f} / {unit}"

    return None


class IndeedAdapter(JobBoardAdapter):
    source = "indeed"

    def _build_query(self, criteria: SearchCriteria, cursor: str | None) -> str:
        what = f'what: "{criteria.query}"' if criteria.query else ""

        if criteria.location and not criteria.remote_only:
            location = f'location: {{where: "{criteria.location}", radius: 50, radiusUnit: MILES}}'
        else:
            location = ""

        cursor_part = f'cursor: "{cursor}"' if cursor else ""

        if criteria.remote_only:
            filters = (
                "filters: { composite: { filters: ["
                '{ keyword: { field: "attributes", keys: ["DSQF7"] } }] } }'
            )
        else:
            filters = ""

        return _GQL_QUERY.format(
            what=what,
            location=location,
            cursor=cursor_part,
            filters=filters,
        )

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def _fetch_page(self, criteria: SearchCriteria, cursor: str | None) -> dict:
        query = self._build_query(criteria, cursor)
        payload = {"query": query}
        headers = {**_HEADERS, "indeed-api-key": settings.indeed_api_key.get_secret_value()}
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            resp = await client.post(_GRAPHQL_URL, json=payload)
            resp.raise_for_status()
            return resp.json()

    def _normalize(self, result: dict) -> JobPosting | None:
        try:
            job = result["job"]
            job_key = job["key"]
            title = job["title"]

            employer = job.get("employer") or {}
            company = employer.get("name")

            loc = job.get("location") or {}
            city = loc.get("city") or ""
            admin1 = loc.get("admin1Code") or ""
            if city and admin1:
                location = f"{city}, {admin1}"
            elif city:
                location = city
            else:
                location = None

            loc_long = (loc.get("formatted") or {}).get("long") or ""
            attributes = job.get("attributes") or []
            remote_status = _infer_remote(loc_long, attributes)

            desc_html = (job.get("description") or {}).get("html") or ""
            description = _strip_html(desc_html)

            ts_ms = job.get("datePublished")
            posted_date = None
            if ts_ms is not None:
                posted_date = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).strftime("%Y-%m-%d")

            compensation = _format_compensation(job.get("compensation"))

            return JobPosting(
                source=self.source,
                source_job_id=str(job_key),
                title=title,
                company=company,
                location=location,
                remote_status=remote_status,
                url=f"https://www.indeed.com/viewjob?jk={job_key}",
                description=description,
                compensation=compensation,
                posted_date=posted_date,
            )
        except (KeyError, TypeError, AttributeError) as exc:
            logger.warning("indeed: failed to normalize item: %s", exc)
            return None

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        if not settings.indeed_api_key.get_secret_value():
            logger.info("indeed: INDEED_API_KEY not set — skipping")
            return []

        postings: list[JobPosting] = []
        seen_ids: set[str] = set()
        cursor: str | None = None

        for page in range(_MAX_PAGES):
            try:
                data = await self._fetch_page(criteria, cursor)
            except Exception as exc:
                cause = exc.last_attempt.exception() if isinstance(exc, RetryError) else exc
                if isinstance(cause, httpx.HTTPStatusError):
                    logger.error("indeed: HTTP %d", cause.response.status_code)
                else:
                    logger.error("indeed: fetch failed: %s", cause)
                break

            job_search = (data.get("data") or {}).get("jobSearch") or {}
            results = job_search.get("results") or []
            cursor = (job_search.get("pageInfo") or {}).get("nextCursor")

            for result in self._safe_iter(results):
                posting = self._normalize(result)
                if posting is None or posting.source_job_id in seen_ids:
                    continue
                seen_ids.add(posting.source_job_id)
                if criteria.remote_only and posting.remote_status != RemoteStatus.remote:
                    continue
                postings.append(posting)

            if not results or cursor is None:
                break

            if page < _MAX_PAGES - 1:
                await asyncio.sleep(random.uniform(*_PAGE_DELAY))

        logger.info("indeed: query=%r → %d results", criteria.query, len(postings))
        return postings
