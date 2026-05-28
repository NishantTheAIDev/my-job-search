"""Fixture-based tests for the LinkedIn adapter. Never hits live endpoints."""

import asyncio
import re
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import backend.adapters.linkedin as linkedin_module
from backend.adapters.linkedin import LinkedInAdapter
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_LINKEDIN_URL_RE = re.compile(
    r"https://www\.linkedin\.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)


def _load_fixture() -> str:
    return (FIXTURES_DIR / "linkedin_response.html").read_text()


@pytest.fixture
def adapter() -> LinkedInAdapter:
    return LinkedInAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="")


@pytest.fixture(autouse=True)
def single_page(monkeypatch):
    """Restrict to one page in every test unless explicitly overridden."""
    monkeypatch.setattr(linkedin_module, "_MAX_PAGES", 1)


# ---------------------------------------------------------------------------
# 1. Happy-path: all cards normalized and returned
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_LINKEDIN_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert len(postings) == 4
    assert all(p.source == "linkedin" for p in postings)

    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"7001", "7002", "7003", "7004"}

    by_id = {p.source_job_id: p for p in postings}
    assert by_id["7001"].title == "Senior AI Engineer"
    assert by_id["7001"].company == "TechCorp"
    assert by_id["7001"].location == "San Francisco, CA"
    assert by_id["7001"].url == "https://www.linkedin.com/jobs/view/7001"
    assert by_id["7001"].posted_date == "2024-05-01"


# ---------------------------------------------------------------------------
# 2. remote_only=True: f_WT=2 sent in params; only remote listings returned
# ---------------------------------------------------------------------------


async def test_remote_only_sends_param_and_filters(httpx_mock, adapter):
    httpx_mock.add_response(url=_LINKEDIN_URL_RE, text=_load_fixture())

    criteria = SearchCriteria(query="", remote_only=True)
    postings = await adapter.search(criteria)

    # 7002 (location="Remote") and 7004 (title contains "Work From Home")
    assert len(postings) == 2
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"7002", "7004"}
    assert all(p.remote_status == RemoteStatus.remote for p in postings)

    request = httpx_mock.get_requests()[0]
    assert "f_WT=2" in str(request.url)


# ---------------------------------------------------------------------------
# 3. Remote status inferred from location text and title text
# ---------------------------------------------------------------------------


async def test_remote_status_inferred(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_LINKEDIN_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["7001"].remote_status == RemoteStatus.unspecified  # "San Francisco, CA"
    assert by_id["7002"].remote_status == RemoteStatus.remote        # location="Remote"
    assert by_id["7003"].remote_status == RemoteStatus.unspecified  # "New York, NY"
    assert by_id["7004"].remote_status == RemoteStatus.remote        # title has "Work From Home"


# ---------------------------------------------------------------------------
# 4. Compensation: salary text mapped; absent salary tag → None
# ---------------------------------------------------------------------------


async def test_compensation_mapped(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_LINKEDIN_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["7001"].compensation == "$150,000 - $200,000/yr"
    assert by_id["7002"].compensation is None
    assert by_id["7003"].compensation is None
    assert by_id["7004"].compensation is None


# ---------------------------------------------------------------------------
# 5. Date: both listdate and listdate--new classes parsed correctly
# ---------------------------------------------------------------------------


async def test_date_parsed_from_both_time_classes(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_LINKEDIN_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["7001"].posted_date == "2024-05-01"   # listdate class
    assert by_id["7002"].posted_date == "2024-05-10"   # listdate--new class
    assert by_id["7003"].posted_date == "2024-04-20"
    assert by_id["7004"].posted_date == "2024-05-05"


# ---------------------------------------------------------------------------
# 6. Malformed card (no href) is skipped; valid cards still returned
# ---------------------------------------------------------------------------


async def test_malformed_card_skipped(httpx_mock, adapter, base_criteria):
    malformed = """
    <div class="base-search-card">
      <h4 class="base-search-card__subtitle"><a>Ghost Corp</a></h4>
    </div>
    """
    html = malformed + _load_fixture()
    httpx_mock.add_response(url=_LINKEDIN_URL_RE, text=html)

    postings = await adapter.search(base_criteria)

    assert len(postings) == 4
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"7001", "7002", "7003", "7004"}


# ---------------------------------------------------------------------------
# 7. HTTP 429 (non-retryable) → returns [] without raising
# ---------------------------------------------------------------------------


async def test_http_429_returns_empty(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_LINKEDIN_URL_RE, status_code=429)

    postings = await adapter.search(base_criteria)

    assert postings == []


# ---------------------------------------------------------------------------
# 8. HTTP 404 → returns [] without raising
# ---------------------------------------------------------------------------


async def test_http_error_returns_empty(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_LINKEDIN_URL_RE, status_code=404)

    postings = await adapter.search(base_criteria)

    assert postings == []


# ---------------------------------------------------------------------------
# 9. Pagination stops when a page returns no cards
# ---------------------------------------------------------------------------


async def test_pagination_stops_when_no_cards(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(linkedin_module, "_MAX_PAGES", 2)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    httpx_mock.add_response(url=_LINKEDIN_URL_RE, text=_load_fixture())   # page 0: 4 cards
    httpx_mock.add_response(url=_LINKEDIN_URL_RE, text="<html></html>")   # page 1: no cards

    postings = await adapter.search(SearchCriteria(query="engineer"))

    assert len(postings) == 4
    assert len(httpx_mock.get_requests()) == 2


# ---------------------------------------------------------------------------
# 10. Duplicate job IDs across pages are deduplicated
# ---------------------------------------------------------------------------


async def test_dedup_across_pages(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(linkedin_module, "_MAX_PAGES", 2)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    fixture = _load_fixture()
    httpx_mock.add_response(url=_LINKEDIN_URL_RE, text=fixture)   # page 0
    httpx_mock.add_response(url=_LINKEDIN_URL_RE, text=fixture)   # page 1: same IDs

    postings = await adapter.search(SearchCriteria(query=""))

    assert len(postings) == 4  # not 8
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"7001", "7002", "7003", "7004"}