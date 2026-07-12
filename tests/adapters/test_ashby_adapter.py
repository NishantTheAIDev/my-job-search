"""Fixture-based tests for the Ashby adapter. Never hits live endpoints."""

import json
import re
from pathlib import Path

import pytest

from backend.adapters.ashby import AshbyAdapter
from backend.config import settings
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_ASHBY_URL_RE = re.compile(r"https://api\.ashbyhq\.com/posting-api/job-board/acme")


def _load_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "ashby_response.json").read_text())


@pytest.fixture
def adapter() -> AshbyAdapter:
    return AshbyAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="")


# ---------------------------------------------------------------------------
# 1. Happy-path: listed postings normalized; unlisted skipped
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(settings, "ashby_companies", "acme")
    httpx_mock.add_response(url=_ASHBY_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)

    # 3 listed jobs; the unlisted one is filtered out
    assert len(postings) == 3
    assert {p.source for p in postings} == {"ashby"}
    ids = {p.source_job_id for p in postings}
    assert ids == {"job-remote-1", "job-onsite-2", "job-hybrid-3"}
    assert "job-unlisted-4" not in ids

    by_id = {p.source_job_id: p for p in postings}
    assert by_id["job-remote-1"].url == "https://jobs.ashbyhq.com/acme/job-remote-1"
    assert by_id["job-remote-1"].company == "acme"


# ---------------------------------------------------------------------------
# 2. workplaceType maps to RemoteStatus
# ---------------------------------------------------------------------------


async def test_workplace_type_mapping(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(settings, "ashby_companies", "acme")
    httpx_mock.add_response(url=_ASHBY_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["job-remote-1"].remote_status == RemoteStatus.remote
    assert by_id["job-onsite-2"].remote_status == RemoteStatus.onsite
    assert by_id["job-hybrid-3"].remote_status == RemoteStatus.hybrid


# ---------------------------------------------------------------------------
# 3. remote_only keeps only remote postings
# ---------------------------------------------------------------------------


async def test_remote_only_filter(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "ashby_companies", "acme")
    httpx_mock.add_response(url=_ASHBY_URL_RE, json=_load_fixture())

    postings = await adapter.search(SearchCriteria(query="", remote_only=True))

    assert len(postings) == 1
    assert postings[0].source_job_id == "job-remote-1"


# ---------------------------------------------------------------------------
# 4. Query filter uses whole-word matching
# ---------------------------------------------------------------------------


async def test_query_filter(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "ashby_companies", "acme")
    httpx_mock.add_response(url=_ASHBY_URL_RE, json=_load_fixture())

    postings = await adapter.search(SearchCriteria(query="python"))

    assert len(postings) == 1
    assert postings[0].source_job_id == "job-remote-1"


# ---------------------------------------------------------------------------
# 5. descriptionPlain preferred; HTML stripped as fallback
# ---------------------------------------------------------------------------


async def test_description_html_fallback(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(settings, "ashby_companies", "acme")
    httpx_mock.add_response(url=_ASHBY_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    # job-hybrid-3 has empty descriptionPlain → HTML stripped
    assert "<p>" not in by_id["job-hybrid-3"].description
    assert "Kubernetes" in by_id["job-hybrid-3"].description


# ---------------------------------------------------------------------------
# 6. Location filter (only when not remote-only)
# ---------------------------------------------------------------------------


async def test_location_filter(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "ashby_companies", "acme")
    httpx_mock.add_response(url=_ASHBY_URL_RE, json=_load_fixture())

    postings = await adapter.search(SearchCriteria(query="", location="India"))

    assert len(postings) == 1
    assert postings[0].source_job_id == "job-onsite-2"


# ---------------------------------------------------------------------------
# 7. publishedAt parsed to YYYY-MM-DD
# ---------------------------------------------------------------------------


async def test_published_date_parsed(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(settings, "ashby_companies", "acme")
    httpx_mock.add_response(url=_ASHBY_URL_RE, json=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["job-remote-1"].posted_date == "2024-05-01"


# ---------------------------------------------------------------------------
# 8. No slugs configured → returns [] without any HTTP call
# ---------------------------------------------------------------------------


async def test_no_slugs_returns_empty(adapter, monkeypatch):
    monkeypatch.setattr(settings, "ashby_companies", "")

    postings = await adapter.search(SearchCriteria(query="engineer"))

    assert postings == []
