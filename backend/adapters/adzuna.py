"""Adzuna job board adapter (free public REST API)."""

import logging
import re
from datetime import datetime

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.adapters.base import JobBoardAdapter
from backend.config import settings
from backend.models.job_posting import JobPosting, RemoteStatus, SearchCriteria

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

# Country names/aliases → Adzuna two-letter country code.
# Checked longest-first so "united kingdom" wins over "uk".
_COUNTRY_CODES: dict[str, str] = {
    "australia": "au",
    "austria": "at",
    "belgium": "be",
    "brazil": "br",
    "canada": "ca",
    "india": "in",
    "germany": "de",
    "deutschland": "de",
    "great britain": "gb",
    "united kingdom": "gb",
    "england": "gb",
    "uk": "gb",
    "mexico": "mx",
    "netherlands": "nl",
    "holland": "nl",
    "new zealand": "nz",
    "poland": "pl",
    "singapore": "sg",
    "south africa": "za",
    "united states": "us",
    "usa": "us",
}


def _parse_location(location: str | None) -> tuple[str, str | None]:
    """Return (adzuna_country_code, city_or_area_for_where_param).

    Strips the country name from the location string so the remainder
    (e.g. "Bangalore" from "Bangalore, India") becomes the ``where`` param.
    Defaults to the US endpoint when no known country is detected.
    """
    if not location:
        return "us", None

    loc = location.strip()
    loc_lower = loc.lower()

    for name in sorted(_COUNTRY_CODES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(name) + r"\b", loc_lower):
            code = _COUNTRY_CODES[name]
            city = re.sub(r"\b" + re.escape(name) + r"\b", "", loc, flags=re.IGNORECASE).strip(" ,")
            return code, city if city else None

    # No country found — default to US, pass the whole string as where
    return "us", loc


def _parse_compensation(result: dict) -> str | None:
    sal_min = result.get("salary_min")
    sal_max = result.get("salary_max")
    if sal_min and sal_max:
        return f"${int(sal_min):,}–${int(sal_max):,} / year"
    if sal_min:
        return f"${int(sal_min):,}+ / year"
    return None


def _parse_date(iso_str: str | None) -> str | None:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _infer_remote(location_name: str) -> RemoteStatus:
    if "remote" in location_name.lower():
        return RemoteStatus.remote
    return RemoteStatus.unspecified


class AdzunaAdapter(JobBoardAdapter):
    source = "adzuna"

    def _normalize(self, item: dict) -> JobPosting | None:
        try:
            location_name = (item.get("location") or {}).get("display_name") or ""
            return JobPosting(
                source=self.source,
                source_job_id=str(item["id"]),
                title=item["title"],
                company=(item.get("company") or {}).get("display_name"),
                location=location_name or None,
                remote_status=_infer_remote(location_name),
                url=item["redirect_url"],
                description=item.get("description") or "",
                compensation=_parse_compensation(item),
                posted_date=_parse_date(item.get("created")),
            )
        except (KeyError, TypeError) as exc:
            logger.warning("adzuna: failed to normalize item %s: %s", item.get("id"), exc)
            return None

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        wait=wait_exponential(min=1, max=30),
        stop=stop_after_attempt(3),
    )
    async def _fetch_page(self, url: str, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        if not settings.adzuna_app_id or not settings.adzuna_app_key.get_secret_value():
            logger.warning("adzuna: app_id or app_key not configured, skipping")
            return []

        country, city = _parse_location(criteria.location)
        url = _BASE_URL.format(country=country, page=criteria.page)

        params: dict = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key.get_secret_value(),
            "what": criteria.query,
            "results_per_page": 20,
            "content-type": "application/json",
        }
        if criteria.remote_only:
            params["where"] = "remote"
        elif city:
            params["where"] = city
        if criteria.posted_within_days:
            params["max_days_old"] = criteria.posted_within_days

        raw = await self._fetch_page(url, params)
        results = raw.get("results") or []

        postings: list[JobPosting] = []
        for item in self._safe_iter(results):
            posting = self._normalize(item)
            if posting is None:
                continue
            # post-filter: if remote_only, skip non-remote results
            if criteria.remote_only and posting.remote_status != RemoteStatus.remote:
                continue
            postings.append(posting)

        logger.info(
            "adzuna: query=%r page=%d → %d results", criteria.query, criteria.page, len(postings)
        )
        return postings
