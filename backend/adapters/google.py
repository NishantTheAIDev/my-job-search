"""Google Jobs adapter (HTML + async callback scraping).

Two-step approach:
  1. GET the initial search page to extract embedded job JSON and a pagination cursor.
  2. GET subsequent pages via the async callback endpoint using the cursor.

Remote mapping: appends "remote" to the search query when remote_only is set.
  Remote status is also inferred from description and location text.

Rate limit: up to _MAX_PAGES pages with _PAGE_DELAY between pages.
Deduplication by URL across pages.
"""

import asyncio
import json
import logging
import random
import re
from datetime import datetime, timedelta

import httpx
from bs4 import BeautifulSoup
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.adapters.base import JobBoardAdapter
from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.google.com/search"
_CALLBACK_URL = "https://www.google.com/async/callback:550"
_MAX_PAGES = 3
_PAGE_DELAY = (2.0, 4.0)

# Static JS bundle reference — required by Google's callback endpoint
_ASYNC_PARAM = (
    "_basejs:/xjs/_/js/k=xjs.s.en_US.JwveA-JiKmg.2018.O/am=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAACAAAoICAAAAAAAKMAfAAAAIAQAAAAAAAAAAAAACCAAAEJDAAACAAAAAGABAIAAARBAAABAAAAAgAgQAABAASKAfv8JAAABAAAAAAwAQAQACQAAAAAAcAEAQABoCAAAABAAAIABAACAAAAEAAAAFAAAAAAAAAAAAAAAAAAAAAAAAACAQADoBwAAAAAAAAAAAAAQBAAAAATQAAoACOAHAAAAAAAAAQAAAIIAAAA_ZAACAAAAAAAAcB8APB4wHFJ4AAAAAAAAAAAAAAAACECCYA5If0EACAAAAAAAAAAAAAAAAAAAUgRNXG4AMAE/dg=0/br=1/rs=ACT90oGxMeaFMCopIHq5tuQM-6_3M_VMjQ"
)

_HEADERS_INITIAL = {
    "accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "accept-language": "en-US,en;q=0.9",
    "referer": "https://www.google.com/",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
}

_HEADERS_JOBS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "referer": "https://www.google.com/",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

_REMOTE_KEYWORDS = ("remote", "work from home", "wfh", "anywhere")
_HYBRID_KEYWORDS = ("hybrid",)

_CURSOR_RE = re.compile(r'<div jsname="Yust4d"[^>]+data-async-fc="([^"]+)"')
# Match the job info array following the key "520084652":
# Uses DOTALL so . matches newlines; the suffix "}]]]]]" anchors the end of the value.
_JOB_KEY = "520084652"
_JOB_RE = re.compile(r'"520084652":\s*(\[(?:[^[\]]|\[(?:[^[\]]|\[[^[\]]*\])*\])*\])', re.DOTALL)


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on 5xx server errors and transport failures, not 4xx or 429."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _infer_remote(title: str, location: str, description: str) -> RemoteStatus:
    text = f"{title} {location} {description}".lower()
    if any(kw in text for kw in _REMOTE_KEYWORDS):
        return RemoteStatus.remote
    if any(kw in text for kw in _HYBRID_KEYWORDS):
        return RemoteStatus.hybrid
    return RemoteStatus.unspecified


def _parse_days_ago(days_str: str | None) -> str | None:
    if not days_str:
        return None
    match = re.search(r"(\d+)", days_str)
    if match:
        days = int(match.group(1))
        return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return None


def _find_job_info(data: object) -> list | None:
    """Recursively search nested dict/list for key '520084652'."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "520084652" and isinstance(value, list):
                return value
            result = _find_job_info(value)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = _find_job_info(item)
            if result is not None:
                return result
    return None


def _extract_cursor_from_html(html: str) -> str | None:
    match = _CURSOR_RE.search(html)
    return match.group(1) if match else None


class GoogleJobsAdapter(JobBoardAdapter):
    source = "google"

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def _fetch_initial(self, query: str) -> str:
        # ibp=htl;jobs triggers Google's dedicated Jobs widget in the SERP
        params = {"q": query, "ibp": "htl;jobs"}
        async with httpx.AsyncClient(
            timeout=15.0, headers=_HEADERS_INITIAL, follow_redirects=True
        ) as client:
            resp = await client.get(_SEARCH_URL, params=params)
            resp.raise_for_status()
            return resp.text

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def _fetch_next_page(self, cursor: str) -> str:
        params = {"fc": cursor, "fcv": "3", "async": _ASYNC_PARAM}
        async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS_JOBS) as client:
            resp = await client.get(_CALLBACK_URL, params=params)
            resp.raise_for_status()
            return resp.text

    def _normalize(self, job_info: list, seen_urls: set[str]) -> JobPosting | None:
        try:
            title = job_info[0]
            company = job_info[1]
            location = job_info[2]
            url = job_info[3][0][0] if job_info[3] and job_info[3][0] else None
            if not url or url in seen_urls:
                return None
            description = job_info[19] if len(job_info) > 19 else ""
            days_str = job_info[12] if len(job_info) > 12 else None
            job_id = str(job_info[28]) if len(job_info) > 28 else str(abs(hash(url)))

            posted_date = _parse_days_ago(days_str)
            remote_status = _infer_remote(title, location or "", description or "")

            return JobPosting(
                source=self.source,
                source_job_id=job_id,
                title=title,
                company=company,
                location=location,
                remote_status=remote_status,
                url=url,
                description=description or "",
                compensation=None,
                posted_date=posted_date,
            )
        except (KeyError, TypeError, AttributeError, IndexError) as exc:
            logger.warning("google: failed to normalize item: %s", exc)
            return None

    def _extract_jobs_from_ld_json(self, html: str, seen_urls: set[str]) -> list[JobPosting]:
        """Extract JobPosting items from <script type=application/ld+json> blocks."""
        postings: list[JobPosting] = []
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            # Handle both single objects and @graph arrays
            items = data if isinstance(data, list) else [data]
            for item in items:
                graph = item.get("@graph") or []
                candidates = graph if graph else [item]
                for obj in candidates:
                    if obj.get("@type") != "JobPosting":
                        continue
                    try:
                        url = obj.get("url") or obj.get("mainEntityOfPage", {}).get("@id", "")
                        if not url or url in seen_urls:
                            continue
                        title = obj.get("title") or obj.get("name", "")
                        if not title:
                            continue
                        org = obj.get("hiringOrganization") or {}
                        company = org.get("name") if isinstance(org, dict) else None
                        job_loc = obj.get("jobLocation") or {}
                        if isinstance(job_loc, list):
                            job_loc = job_loc[0] if job_loc else {}
                        address = job_loc.get("address") if isinstance(job_loc, dict) else {}
                        if isinstance(address, str):
                            location = address
                        elif isinstance(address, dict):
                            parts = [
                                address.get("addressLocality"),
                                address.get("addressRegion"),
                                address.get("addressCountry"),
                            ]
                            location = ", ".join(str(p) for p in parts if p) or None
                        else:
                            location = None
                        description = obj.get("description") or ""
                        date_posted = obj.get("datePosted")
                        job_id = str(abs(hash(url)))
                        remote_status = _infer_remote(title, location or "", description)
                        seen_urls.add(url)
                        postings.append(
                            JobPosting(
                                source=self.source,
                                source_job_id=job_id,
                                title=title,
                                company=company,
                                location=location,
                                remote_status=remote_status,
                                url=url,
                                description=description,
                                compensation=None,
                                posted_date=date_posted,
                            )
                        )
                    except (KeyError, TypeError, AttributeError):
                        continue
        return postings

    def _extract_jobs_from_html(self, html: str, seen_urls: set[str]) -> list[JobPosting]:
        # Primary: structured data in ld+json blocks (more stable across Google HTML changes)
        postings = self._extract_jobs_from_ld_json(html, seen_urls)
        if postings:
            return postings
        # Fallback: embedded JSON array keyed by Google's internal data key
        for match in _JOB_RE.finditer(html):
            try:
                job_info = json.loads(match.group(1))
                posting = self._normalize(job_info, seen_urls)
                if posting is not None:
                    seen_urls.add(posting.url)
                    postings.append(posting)
            except (json.JSONDecodeError, Exception) as exc:
                logger.warning("google: failed to parse embedded job JSON: %s", exc)
        return postings

    def _extract_jobs_from_callback(self, text: str, seen_urls: set[str]) -> list[JobPosting]:
        postings: list[JobPosting] = []
        try:
            start_idx = text.find("[[[")
            end_idx = text.rindex("]]]") + 3
            if start_idx == -1 or end_idx < 3:
                return postings
            parsed = json.loads(text[start_idx:end_idx])[0]
            for array in parsed:
                try:
                    if not isinstance(array, list) or len(array) < 2:
                        continue
                    _, job_data_str = array[0], array[1]
                    if not isinstance(job_data_str, str) or not job_data_str.startswith("[[["):
                        continue
                    job_d = json.loads(job_data_str)
                    job_info = _find_job_info(job_d)
                    if job_info:
                        posting = self._normalize(job_info, seen_urls)
                        if posting is not None:
                            seen_urls.add(posting.url)
                            postings.append(posting)
                except (json.JSONDecodeError, TypeError, IndexError, ValueError):
                    continue
        except (json.JSONDecodeError, ValueError, IndexError) as exc:
            logger.warning("google: failed to parse callback response: %s", exc)
        return postings

    def _build_query(self, criteria: SearchCriteria) -> str:
        query = f"{criteria.query} jobs"
        if criteria.remote_only:
            query += " remote"
        elif criteria.location:
            query += f" near {criteria.location}"
        if criteria.posted_within_days:
            if criteria.posted_within_days <= 1:
                query += " since yesterday"
            elif criteria.posted_within_days <= 7:
                query += " in the last week"
            else:
                query += " in the last month"
        return query

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        query = self._build_query(criteria)
        seen_urls: set[str] = set()
        postings: list[JobPosting] = []

        try:
            initial_html = await self._fetch_initial(query)
        except Exception as exc:
            cause = exc.last_attempt.exception() if isinstance(exc, RetryError) else exc
            if isinstance(cause, httpx.HTTPStatusError):
                logger.error("google: HTTP %d on initial fetch", cause.response.status_code)
            else:
                logger.error("google: initial fetch failed: %s", cause)
            return []

        page_postings = self._extract_jobs_from_html(initial_html, seen_urls)
        for p in page_postings:
            if criteria.remote_only and p.remote_status != RemoteStatus.remote:
                continue
            postings.append(p)

        cursor = _extract_cursor_from_html(initial_html)

        for page in range(1, _MAX_PAGES):
            if not cursor:
                break

            await asyncio.sleep(random.uniform(*_PAGE_DELAY))

            try:
                callback_text = await self._fetch_next_page(cursor)
            except Exception as exc:
                cause = exc.last_attempt.exception() if isinstance(exc, RetryError) else exc
                if isinstance(cause, httpx.HTTPStatusError):
                    logger.error("google: HTTP %d on page %d", cause.response.status_code, page + 1)
                else:
                    logger.error("google: page %d fetch failed: %s", page + 1, cause)
                break

            page_postings = self._extract_jobs_from_callback(callback_text, seen_urls)
            for p in page_postings:
                if criteria.remote_only and p.remote_status != RemoteStatus.remote:
                    continue
                postings.append(p)

            cursor = _extract_cursor_from_html(callback_text)

        logger.info("google: query=%r → %d results", criteria.query, len(postings))
        return postings
