"""LinkedIn job board adapter (guest search HTML API — no auth required).

LinkedIn's public guest endpoint returns HTML fragments containing job cards.
Pages are fetched sequentially with a small random async delay to stay within
LinkedIn's rate tolerance; _MAX_PAGES caps the total fetch depth per search.

Descriptions are not populated at search time — each would require a separate
page request. The url field points to the canonical job page; descriptions can
be fetched on-demand if needed.

Remote mapping: f_WT=2 sends the remote filter natively. Remote status is also
inferred client-side from title and location text for listings that arrive
without the flag set (e.g. "Work From Home" in the title).
"""

import asyncio
import logging
import random
from datetime import datetime

import httpx
from bs4 import BeautifulSoup, Tag
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.adapters.base import JobBoardAdapter
from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
_RESULTS_PER_PAGE = 25
_MAX_PAGES = 3
_PAGE_DELAY = (2.0, 4.0)

_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

_REMOTE_KEYWORDS = ("remote", "work from home", "wfh")


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on 5xx server errors and transport failures, not 4xx or 429."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _parse_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _infer_remote(title: str, location: str) -> RemoteStatus:
    text = f"{title} {location}".lower()
    if any(kw in text for kw in _REMOTE_KEYWORDS):
        return RemoteStatus.remote
    return RemoteStatus.unspecified


class LinkedInAdapter(JobBoardAdapter):
    source = "linkedin"

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def _fetch_page(self, params: dict) -> str:
        async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS) as client:
            resp = await client.get(_SEARCH_URL, params=params)
            resp.raise_for_status()
            return resp.text

    def _normalize(self, card: Tag) -> JobPosting | None:
        try:
            href_tag = card.find("a", class_="base-card__full-link")
            if not href_tag or not href_tag.get("href"):
                return None
            job_id = href_tag["href"].split("?")[0].split("-")[-1]

            title_tag = card.find("span", class_="sr-only")
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title:
                return None

            company_tag = card.find("h4", class_="base-search-card__subtitle")
            company_a = company_tag.find("a") if company_tag else None
            company = company_a.get_text(strip=True) if company_a else None

            metadata = card.find("div", class_="base-search-card__metadata")
            location_tag = (
                metadata.find("span", class_="job-search-card__location") if metadata else None
            )
            location = location_tag.get_text(strip=True) if location_tag else None

            time_tag = None
            if metadata:
                time_tag = metadata.find(
                    "time", class_="job-search-card__listdate"
                ) or metadata.find("time", class_="job-search-card__listdate--new")
            posted_date = _parse_date(time_tag.get("datetime") if time_tag else None)

            salary_tag = card.find("span", class_="job-search-card__salary-info")
            compensation = (
                (salary_tag.get_text(separator=" ").strip() or None) if salary_tag else None
            )

            return JobPosting(
                source=self.source,
                source_job_id=job_id,
                title=title,
                company=company,
                location=location,
                remote_status=_infer_remote(title, location or ""),
                url=f"https://www.linkedin.com/jobs/view/{job_id}",
                description="",
                compensation=compensation,
                posted_date=posted_date,
            )
        except (AttributeError, KeyError, TypeError) as exc:
            logger.warning("linkedin: failed to normalize card: %s", exc)
            return None

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        params: dict = {"keywords": criteria.query, "start": 0}
        if criteria.remote_only:
            params["f_WT"] = 2
        elif criteria.location:
            params["location"] = criteria.location
        if criteria.posted_within_days:
            params["f_TPR"] = f"r{criteria.posted_within_days * 86400}"

        postings: list[JobPosting] = []
        seen_ids: set[str] = set()

        for page in range(_MAX_PAGES):
            params["start"] = page * _RESULTS_PER_PAGE
            try:
                html = await self._fetch_page(params)
            except Exception as exc:
                cause = exc.last_attempt.exception() if isinstance(exc, RetryError) else exc
                if isinstance(cause, httpx.HTTPStatusError):
                    logger.error("linkedin: HTTP %d", cause.response.status_code)
                else:
                    logger.error("linkedin: fetch failed: %s", cause)
                break

            soup = BeautifulSoup(html, "html.parser")
            cards = soup.find_all("div", class_="base-search-card")
            if not cards:
                break

            for card in self._safe_iter(cards):
                posting = self._normalize(card)
                if posting is None or posting.source_job_id in seen_ids:
                    continue
                seen_ids.add(posting.source_job_id)
                if criteria.remote_only and posting.remote_status != RemoteStatus.remote:
                    continue
                postings.append(posting)

            if page < _MAX_PAGES - 1 and cards:
                await asyncio.sleep(random.uniform(*_PAGE_DELAY))

        logger.info("linkedin: query=%r → %d results", criteria.query, len(postings))
        return postings