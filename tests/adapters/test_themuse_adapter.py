"""Fixture-based tests for The Muse adapter. Never hits live endpoints."""

import json
import re
from pathlib import Path

import pytest

import backend.adapters.themuse as themuse_module
from backend.adapters.themuse import TheMuseAdapter
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_THEMUSE_URL_RE = re.compile(r"https://www\.themuse\.com/api/public/jobs")


def _load_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "themuse_response.json").read_text())


@pytest.fixture
def adapter() -> TheMuseAdapter:
    return TheMuseAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="")


# ---------------------------------------------------------------------------
# 1. Happy-path: normalized postings returned
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(themuse_module, "_MAX_PAGES", 1)
    httpx_mock.add_response(url=_THEMUSE_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert len(postings) == 4
    assert all(p.source == "themuse" for p in postings)

    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"5001", "5002", "5003", "5004"}

    titles = [p.title for p in postings]
    assert "Senior AI Engineer" in titles
    assert "ML Engineer" in titles

    by_id = {p.source_job_id: p for p in postings}
    assert by_id["5001"].company == "TechCorp"
    assert by_id["5001"].url == "https://www.themuse.com/jobs/techcorp/senior-ai-engineer"
    assert by_id["5001"].posted_date == "2024-05-01"
    assert by_id["5004"].location == "Flexible / Remote"


# ---------------------------------------------------------------------------
# 2. Remote-only filter: only "Remote" and "Flexible / Remote" postings survive
# ---------------------------------------------------------------------------


async def test_remote_only_filter(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(themuse_module, "_MAX_PAGES", 1)
    httpx_mock.add_response(url=_THEMUSE_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="", remote_only=True)
    postings = await adapter.search(criteria)

    assert len(postings) == 2
    assert all(p.remote_status == RemoteStatus.remote for p in postings)

    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"5001", "5004"}


# ---------------------------------------------------------------------------
# 3. Query filter: "python" matches only the two engineering roles
# ---------------------------------------------------------------------------


async def test_query_filter(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(themuse_module, "_MAX_PAGES", 1)
    httpx_mock.add_response(url=_THEMUSE_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="python")
    postings = await adapter.search(criteria)

    # 5001 (Python in description) and 5003 (Python in description) match.
    # 5002 (marketing) and 5004 (ML, no "python") do not.
    assert len(postings) == 2
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"5001", "5003"}


# ---------------------------------------------------------------------------
# 4. Word-boundary matching: "ai" must not match substrings in unrelated words
# ---------------------------------------------------------------------------


async def test_word_boundary_query(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(themuse_module, "_MAX_PAGES", 1)
    httpx_mock.add_response(url=_THEMUSE_URL_RE, json=_load_fixture())

    criteria = SearchCriteria(query="ai")
    postings = await adapter.search(criteria)

    # 5001 ("AI" in title) and 5004 ("AI" in description) match.
    # 5002 has "available" and "training" — "ai" must NOT match those substrings.
    assert len(postings) == 2
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"5001", "5004"}


# ---------------------------------------------------------------------------
# 5. HTML is stripped from the description field
# ---------------------------------------------------------------------------


async def test_html_stripped_from_description(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(themuse_module, "_MAX_PAGES", 1)
    httpx_mock.add_response(url=_THEMUSE_URL_RE, json=_load_fixture())

    postings = await adapter.search(SearchCriteria(query=""))

    by_id = {p.source_job_id: p for p in postings}
    desc = by_id["5001"].description

    assert "AI" in desc
    assert "Python" in desc
    assert "<p>" not in desc
    assert "<strong>" not in desc
    assert "<em>" not in desc


# ---------------------------------------------------------------------------
# 6. No API key configured → still fetches (The Muse is keyless by default)
# ---------------------------------------------------------------------------


async def test_no_api_key_still_fetches(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(themuse_module, "_MAX_PAGES", 1)
    monkeypatch.setattr("backend.adapters.themuse.settings.themuse_api_key", "")
    httpx_mock.add_response(url=_THEMUSE_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert len(postings) == 4  # all four returned; no early exit


# ---------------------------------------------------------------------------
# 7. Malformed item (missing required fields) is skipped; valid items returned
# ---------------------------------------------------------------------------


async def test_malformed_item_skipped(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(themuse_module, "_MAX_PAGES", 1)

    fixture = _load_fixture()
    malformed = {
        "name": "Ghost Job",
        "contents": "<p>No id or refs here.</p>",
        "company": {"name": "Nobody"},
        "locations": [{"name": "Remote"}],
        "publication_date": "2024-05-05T00:00:00Z",
        # "id" and "refs" intentionally absent
    }
    fixture["results"].insert(0, malformed)

    httpx_mock.add_response(url=_THEMUSE_URL_RE, json=fixture)

    postings = await adapter.search(SearchCriteria(query=""))

    assert len(postings) == 4
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"5001", "5002", "5003", "5004"}


# ---------------------------------------------------------------------------
# 8. All pages fail → returns [] without raising
# ---------------------------------------------------------------------------


async def test_all_pages_fail_returns_empty(httpx_mock, adapter, base_criteria, monkeypatch):
    # 404 is not retried by _is_retryable, so one mock response per page is enough.
    monkeypatch.setattr(themuse_module, "_MAX_PAGES", 1)
    httpx_mock.add_response(url=_THEMUSE_URL_RE, status_code=404)

    postings = await adapter.search(base_criteria)

    assert postings == []


# ---------------------------------------------------------------------------
# 9. Multi-page: results from all pages are combined and filtered
# ---------------------------------------------------------------------------


async def test_multi_page_results_combined(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(themuse_module, "_MAX_PAGES", 2)

    page0 = _load_fixture()
    # Page 1 has one extra python job
    page1 = {
        "results": [
            {
                "id": 5099,
                "name": "Python Developer",
                "contents": "<p>Python and Django.</p>",
                "refs": {"landing_page": "https://www.themuse.com/jobs/co/python-dev"},
                "company": {"id": 9, "name": "AnotherCo", "short_name": "anotherco"},
                "locations": [{"name": "Austin, TX"}],
                "levels": [{"name": "Mid Level", "short_name": "mid"}],
                "categories": [{"name": "Software Engineer"}],
                "publication_date": "2024-05-05T00:00:00Z",
            }
        ],
        "page": 1,
        "page_count": 2,
        "total": 5,
    }
    httpx_mock.add_response(url=_THEMUSE_URL_RE, json=page0)
    httpx_mock.add_response(url=_THEMUSE_URL_RE, json=page1)

    criteria = SearchCriteria(query="python")
    postings = await adapter.search(criteria)

    # 5001, 5003 from page 0 plus 5099 from page 1
    assert len(postings) == 3
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"5001", "5003", "5099"}
