"""Fixture-based tests for the Arbeitnow adapter. Never hits live endpoints."""

import json
import re
from pathlib import Path

import pytest

import backend.adapters.arbeitnow as arbeitnow_module
from backend.adapters.arbeitnow import ArbeitnowAdapter
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"
_ARBEITNOW_URL_RE = re.compile(r"https://www\.arbeitnow\.com/api/job-board-api")


def _load_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "arbeitnow_response.json").read_text())


@pytest.fixture(autouse=True)
def single_page(monkeypatch):
    """Run each test with one page to avoid needing multiple mock responses."""
    monkeypatch.setattr(arbeitnow_module, "_NUM_PAGES", 1)


@pytest.fixture
def adapter() -> ArbeitnowAdapter:
    return ArbeitnowAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="")


# ---------------------------------------------------------------------------
# 1. Happy path: 3 postings, correct source_job_ids and field mapping
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert len(postings) == 3
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {
        "senior-python-engineer-techcorp-001",
        "frontend-developer-acme-002",
        "data-engineer-dataflow-003",
    }

    by_id = {p.source_job_id: p for p in postings}
    assert by_id["senior-python-engineer-techcorp-001"].title == "Senior Python Engineer"
    assert by_id["senior-python-engineer-techcorp-001"].company == "TechCorp"
    assert by_id["senior-python-engineer-techcorp-001"].url == (
        "https://www.arbeitnow.com/jobs/techcorp/senior-python-engineer-001"
    )


# ---------------------------------------------------------------------------
# 2. All postings have source="arbeitnow"
# ---------------------------------------------------------------------------


async def test_all_postings_have_correct_source(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert all(p.source == "arbeitnow" for p in postings)


# ---------------------------------------------------------------------------
# 3. remote_only=True: only the remote posting is returned
# ---------------------------------------------------------------------------


async def test_remote_only_filter(httpx_mock, adapter):
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="", remote_only=True)
    postings = await adapter.search(criteria)

    assert len(postings) == 1
    assert postings[0].source_job_id == "senior-python-engineer-techcorp-001"
    assert postings[0].remote_status == RemoteStatus.remote


# ---------------------------------------------------------------------------
# 4. Remote status: remote==True → remote; remote==False → unspecified
# ---------------------------------------------------------------------------


async def test_remote_status_mapped(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["senior-python-engineer-techcorp-001"].remote_status == RemoteStatus.remote
    assert by_id["frontend-developer-acme-002"].remote_status == RemoteStatus.unspecified
    assert by_id["data-engineer-dataflow-003"].remote_status == RemoteStatus.unspecified


# ---------------------------------------------------------------------------
# 5. Location filter (non-remote-only): narrows by posting location string
# ---------------------------------------------------------------------------


async def test_location_filter(httpx_mock, adapter):
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="", location="Germany")
    postings = await adapter.search(criteria)

    # "Berlin, Germany" and "Munich, Germany" match; "Remote" does not
    assert len(postings) == 2
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"frontend-developer-acme-002", "data-engineer-dataflow-003"}


# ---------------------------------------------------------------------------
# 6. Query filter: whole-word match on title + description
# ---------------------------------------------------------------------------


async def test_query_filter(httpx_mock, adapter):
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="python")
    postings = await adapter.search(criteria)

    # job 001 (title) and 003 (description "Python and Spark") both contain "python"
    assert len(postings) == 2
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"senior-python-engineer-techcorp-001", "data-engineer-dataflow-003"}


# ---------------------------------------------------------------------------
# 7. Compensation: salary string preserved, null mapped to None
# ---------------------------------------------------------------------------


async def test_compensation_mapped(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["senior-python-engineer-techcorp-001"].compensation == "$120,000 - $160,000"
    assert by_id["frontend-developer-acme-002"].compensation is None
    assert by_id["data-engineer-dataflow-003"].compensation == "€60,000 - €80,000"


# ---------------------------------------------------------------------------
# 8. Date parsed from Unix timestamp
# ---------------------------------------------------------------------------


async def test_date_parsed_from_unix_timestamp(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["senior-python-engineer-techcorp-001"].posted_date == "2024-05-01"
    assert by_id["frontend-developer-acme-002"].posted_date == "2024-04-30"
    assert by_id["data-engineer-dataflow-003"].posted_date == "2024-04-29"


# ---------------------------------------------------------------------------
# 9. HTML stripped from description
# ---------------------------------------------------------------------------


async def test_html_stripped_from_description(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}
    desc = by_id["senior-python-engineer-techcorp-001"].description

    assert "Senior Python Engineer" in desc
    assert "FastAPI" in desc
    assert "<p>" not in desc
    assert "<strong>" not in desc


# ---------------------------------------------------------------------------
# 10. Malformed item (missing required key) is skipped; valid items returned
# ---------------------------------------------------------------------------


async def test_malformed_item_skipped(httpx_mock, adapter, base_criteria):
    fixture = _load_fixture()
    malformed = {
        # "slug" intentionally absent → KeyError in _normalize
        "title": "Ghost Job",
        "company_name": "Ghost Corp",
        "remote": False,
        "url": "https://example.com",
        "description": "<p>Ghost</p>",
        "created_at": 1714521600,
    }
    fixture["data"].insert(0, malformed)
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, json=fixture)

    postings = await adapter.search(base_criteria)

    assert len(postings) == 3
    source_ids = {p.source_job_id for p in postings}
    assert "senior-python-engineer-techcorp-001" in source_ids


# ---------------------------------------------------------------------------
# 11. HTTP error → returns [] without raising
# ---------------------------------------------------------------------------


async def test_http_error_returns_empty(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, status_code=404)

    postings = await adapter.search(base_criteria)

    assert postings == []


# ---------------------------------------------------------------------------
# 12. Multi-page: results from all pages are combined
# ---------------------------------------------------------------------------


async def test_multi_page_results_combined(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(arbeitnow_module, "_NUM_PAGES", 2)

    page1 = _load_fixture()
    page2 = {
        "data": [
            {
                "slug": "devops-engineer-cloudco-004",
                "title": "DevOps Engineer",
                "company_name": "CloudCo",
                "location": "Remote",
                "remote": True,
                "tags": ["devops", "kubernetes"],
                "url": "https://www.arbeitnow.com/jobs/cloudco/devops-004",
                "description": "<p>DevOps role with Kubernetes.</p>",
                "salary": None,
                "created_at": 1714262400,
            }
        ],
        "links": {},
        "meta": {"current_page": 2, "last_page": 50},
    }
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, json=page1)
    httpx_mock.add_response(url=_ARBEITNOW_URL_RE, json=page2)

    postings = await adapter.search(SearchCriteria(query=""))

    assert len(postings) == 4
    source_ids = {p.source_job_id for p in postings}
    assert "devops-engineer-cloudco-004" in source_ids
