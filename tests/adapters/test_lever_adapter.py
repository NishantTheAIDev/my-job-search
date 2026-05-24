"""Fixture-based tests for the Lever adapter. Never hits live endpoints."""
import json
import re
from pathlib import Path

import pytest

from backend.adapters.lever import LeverAdapter
from backend.config import settings
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Match the Lever v0 postings endpoint regardless of query-string parameters.
_LEVER_URL_RE = re.compile(r"https://api\.lever\.co/v0/postings/acme")


def _load_fixture() -> list:
    return json.loads((FIXTURES_DIR / "lever_response.json").read_text())


@pytest.fixture
def adapter() -> LeverAdapter:
    return LeverAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="")


# ---------------------------------------------------------------------------
# 1. Happy-path: normalized postings returned
# ---------------------------------------------------------------------------

async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(settings, "lever_companies", "acme")

    httpx_mock.add_response(
        url=_LEVER_URL_RE,
        json=_load_fixture(),
    )

    postings = await adapter.search(base_criteria)

    assert len(postings) == 3

    sources = {p.source for p in postings}
    assert sources == {"lever"}

    titles = [p.title for p in postings]
    assert "Senior Software Engineer" in titles
    assert "Data Scientist" in titles
    assert "DevOps Engineer" in titles

    urls = [p.url for p in postings]
    assert "https://jobs.lever.co/acme/abc-111" in urls

    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"abc-111", "abc-222", "abc-333"}


# ---------------------------------------------------------------------------
# 2. Remote-only filter: only the "remote" workplaceType posting survives
# ---------------------------------------------------------------------------

async def test_remote_only_filter(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "lever_companies", "acme")

    httpx_mock.add_response(
        url=_LEVER_URL_RE,
        json=_load_fixture(),
    )

    criteria = SearchCriteria(query="", remote_only=True)
    postings = await adapter.search(criteria)

    assert len(postings) == 1
    assert postings[0].source_job_id == "abc-111"
    assert postings[0].remote_status == RemoteStatus.remote


# ---------------------------------------------------------------------------
# 3. workplaceType field maps to RemoteStatus correctly
# ---------------------------------------------------------------------------

async def test_workplace_type_mapping(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "lever_companies", "acme")

    httpx_mock.add_response(
        url=_LEVER_URL_RE,
        json=_load_fixture(),
    )

    postings = await adapter.search(SearchCriteria(query=""))

    by_id = {p.source_job_id: p for p in postings}

    assert by_id["abc-111"].remote_status == RemoteStatus.remote
    assert by_id["abc-222"].remote_status == RemoteStatus.onsite
    assert by_id["abc-333"].remote_status == RemoteStatus.hybrid


# ---------------------------------------------------------------------------
# 4. Query filter: only postings matching "python" are returned
# ---------------------------------------------------------------------------

async def test_query_filter(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "lever_companies", "acme")

    httpx_mock.add_response(
        url=_LEVER_URL_RE,
        json=_load_fixture(),
    )

    criteria = SearchCriteria(query="python")
    postings = await adapter.search(criteria)

    # Only abc-111 (SWE with Python in descriptionPlain) matches.
    assert len(postings) == 1
    assert postings[0].source_job_id == "abc-111"


# ---------------------------------------------------------------------------
# 5. createdAt millisecond timestamp is converted to YYYY-MM-DD
# ---------------------------------------------------------------------------

async def test_ms_timestamp_parsed(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "lever_companies", "acme")

    httpx_mock.add_response(
        url=_LEVER_URL_RE,
        json=_load_fixture(),
    )

    postings = await adapter.search(SearchCriteria(query=""))

    by_id = {p.source_job_id: p for p in postings}

    # 1714521600000 ms = 2024-05-01 UTC
    assert by_id["abc-111"].posted_date == "2024-05-01"
    # 1714435200000 ms = 2024-04-30 UTC
    assert by_id["abc-222"].posted_date == "2024-04-30"
    # 1714608000000 ms = 2024-05-02 UTC
    assert by_id["abc-333"].posted_date == "2024-05-02"


# ---------------------------------------------------------------------------
# 6. No slugs configured → returns [] without making any HTTP call
# ---------------------------------------------------------------------------

async def test_no_slugs_returns_empty(adapter, monkeypatch):
    monkeypatch.setattr(settings, "lever_companies", "")

    postings = await adapter.search(SearchCriteria(query="engineer"))

    assert postings == []


# ---------------------------------------------------------------------------
# 7. descriptionPlain preferred over HTML description; HTML stripped as fallback
# ---------------------------------------------------------------------------

async def test_descriptionPlain_preferred_over_html(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "lever_companies", "acme")

    httpx_mock.add_response(
        url=_LEVER_URL_RE,
        json=_load_fixture(),
    )

    postings = await adapter.search(SearchCriteria(query=""))

    by_id = {p.source_job_id: p for p in postings}

    # abc-111 and abc-222 have descriptionPlain — used as-is (no HTML tags)
    assert "<p>" not in by_id["abc-111"].description
    assert by_id["abc-111"].description == "We are looking for a Senior Software Engineer with Python experience."

    # abc-333 has only HTML description — must be stripped
    assert "<p>" not in by_id["abc-333"].description
    assert "DevOps engineer with Kubernetes experience." in by_id["abc-333"].description
