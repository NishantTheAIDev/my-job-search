"""Fixture-based tests for the Indeed adapter. Never hits live endpoints."""

import json
import re
from pathlib import Path

import pytest

import backend.adapters.indeed as indeed_module
from backend.adapters.indeed import IndeedAdapter
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_INDEED_URL_RE = re.compile(r"https://apis\.indeed\.com/graphql")


def _load_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "indeed_response.json").read_text())


@pytest.fixture
def adapter() -> IndeedAdapter:
    return IndeedAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="software engineer")


@pytest.fixture(autouse=True)
def single_page(monkeypatch):
    """Restrict to one page in every test unless explicitly overridden."""
    monkeypatch.setattr(indeed_module, "_MAX_PAGES", 1)


# ---------------------------------------------------------------------------
# 1. Happy path: 3 postings, correct source_job_ids, field mapping
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_INDEED_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert len(postings) == 3
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"3001", "3002", "3003"}

    by_id = {p.source_job_id: p for p in postings}
    assert by_id["3001"].title == "Senior Software Engineer"
    assert by_id["3001"].company == "TechCorp"
    assert by_id["3001"].location == "San Francisco, CA"
    assert by_id["3001"].url == "https://www.indeed.com/viewjob?jk=3001"


# ---------------------------------------------------------------------------
# 2. All postings have source="indeed"
# ---------------------------------------------------------------------------


async def test_all_postings_have_correct_source(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_INDEED_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert all(p.source == "indeed" for p in postings)


# ---------------------------------------------------------------------------
# 3. remote_only=True: only remote posting returned, DSQF7 filter in body
# ---------------------------------------------------------------------------


async def test_remote_only_filters_and_sends_param(httpx_mock, adapter):
    httpx_mock.add_response(url=_INDEED_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="developer", remote_only=True)
    postings = await adapter.search(criteria)

    # Only 3002 has "Remote" location + "Remote" attribute label
    assert len(postings) == 1
    assert postings[0].source_job_id == "3002"
    assert postings[0].remote_status == RemoteStatus.remote

    request = httpx_mock.get_requests()[0]
    body = json.loads(request.content)
    query_str = body["query"]
    assert "DSQF7" in query_str
    assert "f_WT" not in str(request.url)


# ---------------------------------------------------------------------------
# 4. Compensation: estimated salary, baseSalary, and missing salary
# ---------------------------------------------------------------------------


async def test_compensation_mapped(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_INDEED_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    # 3001: estimated baseSalary USD 150000–200000 / year
    assert by_id["3001"].compensation == "USD 150,000–200,000 / year"
    # 3003: direct baseSalary USD 120000–160000 / year
    assert by_id["3003"].compensation == "USD 120,000–160,000 / year"
    # 3002: no salary data
    assert by_id["3002"].compensation is None


# ---------------------------------------------------------------------------
# 5. Date parsed from millisecond timestamp
# ---------------------------------------------------------------------------


async def test_date_parsed_from_ms_timestamp(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_INDEED_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    # 1714521600000 ms = 2024-05-01
    assert by_id["3001"].posted_date == "2024-05-01"


# ---------------------------------------------------------------------------
# 6. HTML stripped from description
# ---------------------------------------------------------------------------


async def test_html_stripped_from_description(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_INDEED_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    desc = by_id["3001"].description
    assert "backend" in desc
    assert "Python" in desc
    assert "<p>" not in desc
    assert "<strong>" not in desc


# ---------------------------------------------------------------------------
# 7. Malformed item (missing key) skipped; valid items still returned
# ---------------------------------------------------------------------------


async def test_malformed_item_skipped(httpx_mock, adapter, base_criteria):
    fixture = _load_fixture()
    malformed = {
        "job": {
            # "key" intentionally absent
            "title": "Ghost Job",
            "datePublished": 1714521600000,
            "description": {"html": "<p>No key.</p>"},
            "location": {"city": "Nowhere", "admin1Code": None, "countryCode": "US", "formatted": {"long": "Nowhere"}},
            "compensation": {"baseSalary": None, "estimated": None, "currencyCode": "USD"},
            "attributes": [],
            "employer": {"name": "Ghost Corp"},
        }
    }
    fixture["data"]["jobSearch"]["results"].insert(0, malformed)

    httpx_mock.add_response(url=_INDEED_URL_RE, json=fixture)

    postings = await adapter.search(base_criteria)

    assert len(postings) == 3
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"3001", "3002", "3003"}


# ---------------------------------------------------------------------------
# 8. HTTP error → returns [] without raising
# ---------------------------------------------------------------------------


async def test_http_error_returns_empty(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_INDEED_URL_RE, status_code=404)

    postings = await adapter.search(base_criteria)

    assert postings == []
