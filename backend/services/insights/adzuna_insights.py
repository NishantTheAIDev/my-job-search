"""Adzuna insights client — salary histograms, history, and category hotness."""

import asyncio
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings
from backend.services.insights._http import retry_transient, safe_err

logger = logging.getLogger(__name__)

_BASE = "https://api.adzuna.com/v1/api/jobs"

# A single insights page load fans out ~22 Adzuna calls (salaries + history + categories +
# per-category searches). Firing them all at once trips Adzuna's free-tier rate limit (429),
# so cap in-flight requests. Cold load is slightly slower but reliable; results cache 24h.
_CONCURRENCY = asyncio.Semaphore(4)


# Subset of the Adzuna two-letter country codes used for insights.
# Kept in sync with backend/adapters/adzuna.py::_COUNTRY_CODES.
REGION_TO_ADZUNA: dict[str, str] = {
    "in": "in",
    "us": "us",
    "gb": "gb",
    "world": "gb",  # best English-language broad proxy
}

REGION_CURRENCY: dict[str, str] = {
    "in": "INR",
    "us": "USD",
    "gb": "GBP",
    "world": "USD",
}

# Roles used for the default salary table
DEFAULT_ROLES: list[str] = [
    "Software Engineer",
    "Data Scientist",
    "Product Manager",
    "DevOps Engineer",
    "Data Analyst",
    "Frontend Developer",
    "Backend Developer",
    "ML Engineer",
]


def _creds_present() -> bool:
    return bool(settings.adzuna_app_id and settings.adzuna_app_key.get_secret_value())


def _auth_params() -> dict:
    return {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key.get_secret_value(),
    }


@retry(
    retry=retry_transient,
    wait=wait_exponential(min=1, max=8),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _get(url: str, params: dict) -> dict:
    async with _CONCURRENCY, httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _safe_bucket(bucket_str: str, count_str: str) -> tuple[float, int] | None:
    """Parse a histogram bucket safely; return None on any conversion error."""
    try:
        return float(bucket_str), int(count_str)
    except Exception:  # noqa: BLE001
        return None


def _compute_median(histogram: dict) -> tuple[float | None, int]:
    """Walk a salary-histogram dict (bucket_str → count_str) to the 50th-percentile bucket.

    Returns (median_salary, total_sample_size). Buckets with non-numeric keys are skipped.
    """
    parsed: list[tuple[float, int]] = []
    for bucket_str, count_str in histogram.items():
        item = _safe_bucket(bucket_str, count_str)
        if item is not None:
            parsed.append(item)

    if not parsed:
        return None, 0

    parsed.sort(key=lambda x: x[0])
    total = sum(c for _, c in parsed)
    midpoint = total / 2.0
    cumulative = 0.0
    for bucket, count in parsed:
        cumulative += count
        if cumulative >= midpoint:
            return bucket, total
    # Fallback: return the highest bucket
    return parsed[-1][0], total


async def salary_histogram(role: str, region: str) -> tuple[float | None, int]:
    """Return (median_salary, sample_size) for the given role and region.

    Returns (None, 0) gracefully on any error or missing creds.
    """
    if not _creds_present():
        logger.warning("adzuna_insights: creds not configured — skipping salary_histogram")
        return None, 0

    country = REGION_TO_ADZUNA.get(region, "gb")
    url = f"{_BASE}/{country}/histogram"
    params = {**_auth_params(), "what": role}

    try:
        data = await _get(url, params)
        histogram = data.get("histogram") or {}
        return _compute_median(histogram)
    except Exception as exc:
        logger.warning(
            "adzuna_insights: salary_histogram role=%r region=%r error=%s",
            role,
            region,
            safe_err(exc),
        )
        return None, 0


async def salary_history(role: str, region: str) -> list[dict]:
    """Return a list of {period: 'YYYY-MM', value: float} dicts sorted chronologically.

    Returns [] gracefully on any error or missing creds.
    """
    if not _creds_present():
        logger.warning("adzuna_insights: creds not configured — skipping salary_history")
        return []

    country = REGION_TO_ADZUNA.get(region, "gb")
    url = f"{_BASE}/{country}/history"
    params = {**_auth_params(), "what": role}

    try:
        data = await _get(url, params)
        month_map: dict = data.get("month") or {}
        result = [
            {"period": period, "value": float(value)}
            for period, value in month_map.items()
            if value is not None
        ]
        result.sort(key=lambda x: x["period"])
        return result
    except Exception as exc:
        logger.warning(
            "adzuna_insights: salary_history role=%r region=%r error=%s",
            role,
            region,
            safe_err(exc),
        )
        return []


async def hottest_fields(region: str) -> list[dict]:
    """Return top fields sorted by vacancy count.

    Each entry: {label, tag, openings, mean_salary}.
    Returns [] on missing creds or errors.
    """
    if not _creds_present():
        logger.warning("adzuna_insights: creds not configured — skipping hottest_fields")
        return []

    country = REGION_TO_ADZUNA.get(region, "gb")

    # Step 1: fetch category list
    cat_url = f"{_BASE}/{country}/categories"
    try:
        cat_data = await _get(cat_url, _auth_params())
        categories: list[dict] = cat_data.get("results") or []
    except Exception as exc:
        logger.warning("adzuna_insights: categories region=%r error=%s", region, safe_err(exc))
        return []

    if not categories:
        return []

    # Step 2: for each category fetch vacancy count + mean salary (search page 1, 1 result).
    # Limit to avoid excessive requests — take first 12 categories and keep top 8.
    # Fan out concurrently so this section isn't ~12 sequential round-trips inside the request.
    search_base = f"{_BASE}/{country}/search/1"
    auth = _auth_params()
    sample = [cat for cat in categories[:12] if cat.get("tag")]

    async def _fetch_one(cat: dict) -> dict | None:
        tag = cat["tag"]
        label = cat.get("label") or tag
        params = {**auth, "category": tag, "results_per_page": 1}
        try:
            result = await _get(search_base, params)
        except Exception as exc:
            logger.warning("adzuna_insights: category %r search error=%s", tag, safe_err(exc))
            return None
        mean = result.get("mean")
        return {
            "label": label,
            "tag": tag,
            "openings": int(result.get("count") or 0),
            # None (not 0.0) when Adzuna has no mean — the UI hides "avg" rather than showing ₹0.
            "mean_salary": float(mean) if mean else None,
        }

    results = await asyncio.gather(*[_fetch_one(cat) for cat in sample], return_exceptions=True)
    fields = [r for r in results if isinstance(r, dict)]
    fields.sort(key=lambda x: x["openings"], reverse=True)
    return fields[:8]
