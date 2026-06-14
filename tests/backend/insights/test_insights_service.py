"""Tests for the insights orchestration service — cache, fault tolerance, and region validation."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from backend.models.insights_cache import InsightsCache
from backend.services.insights_service import VALID_REGIONS, get_insights, get_salary

# ---------------------------------------------------------------------------
# In-memory session fixture (each test gets an isolated DB)
# ---------------------------------------------------------------------------


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Stub payloads
# ---------------------------------------------------------------------------

_NEWS = [{"title": "t1", "url": "http://u", "domain": "d.com", "seendate": "20260101T000000Z"}]
_SALARIES = [
    {"role": "Software Engineer", "median": 80000.0, "currency": "USD", "sample_size": 100}
]
_HOT_FIELDS = [
    {
        "label": "IT Jobs",
        "tag": "it-jobs",
        "openings": 5000,
        "mean_salary": 70000.0,
        "currency": "USD",
    }
]
_TRENDS = {
    "salary_history": [{"period": "2024-01", "value": 80000.0}],
    "unemployment": [{"year": 2023, "value": 3.9}],
    "employment": [{"year": 2023, "value": 60.1}],
}


def _all_section_patches():
    """Return a dict of patch targets → async return values for all four sections."""
    return {
        "backend.services.insights_service._fetch_news": _NEWS,
        "backend.services.insights_service._fetch_salaries": _SALARIES,
        "backend.services.insights_service._fetch_hottest_fields": _HOT_FIELDS,
        "backend.services.insights_service._fetch_trends": _TRENDS,
    }


# ---------------------------------------------------------------------------
# 1. Read-through cache — first call fetches + writes; second hits cache
# ---------------------------------------------------------------------------


async def test_first_call_fetches_and_writes_cache(session: Session):
    fetch_calls: list[str] = []

    async def mock_fetch_news(region: str) -> list:
        fetch_calls.append("news")
        return _NEWS

    async def mock_fetch_salaries(region: str) -> list:
        fetch_calls.append("salaries")
        return _SALARIES

    async def mock_fetch_hottest_fields(region: str) -> list:
        fetch_calls.append("hottest_fields")
        return _HOT_FIELDS

    async def mock_fetch_trends(region: str) -> dict:
        fetch_calls.append("trends")
        return _TRENDS

    with (
        patch("backend.services.insights_service._fetch_news", mock_fetch_news),
        patch("backend.services.insights_service._fetch_salaries", mock_fetch_salaries),
        patch("backend.services.insights_service._fetch_hottest_fields", mock_fetch_hottest_fields),
        patch("backend.services.insights_service._fetch_trends", mock_fetch_trends),
    ):
        await get_insights("us", session)

    assert set(fetch_calls) == {"news", "salaries", "hottest_fields", "trends"}

    # All four sections cached per-region.
    from sqlmodel import select

    rows = session.exec(select(InsightsCache).where(InsightsCache.region == "us")).all()
    assert {r.section for r in rows} == {"news", "salaries", "hottest_fields", "trends"}


async def test_second_call_within_ttl_does_not_refetch(session: Session, monkeypatch):
    """A second get_insights call within the TTL window must read from cache, not re-fetch."""
    fetch_counter = {"count": 0}

    async def mock_fetch_news(region: str) -> list:
        fetch_counter["count"] += 1
        return _NEWS

    async def mock_fetch_salaries(region: str) -> list:
        fetch_counter["count"] += 1
        return _SALARIES

    async def mock_fetch_hottest_fields(region: str) -> list:
        fetch_counter["count"] += 1
        return _HOT_FIELDS

    async def mock_fetch_trends(region: str) -> dict:
        fetch_counter["count"] += 1
        return _TRENDS

    with (
        patch("backend.services.insights_service._fetch_news", mock_fetch_news),
        patch("backend.services.insights_service._fetch_salaries", mock_fetch_salaries),
        patch("backend.services.insights_service._fetch_hottest_fields", mock_fetch_hottest_fields),
        patch("backend.services.insights_service._fetch_trends", mock_fetch_trends),
    ):
        # First call — populates cache (4 fetches)
        await get_insights("us", session)
        first_count = fetch_counter["count"]

        # Second call — should use cache
        await get_insights("us", session)
        second_count = fetch_counter["count"]

    # No additional fetches on the second call
    assert first_count == 4
    assert second_count == 4  # unchanged


async def test_stale_cache_triggers_refetch(session: Session, monkeypatch):
    """A cache row older than the TTL must trigger a re-fetch."""
    # Manually insert a stale cache row for the 'news' section
    stale_time = datetime.now(UTC) - timedelta(hours=48)
    stale_row = InsightsCache(
        section="news",
        region="us",
        payload=json.dumps(
            {"items": [{"title": "old", "url": "http://old", "domain": "old.com", "seendate": ""}]}
        ),
        fetched_at=stale_time,
    )
    session.add(stale_row)
    session.commit()

    fetch_calls: list[str] = []

    async def mock_fetch_news(region: str) -> list:
        fetch_calls.append("news")
        return _NEWS

    async def mock_fetch_salaries(region: str) -> list:
        return _SALARIES

    async def mock_fetch_hottest_fields(region: str) -> list:
        return _HOT_FIELDS

    async def mock_fetch_trends(region: str) -> dict:
        return _TRENDS

    with (
        patch("backend.services.insights_service._fetch_news", mock_fetch_news),
        patch("backend.services.insights_service._fetch_salaries", mock_fetch_salaries),
        patch("backend.services.insights_service._fetch_hottest_fields", mock_fetch_hottest_fields),
        patch("backend.services.insights_service._fetch_trends", mock_fetch_trends),
    ):
        await get_insights("us", session)

    # News must have been re-fetched
    assert "news" in fetch_calls


# ---------------------------------------------------------------------------
# 2. Partial failure — one section raises; others still populate
# ---------------------------------------------------------------------------


async def test_partial_section_failure_does_not_blank_page(session: Session):
    """If one section's fetcher raises, get_insights still returns the other sections."""

    async def mock_fetch_news(region: str) -> list:
        raise RuntimeError("GDELT is down")

    async def mock_fetch_salaries(region: str) -> list:
        return _SALARIES

    async def mock_fetch_hottest_fields(region: str) -> list:
        return _HOT_FIELDS

    async def mock_fetch_trends(region: str) -> dict:
        return _TRENDS

    with (
        patch("backend.services.insights_service._fetch_news", mock_fetch_news),
        patch("backend.services.insights_service._fetch_salaries", mock_fetch_salaries),
        patch("backend.services.insights_service._fetch_hottest_fields", mock_fetch_hottest_fields),
        patch("backend.services.insights_service._fetch_trends", mock_fetch_trends),
    ):
        result = await get_insights("us", session)

    # Salaries, hottest_fields, and trends should be populated
    assert result["salaries"] == _SALARIES
    assert result["hottest_fields"] == _HOT_FIELDS
    assert result["trends"] == _TRENDS
    # News section should degrade gracefully to an empty list
    assert result["news"] == []


# ---------------------------------------------------------------------------
# 3. Unknown region raises ValueError
# ---------------------------------------------------------------------------


async def test_get_insights_unknown_region_raises_value_error(session: Session):
    with pytest.raises(ValueError, match="Unknown region code"):
        await get_insights("xx", session)


async def test_get_insights_valid_regions_do_not_raise(session: Session):
    """All four VALID_REGIONS must be accepted without raising."""
    call_counter = {"count": 0}

    async def noop_fetcher(region: str):
        call_counter["count"] += 1
        return []

    async def noop_trends(region: str):
        return _TRENDS

    with (
        patch("backend.services.insights_service._fetch_news", noop_fetcher),
        patch("backend.services.insights_service._fetch_salaries", noop_fetcher),
        patch("backend.services.insights_service._fetch_hottest_fields", noop_fetcher),
        patch("backend.services.insights_service._fetch_trends", noop_trends),
    ):
        for region in VALID_REGIONS:
            result = await get_insights(region, session)
            assert result["region"] == region


# ---------------------------------------------------------------------------
# 4. get_salary — read-through cache and unknown region
# ---------------------------------------------------------------------------


async def test_get_salary_caches_result(session: Session, monkeypatch):
    call_count = {"n": 0}

    async def mock_salary_histogram(role: str, region: str):
        call_count["n"] += 1
        return (90000.0, 200)

    with patch("backend.services.insights_service.salary_histogram", mock_salary_histogram):
        r1 = await get_salary("Data Scientist", "us", session)
        r2 = await get_salary("Data Scientist", "us", session)

    assert call_count["n"] == 1  # second call read from cache
    assert r1 == r2
    assert r1["role"] == "Data Scientist"
    assert r1["median"] == pytest.approx(90000.0)
    assert r1["sample_size"] == 200


async def test_get_salary_unknown_region_raises_value_error(session: Session):
    with pytest.raises(ValueError, match="Unknown region code"):
        await get_salary("Software Engineer", "zz", session)


async def test_get_salary_response_structure(session: Session):
    async def mock_salary_histogram(role: str, region: str):
        return (75000.0, 150)

    with patch("backend.services.insights_service.salary_histogram", mock_salary_histogram):
        result = await get_salary("Frontend Developer", "in", session)

    assert set(result.keys()) == {"role", "median", "currency", "sample_size"}
    assert result["currency"] == "INR"
    assert result["median"] == pytest.approx(75000.0)
    assert result["sample_size"] == 150


async def test_get_salary_null_median_not_cached(session: Session):
    """A null median is NOT cached — it usually signals a transient fetch failure, so the
    next request re-fetches rather than serving 'no data' for the whole TTL."""
    call_count = {"n": 0}

    async def mock_salary_histogram(role: str, region: str):
        call_count["n"] += 1
        return (None, 0)

    with patch("backend.services.insights_service.salary_histogram", mock_salary_histogram):
        r1 = await get_salary("Niche Role", "us", session)
        r2 = await get_salary("Niche Role", "us", session)

    assert call_count["n"] == 2  # re-fetched, not served from cache
    assert r1["median"] is None
    assert r2["median"] is None


# ---------------------------------------------------------------------------
# 5. Output structure of get_insights
# ---------------------------------------------------------------------------


async def test_get_insights_output_has_required_keys(session: Session):
    async def noop(_region):
        return []

    async def noop_trends(_region):
        return _TRENDS

    with (
        patch("backend.services.insights_service._fetch_news", noop),
        patch("backend.services.insights_service._fetch_salaries", noop),
        patch("backend.services.insights_service._fetch_hottest_fields", noop),
        patch("backend.services.insights_service._fetch_trends", noop_trends),
    ):
        result = await get_insights("gb", session)

    required_keys = {
        "region",
        "currency",
        "generated_at",
        "news",
        "salaries",
        "hottest_fields",
        "trends",
    }
    assert required_keys.issubset(result.keys())
    assert result["region"] == "gb"
    assert result["currency"] == "GBP"
