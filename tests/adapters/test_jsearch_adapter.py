"""Fixture-based tests for the JSearch adapter. Never hits live endpoints."""

import json
import re
from pathlib import Path

import pytest
from pydantic import SecretStr

import backend.adapters.jsearch as jsearch_module
from backend.adapters.jsearch import JSearchAdapter
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"
_JSEARCH_URL_RE = re.compile(r"https://jsearch\.p\.rapidapi\.com/search-v2")


def _load_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "jsearch_response.json").read_text())


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    """Provide a fake API key so the adapter doesn't skip on missing credentials."""
    monkeypatch.setattr(jsearch_module.settings, "jsearch_api_key", SecretStr("test-api-key"))


@pytest.fixture
def adapter() -> JSearchAdapter:
    return JSearchAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="software engineer")


# ---------------------------------------------------------------------------
# 1. Happy path: 3 postings, correct source_job_ids and field mapping
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JSEARCH_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert len(postings) == 3
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"jsearch_001", "jsearch_002", "jsearch_003"}

    by_id = {p.source_job_id: p for p in postings}
    assert by_id["jsearch_001"].title == "Senior Python Engineer"
    assert by_id["jsearch_001"].company == "TechCorp Inc"
    assert by_id["jsearch_001"].url == "https://techcorp.example.com/jobs/001"


# ---------------------------------------------------------------------------
# 2. All postings have source="jsearch"
# ---------------------------------------------------------------------------


async def test_all_postings_have_correct_source(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JSEARCH_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert all(p.source == "jsearch" for p in postings)


# ---------------------------------------------------------------------------
# 3. remote_only=True: only remote posting returned, work_from_home param sent
# ---------------------------------------------------------------------------


async def test_remote_only_filters_and_sends_param(httpx_mock, adapter):
    httpx_mock.add_response(url=_JSEARCH_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="python developer", remote_only=True)
    postings = await adapter.search(criteria)

    # Only jsearch_001 has job_is_remote=true
    assert len(postings) == 1
    assert postings[0].source_job_id == "jsearch_001"
    assert postings[0].remote_status == RemoteStatus.remote

    request = httpx_mock.get_requests()[0]
    assert "work_from_home=true" in str(request.url)


# ---------------------------------------------------------------------------
# 4. Remote status: job_is_remote=true → remote; city present → onsite
# ---------------------------------------------------------------------------


async def test_remote_status_mapped(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JSEARCH_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["jsearch_001"].remote_status == RemoteStatus.remote
    assert by_id["jsearch_002"].remote_status == RemoteStatus.onsite
    assert by_id["jsearch_003"].remote_status == RemoteStatus.onsite


# ---------------------------------------------------------------------------
# 5. Location built from city/state/country parts
# ---------------------------------------------------------------------------


async def test_location_built_correctly(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JSEARCH_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    # jsearch_001: no city/state, only country
    assert by_id["jsearch_001"].location == "US"
    # jsearch_002: New York, NY, US
    assert by_id["jsearch_002"].location == "New York, NY, US"
    # jsearch_003: Austin, TX, US
    assert by_id["jsearch_003"].location == "Austin, TX, US"


# ---------------------------------------------------------------------------
# 6. Compensation: salary range, missing salary, hourly rate
# ---------------------------------------------------------------------------


async def test_compensation_mapped(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JSEARCH_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["jsearch_001"].compensation == "USD 130,000–180,000 / year"
    assert by_id["jsearch_002"].compensation is None
    assert by_id["jsearch_003"].compensation == "USD 80–110 / hour"


# ---------------------------------------------------------------------------
# 7. Date parsed from ISO datetime string
# ---------------------------------------------------------------------------


async def test_date_parsed_from_iso(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JSEARCH_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["jsearch_001"].posted_date == "2024-05-01"
    assert by_id["jsearch_002"].posted_date == "2024-05-02"
    assert by_id["jsearch_003"].posted_date == "2024-04-28"


# ---------------------------------------------------------------------------
# 8. Malformed item (missing required key) skipped; valid items returned
# ---------------------------------------------------------------------------


async def test_malformed_item_skipped(httpx_mock, adapter, base_criteria):
    fixture = _load_fixture()
    malformed = {
        "job_id": "bad_001",
        # "job_title" intentionally absent → KeyError in _normalize
        "employer_name": "Ghost Corp",
        "job_apply_link": "https://example.com",
        "job_is_remote": False,
    }
    fixture["data"]["jobs"].insert(0, malformed)
    httpx_mock.add_response(url=_JSEARCH_URL_RE, json=fixture)

    postings = await adapter.search(base_criteria)

    assert len(postings) == 3
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"jsearch_001", "jsearch_002", "jsearch_003"}


# ---------------------------------------------------------------------------
# 9. HTTP error → returns [] without raising
# ---------------------------------------------------------------------------


async def test_http_error_returns_empty(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JSEARCH_URL_RE, status_code=429)

    postings = await adapter.search(base_criteria)

    assert postings == []


# ---------------------------------------------------------------------------
# 10. Non-dict response (RapidAPI auth/quota error as JSON string) → returns []
# ---------------------------------------------------------------------------


async def test_non_dict_response_returns_empty(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_JSEARCH_URL_RE, json="Unauthorized")

    postings = await adapter.search(base_criteria)

    assert postings == []


# ---------------------------------------------------------------------------
# 11. Missing API key → returns [] without making a request
# ---------------------------------------------------------------------------


async def test_no_api_key_returns_empty(monkeypatch, adapter, base_criteria):
    monkeypatch.setattr(jsearch_module.settings, "jsearch_api_key", SecretStr(""))

    postings = await adapter.search(base_criteria)

    assert postings == []


# ---------------------------------------------------------------------------
# 11. Location appended to query when not remote_only
# ---------------------------------------------------------------------------


async def test_location_appended_to_query(httpx_mock, adapter):
    httpx_mock.add_response(url=_JSEARCH_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="data engineer", location="Chicago")
    await adapter.search(criteria)

    request = httpx_mock.get_requests()[0]
    assert "data+engineer+in+Chicago" in str(request.url) or "data engineer in Chicago" in str(
        request.url
    )


# ---------------------------------------------------------------------------
# 12. posted_within_days maps to correct date_posted param
# ---------------------------------------------------------------------------


async def test_date_posted_mapping(httpx_mock, adapter):
    httpx_mock.add_response(url=_JSEARCH_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="engineer", posted_within_days=7)
    await adapter.search(criteria)

    request = httpx_mock.get_requests()[0]
    assert "date_posted=week" in str(request.url)
