"""Fixture-based tests for the We Work Remotely adapter. Never hits live endpoints."""

import re
from pathlib import Path

import pytest

from backend.adapters.weworkremotely import WeWorkRemotelyAdapter
from backend.models.job_posting import RemoteStatus, SearchCriteria

FIXTURES_DIR = Path(__file__).parent / "fixtures"
_WWR_URL_RE = re.compile(r"https://weworkremotely\.com/remote-jobs\.rss")


def _load_fixture() -> str:
    return (FIXTURES_DIR / "weworkremotely_response.xml").read_text()


@pytest.fixture
def adapter() -> WeWorkRemotelyAdapter:
    return WeWorkRemotelyAdapter()


@pytest.fixture
def base_criteria() -> SearchCriteria:
    return SearchCriteria(query="")


# ---------------------------------------------------------------------------
# 1. Happy path: 3 postings, correct source_job_ids and field mapping
# ---------------------------------------------------------------------------


async def test_search_returns_normalized_postings(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_WWR_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert len(postings) == 3
    source_ids = {p.source_job_id for p in postings}
    assert source_ids == {
        "12345-senior-python-engineer",
        "12346-frontend-developer",
        "12347-ml-engineer",
    }

    by_id = {p.source_job_id: p for p in postings}
    assert by_id["12345-senior-python-engineer"].title == "Senior Python Engineer"
    assert by_id["12345-senior-python-engineer"].company == "TechCorp"
    assert by_id["12345-senior-python-engineer"].url == (
        "https://weworkremotely.com/remote-jobs/view/12345-senior-python-engineer"
    )


# ---------------------------------------------------------------------------
# 2. All postings have source="weworkremotely"
# ---------------------------------------------------------------------------


async def test_all_postings_have_correct_source(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_WWR_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert all(p.source == "weworkremotely" for p in postings)


# ---------------------------------------------------------------------------
# 3. All postings have remote_status=remote (WWR is remote-only)
# ---------------------------------------------------------------------------


async def test_all_postings_are_remote(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_WWR_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)

    assert all(p.remote_status == RemoteStatus.remote for p in postings)


# ---------------------------------------------------------------------------
# 4. remote_only=True: all postings returned (all are already remote)
# ---------------------------------------------------------------------------


async def test_remote_only_returns_all(httpx_mock, adapter):
    httpx_mock.add_response(url=_WWR_URL_RE, text=_load_fixture())

    criteria = SearchCriteria(query="", remote_only=True)
    postings = await adapter.search(criteria)

    assert len(postings) == 3


# ---------------------------------------------------------------------------
# 5. Title/company split: "Company: Job Title" parsed into separate fields
# ---------------------------------------------------------------------------


async def test_title_and_company_split(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_WWR_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["12345-senior-python-engineer"].title == "Senior Python Engineer"
    assert by_id["12345-senior-python-engineer"].company == "TechCorp"
    assert by_id["12346-frontend-developer"].title == "Frontend Developer"
    assert by_id["12346-frontend-developer"].company == "Acme Corp"


# ---------------------------------------------------------------------------
# 6. Query filter: whole-word client-side matching on title + description
# ---------------------------------------------------------------------------


async def test_query_filter(httpx_mock, adapter):
    httpx_mock.add_response(url=_WWR_URL_RE, text=_load_fixture())

    criteria = SearchCriteria(query="python")
    postings = await adapter.search(criteria)

    # Only job 12345 has "Python" in its description
    assert len(postings) == 1
    assert postings[0].source_job_id == "12345-senior-python-engineer"


# ---------------------------------------------------------------------------
# 7. Date parsed from RFC 2822 format
# ---------------------------------------------------------------------------


async def test_date_parsed_from_rfc2822(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_WWR_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}

    assert by_id["12345-senior-python-engineer"].posted_date == "2024-05-01"
    assert by_id["12346-frontend-developer"].posted_date == "2024-05-02"
    assert by_id["12347-ml-engineer"].posted_date == "2024-04-28"


# ---------------------------------------------------------------------------
# 8. HTML stripped from description
# ---------------------------------------------------------------------------


async def test_html_stripped_from_description(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_WWR_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)
    by_id = {p.source_job_id: p for p in postings}
    desc = by_id["12345-senior-python-engineer"].description

    assert "Senior Python Engineer" in desc
    assert "<p>" not in desc
    assert "<strong>" not in desc


# ---------------------------------------------------------------------------
# 9. source_job_id extracted as last URL path segment
# ---------------------------------------------------------------------------


async def test_source_job_id_from_url_path(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_WWR_URL_RE, text=_load_fixture())

    postings = await adapter.search(base_criteria)

    # Confirm each ID is the slug segment, not the full URL
    for p in postings:
        assert p.source_job_id.startswith("1234")
        assert "weworkremotely.com" not in p.source_job_id


# ---------------------------------------------------------------------------
# 10. Invalid XML → returns [] without raising
# ---------------------------------------------------------------------------


async def test_invalid_xml_returns_empty(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_WWR_URL_RE, text="<<< not valid xml >>>")

    postings = await adapter.search(base_criteria)

    assert postings == []


# ---------------------------------------------------------------------------
# 11. HTTP error → returns [] without raising
# ---------------------------------------------------------------------------


async def test_http_error_returns_empty(httpx_mock, adapter, base_criteria):
    httpx_mock.add_response(url=_WWR_URL_RE, status_code=404)

    postings = await adapter.search(base_criteria)

    assert postings == []


# ---------------------------------------------------------------------------
# 12. Title without ': ' separator — full string used as title, company is None
# ---------------------------------------------------------------------------


async def test_title_without_separator(httpx_mock, adapter):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title><![CDATA[Senior Engineer (no company prefix)]]></title>
      <link>https://weworkremotely.com/remote-jobs/view/99999-senior-engineer</link>
      <pubDate>Wed, 01 May 2024 10:00:00 +0000</pubDate>
      <description><![CDATA[<p>A role with no company prefix in the title.</p>]]></description>
    </item>
  </channel>
</rss>"""
    httpx_mock.add_response(url=_WWR_URL_RE, text=xml)

    postings = await adapter.search(SearchCriteria(query=""))

    assert len(postings) == 1
    assert postings[0].title == "Senior Engineer (no company prefix)"
    assert postings[0].company is None
