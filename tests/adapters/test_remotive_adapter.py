"""Fixture-based tests for the Remotive adapter. Never hits live endpoints."""

import json
import re
from pathlib import Path

import pytest

from backend.adapters.remotive import RemotiveAdapter
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_REMOTIVE_URL_RE = re.compile(r"https://remotive\.com/api/remote-jobs")


def _load_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "remotive_response.json").read_text())


@pytest.fixture
def adapter() -> RemotiveAdapter:
    return RemotiveAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="")


# ---------------------------------------------------------------------------
# 1. Happy-path: all postings normalized and returned
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_REMOTIVE_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert len(postings) == 4
    assert all(p.source == "remotive" for p in postings)

    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"6001", "6002", "6003", "6004"}

    by_id = {p.source_job_id: p for p in postings}
    assert by_id["6001"].title == "Senior AI Engineer"
    assert by_id["6001"].company == "TechCorp"
    assert by_id["6001"].url == "https://remotive.com/remote-jobs/software-dev/senior-ai-engineer-6001"
    assert by_id["6001"].posted_date == "2024-05-01"
    assert by_id["6001"].location == "Worldwide"


# ---------------------------------------------------------------------------
# 2. All listings are always remote — remote_status must be remote
# ---------------------------------------------------------------------------


async def test_all_postings_are_remote(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_REMOTIVE_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert all(p.remote_status == RemoteStatus.remote for p in postings)


# ---------------------------------------------------------------------------
# 3. remote_only=True — all listings still returned (they're all remote)
# ---------------------------------------------------------------------------


async def test_remote_only_returns_all(httpx_mock, adapter):
    httpx_mock.add_response(url=_REMOTIVE_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="", remote_only=True)
    postings = await adapter.search(criteria)

    assert len(postings) == 4


# ---------------------------------------------------------------------------
# 4. Location "India": Worldwide (6001) and India (6003) match;
#    USA Only (6002) and Europe Only (6004) do not
# ---------------------------------------------------------------------------


async def test_location_filter_india(httpx_mock, adapter):
    httpx_mock.add_response(url=_REMOTIVE_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="", location="India")
    postings = await adapter.search(criteria)

    assert len(postings) == 2
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"6001", "6003"}


# ---------------------------------------------------------------------------
# 5. Location "Europe": Worldwide (6001) and Europe Only (6004) match
# ---------------------------------------------------------------------------


async def test_location_filter_europe(httpx_mock, adapter):
    httpx_mock.add_response(url=_REMOTIVE_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="", location="Europe")
    postings = await adapter.search(criteria)

    assert len(postings) == 2
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"6001", "6004"}


# ---------------------------------------------------------------------------
# 6. Compensation: salary string mapped; empty string becomes None
# ---------------------------------------------------------------------------


async def test_compensation_mapping(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_REMOTIVE_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["6001"].compensation == "$120,000 - $160,000"
    assert by_id["6003"].compensation == "₹30,00,000 - ₹50,00,000"
    assert by_id["6002"].compensation is None  # empty salary string → None


# ---------------------------------------------------------------------------
# 7. HTML is stripped from description
# ---------------------------------------------------------------------------


async def test_html_stripped_from_description(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_REMOTIVE_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    desc = by_id["6001"].description
    assert "AI" in desc
    assert "Python" in desc
    assert "<p>" not in desc
    assert "<strong>" not in desc
    assert "<em>" not in desc


# ---------------------------------------------------------------------------
# 8. Malformed item (missing required fields) is skipped; others returned
# ---------------------------------------------------------------------------


async def test_malformed_item_skipped(httpx_mock, adapter, base_criteria):
    fixture = _load_fixture()
    malformed = {
        "title": "Ghost Job",
        "company_name": "Nobody",
        "candidate_required_location": "Worldwide",
        "description": "<p>No id or url.</p>",
        # "id" and "url" intentionally absent
    }
    fixture["jobs"].insert(0, malformed)

    httpx_mock.add_response(url=_REMOTIVE_URL_RE, json=fixture)

    postings = await adapter.search(base_criteria)

    assert len(postings) == 4
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"6001", "6002", "6003", "6004"}


# ---------------------------------------------------------------------------
# 9. HTTP error → returns [] without raising
# ---------------------------------------------------------------------------


async def test_http_error_returns_empty(httpx_mock, adapter, base_criteria):
    # 404 is not retried by _is_retryable
    httpx_mock.add_response(url=_REMOTIVE_URL_RE, status_code=404)

    postings = await adapter.search(base_criteria)

    assert postings == []
