"""World Bank macro indicators client — unemployment and employment-to-population ratios."""

import asyncio
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings
from backend.services.insights._http import retry_transient, safe_err

logger = logging.getLogger(__name__)

_BASE = "https://api.worldbank.org/v2/country"

# Indicators we fetch
_UNEMPLOYMENT_IND = "SL.UEM.TOTL.ZS"
_EMPLOYMENT_IND = "SL.EMP.TOTL.SP.ZS"

# Region → World Bank country code
REGION_TO_WB: dict[str, str] = {
    "in": "IN",
    "us": "US",
    "gb": "GB",
    "world": "WLD",
}


# World Bank is a non-critical keyless source that is intermittently slow/unreachable.
# Fail fast (short timeout, few retries) so a cold-cache request never stalls the page.
@retry(
    retry=retry_transient,
    wait=wait_exponential(min=1, max=4),
    stop=stop_after_attempt(2),
    reraise=True,
)
async def _get(url: str, params: dict) -> list:
    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        # World Bank returns [meta, [records...]]
        if isinstance(data, list) and len(data) == 2:
            return data[1] or []
        return []


async def _fetch_indicator(wb_country: str, indicator: str) -> list[dict]:
    """Fetch yearly values for an indicator. Returns [{year, value}] sorted asc."""
    url = f"{_BASE}/{wb_country}/indicator/{indicator}"
    params = {
        "format": "json",
        "per_page": 10,
        "date": "2015:2025",
    }
    try:
        records = await _get(url, params)
        result = [
            {"year": int(r["date"]), "value": r["value"]}
            for r in records
            if r.get("date") and r.get("value") is not None
        ]
        result.sort(key=lambda x: x["year"])
        return result
    except Exception as exc:
        logger.warning(
            "worldbank: indicator=%r country=%r error=%s",
            indicator,
            wb_country,
            safe_err(exc),
        )
        return []


async def get_macro(region: str) -> dict:
    """Return macro trend data for the given region.

    Returns {unemployment: [{year, value}], employment: [{year, value}]}.
    Keyless endpoint — always available unless network is down.
    """
    if not settings.worldbank_enabled:
        return {"unemployment": [], "employment": []}

    wb_country = REGION_TO_WB.get(region, "WLD")

    # Fetch the two indicators concurrently rather than back-to-back.
    unemployment, employment = await asyncio.gather(
        _fetch_indicator(wb_country, _UNEMPLOYMENT_IND),
        _fetch_indicator(wb_country, _EMPLOYMENT_IND),
    )

    return {"unemployment": unemployment, "employment": employment}
