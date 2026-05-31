"""Fixture-based tests for the Jobicy adapter. Never hits live endpoints."""

import json
import re
from pathlib import Path

import pytest

from backend.adapters.jobicy import JobicyAdapter
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"
_JOBICY_URL_RE = re.compile(r"https://jobicy\.com/api/v2/remote-jobs")


def _load_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "jobicy_response.json").read_text())


@pytest.fixture
def adapter() -> JobicyAdapter:
    return JobicyAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="")


# ---------------------------------------------------------------------------
# 1. Happy path: 3 postings, correct source_job_ids and field mapping
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JOBICY_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert len(postings) == 3
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"12345", "12346", "12347"}

    by_id = {p.source_job_id: p for p in postings}
    assert by_id["12345"].title == "Senior Python Engineer"
    assert by_id["12345"].company == "TechCorp"
    assert by_id["12345"].url == "https://jobicy.com/jobs/12345-senior-python-engineer"


# ---------------------------------------------------------------------------
# 2. All postings have source="jobicy"
# ---------------------------------------------------------------------------


async def test_all_postings_have_correct_source(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JOBICY_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert all(p.source == "jobicy" for p in postings)


# ---------------------------------------------------------------------------
# 3. All postings have remote_status=remote (Jobicy is remote-only)
# ---------------------------------------------------------------------------


async def test_all_postings_are_remote(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JOBICY_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert all(p.remote_status == RemoteStatus.remote for p in postings)


# ---------------------------------------------------------------------------
# 4. remote_only=True: all postings returned (all are already remote)
# ---------------------------------------------------------------------------


async def test_remote_only_returns_all(httpx_mock, adapter):
    httpx_mock.add_response(url=_JOBICY_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="", remote_only=True)
    postings = await adapter.search(criteria)

    assert len(postings) == 3


# ---------------------------------------------------------------------------
# 5. Query filter: whole-word client-side matching on title + description
# ---------------------------------------------------------------------------


async def test_query_filter(httpx_mock, adapter):
    httpx_mock.add_response(url=_JOBICY_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="python")
    postings = await adapter.search(criteria)

    # Only job 12345 has "Python" in its description
    assert len(postings) == 1
    assert postings[0].source_job_id == "12345"


# ---------------------------------------------------------------------------
# 6. Location filter: jobGeo "USA Only" matches location="USA"
# ---------------------------------------------------------------------------


async def test_location_filter(httpx_mock, adapter):
    httpx_mock.add_response(url=_JOBICY_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="", location="USA")
    postings = await adapter.search(criteria)

    # "Worldwide" (12345) and "USA Only" (12346) match; "Europe" (12347) does not
    assert len(postings) == 2
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"12345", "12346"}


# ---------------------------------------------------------------------------
# 7. "Worldwide" geo matches any location criteria
# ---------------------------------------------------------------------------


async def test_worldwide_geo_matches_any_location(httpx_mock, adapter):
    httpx_mock.add_response(url=_JOBICY_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="", location="Japan")
    postings = await adapter.search(criteria)

    # Only "Worldwide" (12345) matches "Japan"; the others don't
    assert len(postings) == 1
    assert postings[0].source_job_id == "12345"


# ---------------------------------------------------------------------------
# 8. Compensation: range, null, and currency all mapped correctly
# ---------------------------------------------------------------------------


async def test_compensation_mapped(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JOBICY_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["12345"].compensation == "USD 120,000–160,000"
    assert by_id["12346"].compensation is None
    assert by_id["12347"].compensation == "EUR 100,000–130,000"


# ---------------------------------------------------------------------------
# 9. Date parsed from "YYYY-MM-DD HH:MM:SS" format
# ---------------------------------------------------------------------------


async def test_date_parsed(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JOBICY_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["12345"].posted_date == "2024-05-01"
    assert by_id["12346"].posted_date == "2024-05-02"
    assert by_id["12347"].posted_date == "2024-04-28"


# ---------------------------------------------------------------------------
# 10. HTML stripped from description
# ---------------------------------------------------------------------------


async def test_html_stripped_from_description(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JOBICY_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}
    desc = by_id["12345"].description

    assert "Python" in desc
    assert "<p>" not in desc
    assert "<strong>" not in desc


# ---------------------------------------------------------------------------
# 11. Malformed item (missing required key) is skipped; valid items returned
# ---------------------------------------------------------------------------


async def test_malformed_item_skipped(httpx_mock, adapter, base_criteria):
    fixture = _load_fixture()
    malformed = {
        # "id" intentionally absent → KeyError in _normalize
        "url": "https://jobicy.com/jobs/bad",
        "jobTitle": "Ghost Job",
        "companyName": "Ghost Corp",
        "jobGeo": "Worldwide",
    }
    fixture["jobs"].insert(0, malformed)
    httpx_mock.add_response(url=_JOBICY_URL_RE, json=fixture)

    postings = await adapter.search(base_criteria)

    assert len(postings) == 3
    assert {p.source_job_id for p in postings} == {"12345", "12346", "12347"}


# ---------------------------------------------------------------------------
# 12. HTTP error → returns [] without raising
# ---------------------------------------------------------------------------


async def test_http_error_returns_empty(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JOBICY_URL_RE, status_code=404)

    postings = await adapter.search(base_criteria)

    assert postings == []
