"""Fixture-based tests for the news client (Google News RSS + Hacker News fallback)."""

import re
from pathlib import Path

import httpx
import pytest

from backend.config import settings
from backend.services.insights.news import get_news

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_GOOGLE_RE = re.compile(r"https://news\.google\.com/rss/search.*")
_HN_RE = re.compile(r"https://hn\.algolia\.com/.*")

_EMPTY_RSS = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'


def _rss() -> str:
    return (FIXTURES_DIR / "googlenews_rss.xml").read_text()


@pytest.fixture(autouse=True)
def _enable_news(monkeypatch):
    monkeypatch.setattr(settings, "news_enabled", True)


# ---------------------------------------------------------------------------
# Google News (primary)
# ---------------------------------------------------------------------------


async def test_google_news_parses_rss(httpx_mock):
    httpx_mock.add_response(url=_GOOGLE_RE, text=_rss())

    news = await get_news("in")

    # The malicious javascript: link is dropped, leaving 2 safe items.
    assert len(news) == 2
    first = news[0]
    # Trailing " - <Source>" suffix stripped from the title.
    assert first["title"] == "Big Tech hiring rebounds in 2026"
    assert first["url"] == "https://news.google.com/rss/articles/ABC123"
    # Domain comes from the <source url> host, not the Google redirect link.
    assert first["domain"] == "timesofindia.indiatimes.com"
    # pubDate converted to the YYYYMMDDThhmmssZ format the frontend parses.
    assert first["seendate"] == "20260614T083000Z"


async def test_google_news_drops_unsafe_urls(httpx_mock):
    httpx_mock.add_response(url=_GOOGLE_RE, text=_rss())
    news = await get_news("us")
    assert all(n["url"].startswith("https://") for n in news)


async def test_region_uses_locale_params(httpx_mock):
    httpx_mock.add_response(url=_GOOGLE_RE, text=_rss())

    await get_news("in")

    req = httpx_mock.get_requests()[0]
    assert req.url.params["hl"] == "en-IN"
    assert req.url.params["gl"] == "IN"
    assert req.url.params["ceid"] == "IN:en"


# ---------------------------------------------------------------------------
# Hacker News fallback
# ---------------------------------------------------------------------------


async def test_falls_back_to_hn_when_google_empty(httpx_mock):
    httpx_mock.add_response(url=_GOOGLE_RE, text=_EMPTY_RSS)
    httpx_mock.add_response(
        url=_HN_RE,
        json={
            "hits": [
                {"title": "HN story", "url": "https://example.com/a", "created_at_i": 1781000000},
            ]
        },
    )

    news = await get_news("us")
    assert len(news) == 1
    assert news[0]["domain"] == "example.com"


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_falls_back_to_hn_when_google_errors(httpx_mock):
    # Google 500 (retried up to 3 times, then reraised) → fall through to HN.
    for _ in range(3):
        httpx_mock.add_response(url=_GOOGLE_RE, status_code=500)
    httpx_mock.add_response(
        url=_HN_RE,
        json={"hits": [{"title": "HN", "url": "https://x.io/p", "created_at_i": 1781000000}]},
    )

    news = await get_news("gb")
    assert len(news) == 1
    assert news[0]["url"] == "https://x.io/p"


async def test_hn_skips_items_without_external_url(httpx_mock):
    import json

    httpx_mock.add_response(url=_GOOGLE_RE, text=_EMPTY_RSS)
    hn = json.loads((FIXTURES_DIR / "hackernews.json").read_text())
    httpx_mock.add_response(url=_HN_RE, json=hn)

    news = await get_news("world")
    # The "Ask HN" item (url: null) is skipped → 2 of 3 hits remain.
    assert len(news) == 2
    assert news[0]["seendate"] == "20260609T101320Z"  # from created_at_i 1781000000


# ---------------------------------------------------------------------------
# Disabled / total failure
# ---------------------------------------------------------------------------


async def test_news_disabled_returns_empty(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "news_enabled", False)
    news = await get_news("in")
    assert news == []
    assert httpx_mock.get_requests() == []  # no network when disabled


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_both_sources_fail_returns_empty(httpx_mock):
    for _ in range(3):
        httpx_mock.add_response(url=_GOOGLE_RE, status_code=503)
    for _ in range(3):
        httpx_mock.add_response(url=_HN_RE, status_code=503)

    news = await get_news("us")
    assert news == []


async def test_transport_error_falls_through(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("boom"), url=_GOOGLE_RE)
    httpx_mock.add_exception(httpx.ConnectError("boom"), url=_GOOGLE_RE)
    httpx_mock.add_exception(httpx.ConnectError("boom"), url=_GOOGLE_RE)
    httpx_mock.add_response(
        url=_HN_RE,
        json={"hits": [{"title": "HN", "url": "https://x.io/p", "created_at_i": 1781000000}]},
    )
    news = await get_news("in")
    assert len(news) == 1
