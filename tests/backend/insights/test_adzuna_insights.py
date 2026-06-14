"""Fixture-based tests for the Adzuna insights client. Never hits live endpoints."""

import json
import re
from pathlib import Path

import pytest

from backend.config import settings
from backend.services.insights.adzuna_insights import (
    _compute_median,
    hottest_fields,
    salary_histogram,
    salary_history,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_HISTOGRAM_URL_RE = re.compile(r"https://api\.adzuna\.com/v1/api/jobs/\w+/histogram")
_HISTORY_URL_RE = re.compile(r"https://api\.adzuna\.com/v1/api/jobs/\w+/history")
_CATEGORIES_URL_RE = re.compile(r"https://api\.adzuna\.com/v1/api/jobs/\w+/categories")
_SEARCH_URL_RE = re.compile(r"https://api\.adzuna\.com/v1/api/jobs/\w+/search/\d+")


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


# ---------------------------------------------------------------------------
# _compute_median unit tests (pure function, no HTTP)
# ---------------------------------------------------------------------------


def test_compute_median_typical_histogram():
    # Buckets: 20000×5, 40000×20, 60000×50, 80000×40, 100000×25, 120000×10
    # total = 150; midpoint = 75; cumulative crosses at 60000 (5+20+50=75)
    histogram = {
        "20000": "5",
        "40000": "20",
        "60000": "50",
        "80000": "40",
        "100000": "25",
        "120000": "10",
    }
    median, total = _compute_median(histogram)
    assert total == 150
    assert median == 60000.0


def test_compute_median_single_bucket():
    median, total = _compute_median({"50000": "100"})
    assert median == 50000.0
    assert total == 100


def test_compute_median_two_equal_buckets():
    # 10000×10, 20000×10 — total=20, midpoint=10; cumulative hits 10 at first bucket
    median, total = _compute_median({"10000": "10", "20000": "10"})
    assert total == 20
    assert median == 10000.0


def test_compute_median_empty_histogram():
    median, total = _compute_median({})
    assert median is None
    assert total == 0


def test_compute_median_skips_non_numeric_keys():
    # "bad" key should be silently dropped; only numeric keys count
    histogram = {"not_a_number": "5", "50000": "10", "bad": "3"}
    median, total = _compute_median(histogram)
    assert total == 10
    assert median == 50000.0


def test_compute_median_all_non_numeric_returns_none():
    median, total = _compute_median({"foo": "bar", "baz": "qux"})
    assert median is None
    assert total == 0


# ---------------------------------------------------------------------------
# salary_histogram: happy path with fixture
# ---------------------------------------------------------------------------


async def test_salary_histogram_returns_median_from_fixture(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    httpx_mock.add_response(url=_HISTOGRAM_URL_RE, json=_load("adzuna_histogram.json"))

    median, sample_size = await salary_histogram("Software Engineer", "us")

    # Fixture: 20000×5, 40000×20, 60000×50, 80000×40, 100000×25, 120000×10 → total=150
    assert sample_size == 150
    assert median == 60000.0


async def test_salary_histogram_empty_histogram_returns_none(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    httpx_mock.add_response(url=_HISTOGRAM_URL_RE, json={"histogram": {}})

    median, sample_size = await salary_histogram("Software Engineer", "us")

    assert median is None
    assert sample_size == 0


async def test_salary_histogram_missing_histogram_key_returns_none(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    httpx_mock.add_response(url=_HISTOGRAM_URL_RE, json={})

    median, sample_size = await salary_histogram("Software Engineer", "us")

    assert median is None
    assert sample_size == 0


async def test_salary_histogram_missing_creds_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "")

    median, sample_size = await salary_histogram("Software Engineer", "us")

    assert median is None
    assert sample_size == 0


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_salary_histogram_http_error_returns_none(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    # tenacity may retry on 5xx; register enough responses and allow extras
    for _ in range(5):
        httpx_mock.add_response(url=_HISTOGRAM_URL_RE, status_code=500)

    median, sample_size = await salary_histogram("Software Engineer", "us")

    assert median is None
    assert sample_size == 0


# ---------------------------------------------------------------------------
# salary_history
# ---------------------------------------------------------------------------


async def test_salary_history_parses_fixture(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    httpx_mock.add_response(url=_HISTORY_URL_RE, json=_load("adzuna_history.json"))

    history = await salary_history("Software Engineer", "us")

    assert len(history) == 4
    # Results must be sorted chronologically
    periods = [h["period"] for h in history]
    assert periods == sorted(periods)
    assert history[0]["period"] == "2024-01"
    assert history[0]["value"] == 75000.0


async def test_salary_history_empty_month_map(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    httpx_mock.add_response(url=_HISTORY_URL_RE, json={"month": {}})

    history = await salary_history("Software Engineer", "us")

    assert history == []


async def test_salary_history_missing_creds_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "")

    history = await salary_history("Software Engineer", "us")

    assert history == []


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_salary_history_http_error_returns_empty(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    # tenacity retries on HTTPStatusError; register enough and allow extras
    for _ in range(5):
        httpx_mock.add_response(url=_HISTORY_URL_RE, status_code=429)

    history = await salary_history("Software Engineer", "us")

    assert history == []


# ---------------------------------------------------------------------------
# hottest_fields: categories + per-category vacancy counts
# ---------------------------------------------------------------------------


async def test_hottest_fields_sorted_by_openings_desc(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    httpx_mock.add_response(url=_CATEGORIES_URL_RE, json=_load("adzuna_categories.json"))

    # Per-category searches: IT=12500, Engineering=8000, Accounting=3000
    httpx_mock.add_response(
        url=_SEARCH_URL_RE, json={"count": 12500, "mean": 72000.0, "results": []}
    )
    httpx_mock.add_response(
        url=_SEARCH_URL_RE, json={"count": 8000, "mean": 65000.0, "results": []}
    )
    httpx_mock.add_response(
        url=_SEARCH_URL_RE, json={"count": 3000, "mean": 55000.0, "results": []}
    )

    fields = await hottest_fields("us")

    assert len(fields) == 3
    # Sorted descending by openings
    openings = [f["openings"] for f in fields]
    assert openings == sorted(openings, reverse=True)
    assert fields[0]["openings"] == 12500
    assert fields[0]["label"] == "IT Jobs"


async def test_hottest_fields_missing_creds_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "")

    fields = await hottest_fields("us")

    assert fields == []


async def test_hottest_fields_empty_categories_returns_empty(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    httpx_mock.add_response(url=_CATEGORIES_URL_RE, json={"results": []})

    fields = await hottest_fields("us")

    assert fields == []


@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_hottest_fields_categories_http_error_returns_empty(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    for _ in range(5):
        httpx_mock.add_response(url=_CATEGORIES_URL_RE, status_code=503)

    fields = await hottest_fields("us")

    assert fields == []


async def test_hottest_fields_skips_category_with_empty_tag(httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    categories = {
        "results": [{"tag": "", "label": "Unknown"}, {"tag": "it-jobs", "label": "IT Jobs"}]
    }
    httpx_mock.add_response(url=_CATEGORIES_URL_RE, json=categories)
    httpx_mock.add_response(
        url=_SEARCH_URL_RE, json={"count": 5000, "mean": 60000.0, "results": []}
    )

    fields = await hottest_fields("us")

    assert len(fields) == 1
    assert fields[0]["tag"] == "it-jobs"


async def test_hottest_fields_capped_at_8(httpx_mock, monkeypatch):
    """Even when categories API returns many items, results are capped at 8."""
    monkeypatch.setattr(settings, "adzuna_app_id", "test_id")
    monkeypatch.setattr(settings, "adzuna_app_key", settings.adzuna_app_key.__class__("test_key"))

    # 12 categories (sample limit) — all with valid tags
    categories = {"results": [{"tag": f"cat-{i}", "label": f"Category {i}"} for i in range(12)]}
    httpx_mock.add_response(url=_CATEGORIES_URL_RE, json=categories)

    # Return decreasing counts so ordering is predictable
    for i in range(12):
        httpx_mock.add_response(
            url=_SEARCH_URL_RE, json={"count": 1000 - i * 50, "mean": 50000.0, "results": []}
        )

    fields = await hottest_fields("us")

    assert len(fields) <= 8
