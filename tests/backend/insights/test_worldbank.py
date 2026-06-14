"""Fixture-based tests for the World Bank macro indicators client."""

import json
import re
from pathlib import Path

import pytest

from backend.config import settings
from backend.services.insights.worldbank import get_macro

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_WB_URL_RE = re.compile(r"https://api\.worldbank\.org/v2/country/\w+/indicator/\w+")


def _load(name: str) -> list:
    return json.loads((FIXTURES_DIR / name).read_text())


# ---------------------------------------------------------------------------
# Happy path: parses fixture to year/value points
# ---------------------------------------------------------------------------


async def test_get_macro_parses_unemployment_fixture(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "worldbank_enabled", True)

    fixture = _load("worldbank_unemployment.json")
    # Both unemployment and employment calls go to the same pattern — serve fixture twice
    httpx_mock.add_response(url=_WB_URL_RE, json=fixture)
    httpx_mock.add_response(url=_WB_URL_RE, json=fixture)

    result = await get_macro("us")

    assert "unemployment" in result
    assert "employment" in result
    unemployment = result["unemployment"]
    assert len(unemployment) == 5
    # Should be sorted ascending by year
    years = [p["year"] for p in unemployment]
    assert years == sorted(years)
    assert unemployment[0]["year"] == 2019
    assert unemployment[0]["value"] == pytest.approx(3.7)
    # Last entry should be 2023
    assert unemployment[-1]["year"] == 2023


async def test_get_macro_empty_records_returns_empty_lists(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "worldbank_enabled", True)

    empty = _load("worldbank_empty.json")
    httpx_mock.add_response(url=_WB_URL_RE, json=empty)
    httpx_mock.add_response(url=_WB_URL_RE, json=empty)

    result = await get_macro("us")

    assert result["unemployment"] == []
    assert result["employment"] == []


async def test_get_macro_disabled_returns_empty(monkeypatch):
    """When worldbank_enabled=False, no HTTP calls are made and empty lists are returned."""
    monkeypatch.setattr(settings, "worldbank_enabled", False)

    result = await get_macro("us")

    assert result == {"unemployment": [], "employment": []}


async def test_get_macro_skips_null_values(httpx_mock, monkeypatch):
    """Records with null value should be filtered out."""
    monkeypatch.setattr(settings, "worldbank_enabled", True)

    data_with_nulls = [
        {"page": 1, "pages": 1, "per_page": 10, "total": 3},
        [
            {"date": "2023", "value": 4.1},
            {"date": "2022", "value": None},
            {"date": "2021", "value": 5.0},
        ],
    ]
    httpx_mock.add_response(url=_WB_URL_RE, json=data_with_nulls)
    httpx_mock.add_response(url=_WB_URL_RE, json=data_with_nulls)

    result = await get_macro("us")

    # Only the 2 non-null records should appear
    assert len(result["unemployment"]) == 2
    years = [p["year"] for p in result["unemployment"]]
    assert 2022 not in years


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_get_macro_http_error_returns_empty_lists(httpx_mock, monkeypatch):
    """A network error for one indicator should return empty list for that indicator."""
    monkeypatch.setattr(settings, "worldbank_enabled", True)

    for _ in range(10):
        httpx_mock.add_response(url=_WB_URL_RE, status_code=500)

    result = await get_macro("us")

    assert result["unemployment"] == []
    assert result["employment"] == []


async def test_get_macro_uses_correct_wb_country_for_india(httpx_mock, monkeypatch):
    """region='in' maps to World Bank country code 'IN'."""
    monkeypatch.setattr(settings, "worldbank_enabled", True)

    india_url_re = re.compile(r"https://api\.worldbank\.org/v2/country/IN/indicator/\w+")
    fixture = _load("worldbank_unemployment.json")
    httpx_mock.add_response(url=india_url_re, json=fixture)
    httpx_mock.add_response(url=india_url_re, json=fixture)

    result = await get_macro("in")

    assert "unemployment" in result


async def test_get_macro_world_uses_wld_code(httpx_mock, monkeypatch):
    """region='world' maps to World Bank country code 'WLD'."""
    monkeypatch.setattr(settings, "worldbank_enabled", True)

    world_url_re = re.compile(r"https://api\.worldbank\.org/v2/country/WLD/indicator/\w+")
    fixture = _load("worldbank_unemployment.json")
    httpx_mock.add_response(url=world_url_re, json=fixture)
    httpx_mock.add_response(url=world_url_re, json=fixture)

    result = await get_macro("world")

    assert "unemployment" in result
