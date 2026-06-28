"""Fixture-based tests for the Y Combinator adapter. Never hits live endpoints."""

import re
from pathlib import Path

import pytest

from backend.adapters.ycombinator import YCombinatorAdapter
from backend.config import settings
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_YC_URL_RE = re.compile(r"https://www\.ycombinator\.com/jobs")


def _load_fixture() -> str:
    return (FIXTURES_DIR / "ycombinator_response.html").read_text()


@pytest.fixture
def adapter() -> YCombinatorAdapter:
    return YCombinatorAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="")


@pytest.fixture(autouse=True)
def _enabled(monkeypatch):
    monkeypatch.setattr(settings, "ycombinator_enabled", True)


# ---------------------------------------------------------------------------
# 1. Happy-path: featured postings parsed from the data-page JSON blob
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_YC_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert len(postings) == 20
    assert {p.source for p in postings} == {"ycombinator"}

    by_id = {p.source_job_id: p for p in postings}
    job = by_id["97371"]
    assert job.title == "Full Stack AI Engineer"
    assert job.company == "Scispot"
    assert job.compensation == "$80K - $120K"
    # Relative path is resolved to an absolute YC URL
    assert (
        job.url
        == "https://www.ycombinator.com/companies/scispot-io/jobs/SuXlbFO-full-stack-ai-engineer"
    )


# ---------------------------------------------------------------------------
# 2. Remote status is inferred from the location text
# ---------------------------------------------------------------------------


async def test_remote_status_inferred_from_location(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_YC_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    # 97371 location contains "Remote (...)" → remote
    assert by_id["97371"].remote_status == RemoteStatus.remote
    # 92246 is Palo Alto / San Francisco only → unspecified
    assert by_id["92246"].remote_status == RemoteStatus.unspecified


# ---------------------------------------------------------------------------
# 3. remote_only keeps only remote-eligible postings
# ---------------------------------------------------------------------------


async def test_remote_only_filter(httpx_mock, adapter):
    httpx_mock.add_response(url=_YC_URL_RE, text=_load_fixture())

    postings = await adapter.search(SearchCriteria(query="", remote_only=True))

    assert len(postings) == 12
    assert all(p.remote_status == RemoteStatus.remote for p in postings)


# ---------------------------------------------------------------------------
# 4. Query filter uses whole-word matching over title + description
# ---------------------------------------------------------------------------


async def test_query_filter_whole_word(httpx_mock, adapter):
    httpx_mock.add_response(url=_YC_URL_RE, text=_load_fixture())

    postings = await adapter.search(SearchCriteria(query="android"))

    assert len(postings) == 2
    for p in postings:
        assert "android" in f"{p.title} {p.description}".lower()


async def test_query_no_substring_false_positives(httpx_mock, adapter):
    """A short term must not match as a substring of an unrelated word."""
    httpx_mock.add_response(url=_YC_URL_RE, text=_load_fixture())

    # "end" should not match "Backend"/"Frontend" via substring (whole-word \b)
    postings = await adapter.search(SearchCriteria(query="end"))
    for p in postings:
        assert re.search(r"\bend\b", f"{p.title} {p.description}".lower())


# ---------------------------------------------------------------------------
# 5. Location filter (only when not remote-only)
# ---------------------------------------------------------------------------


async def test_location_filter(httpx_mock, adapter):
    httpx_mock.add_response(url=_YC_URL_RE, text=_load_fixture())

    postings = await adapter.search(SearchCriteria(query="", location="Palo Alto"))

    assert len(postings) >= 1
    assert all("palo alto" in (p.location or "").lower() for p in postings)
    assert "92246" in {p.source_job_id for p in postings}


async def test_location_ignored_when_remote_only(httpx_mock, adapter):
    httpx_mock.add_response(url=_YC_URL_RE, text=_load_fixture())

    # A location that no remote posting matches must not exclude remote jobs
    postings = await adapter.search(SearchCriteria(query="", remote_only=True, location="Atlantis"))

    assert len(postings) == 12
    assert all(p.remote_status == RemoteStatus.remote for p in postings)


# ---------------------------------------------------------------------------
# 6. Relative posted-age is converted to an absolute date (best effort)
# ---------------------------------------------------------------------------


async def test_posted_date_parsed(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_YC_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    # "5 days" ago → a valid YYYY-MM-DD string
    assert by_id["97371"].posted_date is not None
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", by_id["97371"].posted_date)


# ---------------------------------------------------------------------------
# 7. Graceful degradation: malformed / missing data-page → []
# ---------------------------------------------------------------------------


async def test_missing_data_page_returns_empty(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_YC_URL_RE, text="<html><body>no data here</body></html>")

    postings = await adapter.search(base_criteria)

    assert postings == []


async def test_http_error_returns_empty(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_YC_URL_RE, status_code=404)

    postings = await adapter.search(base_criteria)

    assert postings == []


# ---------------------------------------------------------------------------
# 8. Disabled via settings → no HTTP call, returns []
# ---------------------------------------------------------------------------


async def test_disabled_returns_empty(adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(settings, "ycombinator_enabled", False)

    postings = await adapter.search(base_criteria)

    assert postings == []
