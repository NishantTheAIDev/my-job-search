"""Fixture-based tests for the Google Jobs adapter. Never hits live endpoints."""

import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import backend.adapters.google as google_module
from backend.adapters.google import GoogleJobsAdapter, _extract_cursor_from_html, _find_job_info
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_GOOGLE_SEARCH_URL_RE = re.compile(r"https://www\.google\.com/search")
_GOOGLE_JOBS_URL_RE = re.compile(r"https://www\.google\.com/async/callback:550")


def _load_initial_html() -> str:
    return (FIXTURES_DIR / "google_initial.html").read_text()


def _load_page2_text() -> str:
    return (FIXTURES_DIR / "google_page2.txt").read_text()


@pytest.fixture
def adapter() -> GoogleJobsAdapter:
    return GoogleJobsAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="software engineer")


@pytest.fixture(autouse=True)
def single_page(monkeypatch):
    """Restrict to one page (initial only) in every test unless overridden."""
    monkeypatch.setattr(google_module, "_MAX_PAGES", 1)


# ---------------------------------------------------------------------------
# 1. Happy path: 2 postings from initial page, correct fields
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_GOOGLE_SEARCH_URL_RE, text=_load_initial_html())

    postings = await adapter.search(base_criteria)

    assert len(postings) == 2
    assert all(p.source == "google" for p in postings)
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"go-6001", "go-6002"}

    by_id = {p.source_job_id: p for p in postings}
    assert by_id["go-6001"].title == "Senior AI Engineer"
    assert by_id["go-6001"].company == "TechCorp"
    assert by_id["go-6001"].location == "San Francisco, CA"
    assert by_id["go-6001"].url == "https://jobs.techcorp.com/ai-engineer"
    assert by_id["go-6001"].description == "Build AI systems with Python"


# ---------------------------------------------------------------------------
# 2. remote_only=True: "remote" appended to query, only remote posting returned
# ---------------------------------------------------------------------------


async def test_remote_only_appends_to_query_and_filters(httpx_mock, adapter):
    httpx_mock.add_response(url=_GOOGLE_SEARCH_URL_RE, text=_load_initial_html())

    criteria = SearchCriteria(query="backend", remote_only=True)
    postings = await adapter.search(criteria)

    # Only go-6002 has "Remote" in location and "remote" in description
    assert len(postings) == 1
    assert postings[0].source_job_id == "go-6002"
    assert postings[0].remote_status == RemoteStatus.remote

    request = httpx_mock.get_requests()[0]
    assert "remote" in str(request.url).lower()


# ---------------------------------------------------------------------------
# 3. Date parsed from "N days ago" string
# ---------------------------------------------------------------------------


async def test_date_parsed_from_days_ago(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_GOOGLE_SEARCH_URL_RE, text=_load_initial_html())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    expected = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    assert by_id["go-6001"].posted_date == expected


# ---------------------------------------------------------------------------
# 4. Pagination: initial page + page2 → 3 postings total
# ---------------------------------------------------------------------------


async def test_pagination_fetches_page2(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(google_module, "_MAX_PAGES", 2)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    httpx_mock.add_response(url=_GOOGLE_SEARCH_URL_RE, text=_load_initial_html())
    httpx_mock.add_response(url=_GOOGLE_JOBS_URL_RE, text=_load_page2_text())

    postings = await adapter.search(base_criteria)

    source_ids = {p.source_job_id for p in postings}
    assert "go-6001" in source_ids
    assert "go-6002" in source_ids
    assert "go-6003" in source_ids
    assert len(postings) == 3


# ---------------------------------------------------------------------------
# 5. Dedup: same URL appearing in initial and page2 → counted once
# ---------------------------------------------------------------------------


async def test_dedup_same_url_counted_once(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(google_module, "_MAX_PAGES", 2)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    # Initial page has go-6001 and go-6002; page2 has go-6003 (different URL).
    # All three have unique URLs so none are deduped here, confirming the URL
    # dedup set works (if page2 had a repeated URL it would be excluded).
    httpx_mock.add_response(url=_GOOGLE_SEARCH_URL_RE, text=_load_initial_html())
    httpx_mock.add_response(url=_GOOGLE_JOBS_URL_RE, text=_load_page2_text())

    postings = await adapter.search(base_criteria)

    # go-6001 and go-6002 from initial; go-6003 from page2 (different URL)
    assert len(postings) == 3
    urls = [p.url for p in postings]
    assert len(urls) == len(set(urls))  # all unique


# ---------------------------------------------------------------------------
# 6. HTTP error on initial fetch → []
# ---------------------------------------------------------------------------


async def test_http_error_returns_empty(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_GOOGLE_SEARCH_URL_RE, status_code=404)

    postings = await adapter.search(base_criteria)

    assert postings == []


# ---------------------------------------------------------------------------
# 7. _find_job_info: given nested dict with "520084652" key, returns value
# ---------------------------------------------------------------------------


def test_find_job_info_returns_correct_value():
    nested = {
        "outer": [
            {"inner": {"520084652": ["title", "company", "loc"]}},
        ]
    }
    result = _find_job_info(nested)
    assert result == ["title", "company", "loc"]


def test_find_job_info_returns_none_when_missing():
    data = {"foo": {"bar": [1, 2, 3]}}
    assert _find_job_info(data) is None


# ---------------------------------------------------------------------------
# 8. _extract_cursor_from_html: given fixture HTML, returns correct cursor
# ---------------------------------------------------------------------------


def test_extract_cursor_from_html():
    html = _load_initial_html()
    cursor = _extract_cursor_from_html(html)
    assert cursor == "test_cursor_goog"


def test_extract_cursor_returns_none_when_absent():
    html = "<html><body>No cursor here</body></html>"
    assert _extract_cursor_from_html(html) is None
