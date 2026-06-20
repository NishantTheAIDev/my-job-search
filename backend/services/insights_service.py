"""Orchestration service for Job Market Insights — cache-backed, fault-tolerant."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.config import settings
from backend.models.insights_cache import InsightsCache
from backend.services.insights.adzuna_insights import (
    DEFAULT_ROLES,
    REGION_CURRENCY,
    REGION_TO_ADZUNA,
    hottest_fields,
    salary_histogram,
    salary_history,
)
from backend.services.insights.news import get_news
from backend.services.insights.worldbank import get_macro

logger = logging.getLogger(__name__)

VALID_REGIONS: frozenset[str] = frozenset(REGION_TO_ADZUNA.keys())


# ---------------------------------------------------------------------------
# Section fetchers
# ---------------------------------------------------------------------------


async def _fetch_news(region: str) -> list[dict]:
    return await get_news(region)


async def _fetch_salaries(region: str) -> list[dict]:
    currency = REGION_CURRENCY.get(region, "USD")
    tasks = [salary_histogram(role, region) for role in DEFAULT_ROLES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    salaries: list[dict] = []
    for role, result in zip(DEFAULT_ROLES, results, strict=True):
        if isinstance(result, Exception):
            logger.warning(
                "insights: salary_histogram role=%r region=%r error=%s", role, region, result
            )
            continue
        median, sample_size = result
        salaries.append(
            {
                "role": role,
                "median": median,
                "currency": currency,
                "sample_size": sample_size,
            }
        )
    return salaries


async def _fetch_hottest_fields(region: str) -> list[dict]:
    currency = REGION_CURRENCY.get(region, "USD")
    fields = await hottest_fields(region)
    # Attach currency label for the UI
    for f in fields:
        f["currency"] = currency
    return fields


async def _fetch_trends(region: str) -> dict:
    # Run salary history for a representative role and macro data in parallel
    rep_role = "Software Engineer"
    sal_hist_task = salary_history(rep_role, region)
    macro_task = get_macro(region)
    results = await asyncio.gather(sal_hist_task, macro_task, return_exceptions=True)

    sal_hist: list[dict] = []
    macro: dict = {"unemployment": [], "employment": []}

    if isinstance(results[0], Exception):
        logger.warning("insights: salary_history region=%r error=%s", region, results[0])
    else:
        sal_hist = results[0]  # type: ignore[assignment]

    if isinstance(results[1], Exception):
        logger.warning("insights: worldbank region=%r error=%s", region, results[1])
    else:
        macro = results[1]  # type: ignore[assignment]

    return {
        "salary_history": sal_hist,
        "unemployment": macro.get("unemployment", []),
        "employment": macro.get("employment", []),
    }


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _has_data(value: dict | list) -> bool:
    """True if a fetched section is worth caching (non-empty).

    For trends (a dict of series) this is true when any series has points.
    """
    if isinstance(value, dict):
        return any(value.get(k) for k in value)
    return bool(value)


def _get_cached(section: str, region: str, session: Session) -> dict | None:
    """Return a cached payload if it exists and is within the TTL, else None."""
    row = session.exec(
        select(InsightsCache)
        .where(InsightsCache.section == section)
        .where(InsightsCache.region == region)
    ).first()
    if row is None:
        return None
    ttl = timedelta(hours=settings.insights_cache_ttl_hours)
    if datetime.now(UTC) - row.fetched_at.replace(tzinfo=UTC) < ttl:
        try:
            return json.loads(row.payload)
        except json.JSONDecodeError:
            logger.warning("insights cache: corrupt payload section=%r region=%r", section, region)
            return None
    return None


def _upsert_cache(section: str, region: str, payload: dict, session: Session) -> None:
    """Insert or replace a cache row for (section, region).

    A concurrent cold-cache request may have inserted the same (section, region) row;
    the DB-level unique constraint turns that race into an IntegrityError, which we
    recover from by rolling back and updating the now-existing row.
    """
    existing = session.exec(
        select(InsightsCache)
        .where(InsightsCache.section == section)
        .where(InsightsCache.region == region)
    ).first()
    if existing:
        existing.payload = json.dumps(payload)
        existing.fetched_at = datetime.now(UTC)
        session.add(existing)
    else:
        session.add(
            InsightsCache(
                section=section,
                region=region,
                payload=json.dumps(payload),
                fetched_at=datetime.now(UTC),
            )
        )
    try:
        session.commit()
    except IntegrityError:
        # Lost an insert race — roll back and update the row the winner created.
        session.rollback()
        row = session.exec(
            select(InsightsCache)
            .where(InsightsCache.section == section)
            .where(InsightsCache.region == region)
        ).first()
        if row is not None:
            row.payload = json.dumps(payload)
            row.fetched_at = datetime.now(UTC)
            session.add(row)
            session.commit()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_insights(region: str, session: Session) -> dict:
    """Return full insights payload for a region, using read-through cache.

    Each section is fetched independently; one failing source never blanks the page.
    Raises ValueError for unknown region codes (router maps this to HTTP 400).
    """
    if region not in VALID_REGIONS:
        raise ValueError(f"Unknown region code: {region!r}. Valid codes: {sorted(VALID_REGIONS)}")

    sections = ["news", "salaries", "hottest_fields", "trends"]
    fetchers = {
        "news": _fetch_news,
        "salaries": _fetch_salaries,
        "hottest_fields": _fetch_hottest_fields,
        "trends": _fetch_trends,
    }

    async def _load_section(section: str) -> tuple[str, dict | list, bool]:
        """Return (section, value, is_fresh). Network only — no DB writes here,
        so concurrent gather() never commits on the shared Session simultaneously."""
        cached = _get_cached(section, region, session)
        if cached is not None:
            logger.debug("insights cache: hit section=%r region=%r", section, region)
            return section, cached, False
        logger.info("insights: fetching section=%r region=%r", section, region)
        result = await fetchers[section](region)
        return section, result, True

    raw_results = await asyncio.gather(
        *[_load_section(s) for s in sections],
        return_exceptions=True,
    )

    output: dict[str, list | dict] = {}
    to_cache: list[tuple[str, dict]] = []
    for section, raw in zip(sections, raw_results, strict=True):
        if isinstance(raw, Exception):
            logger.error("insights: section=%r region=%r failed: %s", section, region, raw)
            output[section] = [] if section != "trends" else {}
        else:
            # raw is a (section, value, is_fresh) tuple from _load_section
            _, value, is_fresh = raw  # type: ignore[misc]
            # Only cache freshly-fetched sections that actually returned data — otherwise a
            # transient upstream failure (e.g. World Bank timeout, GDELT 429) would freeze
            # an empty section in the cache for the full TTL.
            if is_fresh and _has_data(value):
                to_cache.append((section, value if isinstance(value, dict) else {"items": value}))
            # Unwrap the {items: [...]} envelope used for list sections in cache
            if isinstance(value, dict) and set(value.keys()) == {"items"}:
                output[section] = value["items"]
            else:
                output[section] = value

    # Persist freshly-fetched sections serially (single Session, one writer at a time).
    for section, payload in to_cache:
        _upsert_cache(section, region, payload, session)

    return {
        "region": region,
        "currency": REGION_CURRENCY.get(region, "USD"),
        "generated_at": datetime.now(UTC).isoformat(),
        "news": output.get("news", []),
        "salaries": output.get("salaries", []),
        "hottest_fields": output.get("hottest_fields", []),
        "trends": output.get("trends", {}),
    }


async def get_salary(role: str, region: str, session: Session) -> dict:
    """On-demand single-role salary lookup with cache.

    Returns {role, median, currency, sample_size}.
    Raises ValueError for unknown region codes.
    """
    if region not in VALID_REGIONS:
        raise ValueError(f"Unknown region code: {region!r}. Valid codes: {sorted(VALID_REGIONS)}")

    # Normalize the cache key (case/whitespace-insensitive) so "Data Scientist",
    # "data scientist", and " Data Scientist " share one row instead of polluting the cache.
    role = role.strip()
    section = f"salary:{role.casefold()}"
    currency = REGION_CURRENCY.get(region, "USD")

    cached = _get_cached(section, region, session)
    if cached is not None:
        logger.debug("insights cache: hit section=%r region=%r", section, region)
        return cached

    median, sample_size = await salary_histogram(role, region)
    result = {
        "role": role,
        "median": median,
        "currency": currency,
        "sample_size": sample_size,
    }
    # Don't cache a null result — it usually means a transient fetch failure, and we
    # don't want to serve "no data" for the full TTL when the next request might succeed.
    if median is not None:
        _upsert_cache(section, region, result, session)
    return result
