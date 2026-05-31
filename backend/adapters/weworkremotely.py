"""We Work Remotely adapter (public RSS feed — remote-only listings).

Remote mapping: every WWR listing is remote by definition.
  Feed URL: https://weworkremotely.com/remote-jobs.rss

Title format in feed: "Company: Job Title" — split on first ': ' to extract both.
Source job ID: last path segment of the listing URL (e.g. "12345-senior-engineer").

Rate limit: single request per search() call; results are filtered client-side.
"""

import logging
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.adapters.base import JobBoardAdapter
from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria

logger = logging.getLogger(__name__)

_FEED_URL = "https://weworkremotely.com/remote-jobs.rss"


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _parse_rfc2822_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
    except Exception:
        return None


def _extract_job_id(url: str) -> str:
    """Return the last path segment of the URL as the stable source ID."""
    try:
        segment = urlparse(url).path.rstrip("/").split("/")[-1]
        return segment if segment else url
    except Exception:
        return url


def _split_title(raw: str) -> tuple[str, str | None]:
    """Split 'Company: Job Title' into (job_title, company)."""
    if ": " in raw:
        company, _, job_title = raw.partition(": ")
        return job_title.strip() or raw.strip(), company.strip() or None
    return raw.strip(), None


def _matches_query(title: str, description: str, query: str) -> bool:
    if not query.strip():
        return True
    terms = query.lower().split()
    text = (title + " " + description).lower()
    return all(bool(re.search(r"\b" + re.escape(t) + r"\b", text)) for t in terms)


class WeWorkRemotelyAdapter(JobBoardAdapter):
    source = "weworkremotely"

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def _fetch(self) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_FEED_URL)
            resp.raise_for_status()
            return resp.text

    def _normalize(self, item: ET.Element) -> JobPosting | None:
        try:
            raw_title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            if not raw_title or not url:
                return None
            job_title, company = _split_title(raw_title)
            description_html = (item.findtext("description") or "").strip()
            return JobPosting(
                source=self.source,
                source_job_id=_extract_job_id(url),
                title=job_title,
                company=company,
                location=None,
                remote_status=RemoteStatus.remote,
                url=url,
                description=_strip_html(description_html),
                compensation=None,
                posted_date=_parse_rfc2822_date(item.findtext("pubDate")),
            )
        except Exception as exc:
            logger.warning("weworkremotely: failed to normalize item: %s", exc)
            return None

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        try:
            xml_text = await self._fetch()
        except Exception as exc:
            cause = exc.last_attempt.exception() if isinstance(exc, RetryError) else exc
            if isinstance(cause, httpx.HTTPStatusError):
                logger.error("weworkremotely: HTTP %d", cause.response.status_code)
            else:
                logger.error("weworkremotely: fetch failed: %s", cause)
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.error("weworkremotely: XML parse error: %s", exc)
            return []

        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")

        postings: list[JobPosting] = []
        for xml_item in self._safe_iter(items):
            posting = self._normalize(xml_item)
            if posting is None:
                continue
            if not _matches_query(posting.title, posting.description, criteria.query):
                continue
            postings.append(posting)

        logger.info("weworkremotely: query=%r → %d results", criteria.query, len(postings))
        return postings
