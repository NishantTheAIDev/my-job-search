"""Job-market news — Google News RSS (region-aware primary) with a Hacker News fallback.

Both sources are free and keyless and work worldwide. This replaces the previous GDELT
client, whose hard 1-request/5s rate limit made it unreliable when a user browsed
several regions in a session.

Output is normalized to {title, url, domain, seendate} where ``seendate`` uses the
``YYYYMMDDThhmmssZ`` format the frontend already parses (``parseGdeltDate``).
"""

import logging
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings
from backend.services.insights._http import retry_transient, safe_err

logger = logging.getLogger(__name__)

_GOOGLE_BASE = "https://news.google.com/rss/search"
_HN_BASE = "https://hn.algolia.com/api/v1/search_by_date"

# `when:30d` keeps results recent. Google News interprets the boolean query.
_QUERY = '(hiring OR layoffs OR "job market" OR recruitment) when:30d'
_HN_QUERY = "hiring OR layoffs OR job market"
_MAX_RECORDS = 15

# region → Google News locale params (hl, gl, ceid). `world` falls back to US/English.
_REGION_LOCALE: dict[str, tuple[str, str, str]] = {
    "in": ("en-IN", "IN", "IN:en"),
    "us": ("en-US", "US", "US:en"),
    "gb": ("en-GB", "GB", "GB:en"),
    "world": ("en-US", "US", "US:en"),
}

_UA = "Mozilla/5.0 (compatible; my-job-search/1.0; +https://example.invalid)"


def _is_safe_url(url: str | None) -> bool:
    """Only allow http(s) links — blocks javascript:/data: URIs from untrusted sources."""
    return bool(url) and url.lower().startswith(("http://", "https://"))


def _seendate_from_rfc2822(value: str | None) -> str:
    """Convert an RSS pubDate (RFC 2822) to the YYYYMMDDThhmmssZ format the UI parses."""
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    except TypeError, ValueError:
        return ""


def _seendate_from_unix(ts: int | None) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts), UTC).strftime("%Y%m%dT%H%M%SZ")
    except TypeError, ValueError, OSError:
        return ""


def _strip_source_suffix(title: str, source_name: str) -> str:
    """Google News appends ' - <Source>' to titles; drop it since we show the domain."""
    suffix = f" - {source_name}"
    if source_name and title.endswith(suffix):
        return title[: -len(suffix)]
    return title


@retry(
    retry=retry_transient,
    wait=wait_exponential(min=1, max=8),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _fetch(url: str, params: dict) -> httpx.Response:
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url, params=params, headers={"User-Agent": _UA})
        resp.raise_for_status()
        return resp


def _parse_google_rss(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items: list[dict] = []
    for item in root.findall(".//item")[:_MAX_RECORDS]:
        link = item.findtext("link") or ""
        if not _is_safe_url(link):
            continue
        source = item.find("source")
        source_name = (source.text if source is not None else "") or ""
        source_url = source.get("url") if source is not None else ""
        domain = urlsplit(source_url or link).netloc
        items.append(
            {
                "title": _strip_source_suffix(item.findtext("title") or "", source_name),
                "url": link,
                "domain": domain,
                "seendate": _seendate_from_rfc2822(item.findtext("pubDate")),
            }
        )
    return items


async def _google_news(region: str) -> list[dict]:
    hl, gl, ceid = _REGION_LOCALE.get(region, _REGION_LOCALE["world"])
    params = {"q": _QUERY, "hl": hl, "gl": gl, "ceid": ceid}
    resp = await _fetch(_GOOGLE_BASE, params)
    return _parse_google_rss(resp.text)


async def _hackernews() -> list[dict]:
    """Global tech-focused fallback (Hacker News via the keyless Algolia API)."""
    params = {"query": _HN_QUERY, "tags": "story", "hitsPerPage": _MAX_RECORDS}
    resp = await _fetch(_HN_BASE, params)
    hits = resp.json().get("hits") or []
    items: list[dict] = []
    for hit in hits:
        url = hit.get("url") or ""
        if not _is_safe_url(url):  # skips Ask HN posts (no external URL)
            continue
        items.append(
            {
                "title": hit.get("title") or "",
                "url": url,
                "domain": urlsplit(url).netloc,
                "seendate": _seendate_from_unix(hit.get("created_at_i")),
            }
        )
    return items


async def get_news(region: str) -> list[dict]:
    """Fetch recent job-market news for a region.

    Tries Google News RSS (region-aware) first, then falls back to Hacker News.
    Returns a list of {title, url, domain, seendate}; [] gracefully on error/disabled.
    """
    if not settings.news_enabled:
        return []

    try:
        items = await _google_news(region)
        if items:
            return items
        logger.info("news: google news returned no items region=%r — trying fallback", region)
    except Exception as exc:
        logger.warning(
            "news: google news region=%r error=%s — trying fallback", region, safe_err(exc)
        )

    try:
        return await _hackernews()
    except Exception as exc:
        logger.warning("news: hackernews fallback error=%s", safe_err(exc))
        return []
