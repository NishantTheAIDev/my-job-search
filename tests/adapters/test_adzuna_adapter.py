"""Fixture-based tests for the Adzuna adapter. Never hits live endpoints."""

import json
import re
from pathlib import Path

import pytest

from backend.adapters.adzuna import AdzunaAdapter
from backend.config import settings
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Match the search endpoint regardless of query-string parameters.
_ADZUNA_URL_RE = re.compile(r"https://api\.adzuna\.com/v1/api/jobs/us/search/\d+")


def _load_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "adzuna_response.json").read_text())


@pytest.fixture
def adapter() -> AdzunaAdapter:
    return AdzunaAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="software engineer", location="New York")


# ---------------------------------------------------------------------------
# 1. Happy-path: normalized postings returned
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    httpx_mock.add_response(
        url=_ADZUNA_URL_RE,
        json=_load_fixture(),
    )

    postings = await adapter.search(base_criteria)

    assert len(postings) == 3

    sources = {p.source for p in postings}
    assert sources == {"adzuna"}

    titles = [p.title for p in postings]
    assert "Senior Software Engineer" in titles
    assert "Backend Engineer" in titles
    assert "Python Developer" in titles

    companies = [p.company for p in postings]
    assert "Acme Corp" in companies
    assert "TechStartup" in companies

    urls = [p.url for p in postings]
    assert "https://www.adzuna.com/jobs/1001" in urls


# ---------------------------------------------------------------------------
# 2. Remote-only post-filter: only the "Remote" location posting survives
# ---------------------------------------------------------------------------


async def test_remote_only_filter(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    httpx_mock.add_response(
        url=_ADZUNA_URL_RE,
        json=_load_fixture(),
    )

    criteria = SearchCriteria(query="software engineer", remote_only=True)
    postings = await adapter.search(criteria)

    assert len(postings) == 1
    assert postings[0].source_job_id == "1001"
    assert postings[0].remote_status == RemoteStatus.remote


# ---------------------------------------------------------------------------
# 3. Compensation formatting
# ---------------------------------------------------------------------------


async def test_compensation_formatting(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    httpx_mock.add_response(
        url=_ADZUNA_URL_RE,
        json=_load_fixture(),
    )

    postings = await adapter.search(base_criteria)

    by_id = {p.source_job_id: p for p in postings}

    # result 1001 has both salary_min and salary_max
    assert by_id["1001"].compensation == "$130,000–$170,000 / year"

    # result 1003 has no salary fields at all
    assert by_id["1003"].compensation is None


# ---------------------------------------------------------------------------
# 4. Missing credentials → empty list, no HTTP call made
# ---------------------------------------------------------------------------


async def test_missing_credentials_returns_empty(adapter, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "")

    postings = await adapter.search(SearchCriteria(query="engineer"))

    assert postings == []


# ---------------------------------------------------------------------------
# 5. Malformed item is skipped; valid items are still returned
# ---------------------------------------------------------------------------


async def test_malformed_item_skipped(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    fixture = _load_fixture()
    # Insert a malformed item (missing required "id" and "title") at the front
    malformed = {
        "company": {"display_name": "Ghost Co"},
        "location": {"display_name": "Chicago, IL"},
        "redirect_url": "https://www.adzuna.com/jobs/9999",
        "description": "No id here.",
        "created": "2024-05-04T10:00:00Z",
    }
    fixture["results"].insert(0, malformed)

    httpx_mock.add_response(
        url=_ADZUNA_URL_RE,
        json=fixture,
    )

    postings = await adapter.search(base_criteria)

    # The three valid items from the fixture should still be returned
    assert len(postings) == 3
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"1001", "1002", "1003"}
