"""Fixture-based tests for the Greenhouse adapter. Never hits live endpoints."""

import json
import re
from pathlib import Path

import pytest

from backend.adapters.greenhouse import GreenhouseAdapter
from backend.config import settings
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Match the boards API endpoint regardless of query-string parameters.
_GREENHOUSE_URL_RE = re.compile(r"https://boards-api\.greenhouse\.io/v1/boards/acme/jobs")


def _load_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "greenhouse_response.json").read_text())


@pytest.fixture
def adapter() -> GreenhouseAdapter:
    return GreenhouseAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="")


# ---------------------------------------------------------------------------
# 1. Happy-path: normalized postings returned
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria, monkeypatch):
    monkeypatch.setattr(settings, "greenhouse_companies", "acme")

    httpx_mock.add_response(
        url=_GREENHOUSE_URL_RE,
        json=_load_fixture(),
    )

    postings = await adapter.search(base_criteria)

    assert len(postings) == 3

    sources = {p.source for p in postings}
    assert sources == {"greenhouse"}

    titles = [p.title for p in postings]
    assert "Senior Software Engineer" in titles
    assert "Product Manager" in titles
    assert "Backend Engineer" in titles

    urls = [p.url for p in postings]
    assert "https://boards.greenhouse.io/acme/jobs/4001" in urls

    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"4001", "4002", "4003"}


# ---------------------------------------------------------------------------
# 2. Remote-only filter: only "Remote" and "Remote - US" postings survive
# ---------------------------------------------------------------------------


async def test_remote_only_filter(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "greenhouse_companies", "acme")

    httpx_mock.add_response(
        url=_GREENHOUSE_URL_RE,
        json=_load_fixture(),
    )

    criteria = SearchCriteria(query="", remote_only=True)
    postings = await adapter.search(criteria)

    assert len(postings) == 2
    for posting in postings:
        assert posting.remote_status == RemoteStatus.remote

    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"4001", "4003"}


# ---------------------------------------------------------------------------
# 3. Query filter: only postings matching "python" are returned
# ---------------------------------------------------------------------------


async def test_query_filter(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "greenhouse_companies", "acme")

    httpx_mock.add_response(
        url=_GREENHOUSE_URL_RE,
        json=_load_fixture(),
    )

    criteria = SearchCriteria(query="python")
    postings = await adapter.search(criteria)

    # Jobs 4001 (Python and FastAPI) and 4003 (Go or Python) match; 4002 does not.
    assert len(postings) == 2
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"4001", "4003"}


# ---------------------------------------------------------------------------
# 4. HTML is stripped from the description field
# ---------------------------------------------------------------------------


async def test_html_stripped_from_description(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "greenhouse_companies", "acme")

    httpx_mock.add_response(
        url=_GREENHOUSE_URL_RE,
        json=_load_fixture(),
    )

    postings = await adapter.search(SearchCriteria(query=""))

    by_id = {p.source_job_id: p for p in postings}
    desc = by_id["4001"].description

    # Text content must be present
    assert "Senior Software Engineer" in desc
    # HTML tags must be absent
    assert "<p>" not in desc
    assert "<strong>" not in desc


# ---------------------------------------------------------------------------
# 5. No slugs configured → returns [] without making any HTTP call
# ---------------------------------------------------------------------------


async def test_no_slugs_returns_empty(adapter, monkeypatch):
    monkeypatch.setattr(settings, "greenhouse_companies", "")

    postings = await adapter.search(SearchCriteria(query="engineer"))

    assert postings == []


# ---------------------------------------------------------------------------
# 6. Malformed item (missing id/absolute_url) is skipped; valid items returned
# ---------------------------------------------------------------------------


async def test_malformed_item_skipped(httpx_mock, adapter, monkeypatch):
    monkeypatch.setattr(settings, "greenhouse_companies", "acme")

    fixture = _load_fixture()
    # Insert a malformed item at the front (missing required "id" and "absolute_url")
    malformed = {
        "title": "Ghost Job",
        "location": {"name": "Remote"},
        "content": "<p>No id here.</p>",
        "updated_at": "2024-05-04T10:00:00.000Z",
    }
    fixture["jobs"].insert(0, malformed)

    httpx_mock.add_response(
        url=_GREENHOUSE_URL_RE,
        json=fixture,
    )

    postings = await adapter.search(SearchCriteria(query=""))

    # The three valid items must still be returned; the malformed one is skipped.
    assert len(postings) == 3
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {"4001", "4002", "4003"}
