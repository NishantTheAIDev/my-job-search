#!/usr/bin/env python
"""Resolve which YC companies host jobs on Greenhouse / Lever / Ashby.

Approach B (curated config): the yc-oss public API lists hiring YC companies but
not their ATS board tokens. This script discovers those tokens by deriving
candidate slugs from each company's name + website and probing the three public
board APIs we support. It prints the verified slug lists ready to paste into
.env (GREENHOUSE_COMPANIES / LEVER_COMPANIES / ASHBY_COMPANIES).

It is an offline maintenance tool — NOT called at search time. Run it
periodically and update the env lists:

    uv run python scripts/refresh_yc_ats.py                 # all hiring cos
    uv run python scripts/refresh_yc_ats.py --limit 50      # quick sample
    uv run python scripts/refresh_yc_ats.py --out yc_ats.env

Slug derivation is heuristic: a hit means the slug serves a public board, not
necessarily that it's *this* company's board (a name collision is possible).
Skim the output before committing it.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from urllib.parse import urlparse

import httpx

HIRING_URL = "https://yc-oss.github.io/api/companies/hiring.json"

# {slug} board endpoints. A 200 with a non-empty job list counts as a hit.
ATS_ENDPOINTS: dict[str, str] = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}

_HEADERS = {"user-agent": "my-job-search/1.0 (+yc-ats-resolver)"}
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalize(text: str) -> str:
    return _NON_ALNUM.sub("", text.lower())


def candidate_slugs(name: str | None, website: str | None, yc_slug: str | None) -> list[str]:
    """Derive ordered, de-duplicated candidate ATS slugs for one company.

    Sources, most-reliable first: the website's registrable label, the yc-oss
    slug, and a normalized form of the company name.
    """
    candidates: list[str] = []

    if website:
        host = urlparse(website if "//" in website else f"//{website}").netloc or website
        host = host.split(":")[0]
        labels = [p for p in host.split(".") if p not in ("www", "com", "io", "co", "ai", "app")]
        if labels:
            candidates.append(_normalize(labels[0]))

    if yc_slug:
        candidates.append(_normalize(yc_slug))

    if name:
        candidates.append(_normalize(name))

    # De-duplicate, preserving order; drop empties and very short slugs.
    seen: set[str] = set()
    result: list[str] = []
    for slug in candidates:
        if len(slug) >= 2 and slug not in seen:
            seen.add(slug)
            result.append(slug)
    return result


async def _probe(client: httpx.AsyncClient, ats: str, slug: str) -> bool:
    """Return True if `slug` serves a non-empty public board on `ats`."""
    url = ATS_ENDPOINTS[ats].format(slug=slug)
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return False
        data = resp.json()
    except httpx.HTTPError, ValueError:
        return False
    if ats == "lever":
        return bool(data)  # Lever returns a bare list
    return bool(data.get("jobs"))  # Greenhouse & Ashby wrap in {"jobs": [...]}


async def _resolve_company(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, company: dict
) -> dict[str, str]:
    """Try each ATS for a company; stop at the first slug that hits per ATS."""
    slugs = candidate_slugs(company.get("name"), company.get("website"), company.get("slug"))
    found: dict[str, str] = {}
    async with sem:
        for ats in ATS_ENDPOINTS:
            for slug in slugs:
                if await _probe(client, ats, slug):
                    found[ats] = slug
                    break
    if found:
        print(f"  ✓ {company.get('name')}: {found}", file=sys.stderr)
    return found


async def resolve_all(companies: list[dict], concurrency: int) -> dict[str, list[str]]:
    sem = asyncio.Semaphore(concurrency)
    by_ats: dict[str, list[str]] = {ats: [] for ats in ATS_ENDPOINTS}
    async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS) as client:
        tasks = [_resolve_company(client, sem, c) for c in companies]
        for result in await asyncio.gather(*tasks):
            for ats, slug in result.items():
                by_ats[ats].append(slug)
    for ats in by_ats:
        by_ats[ats] = sorted(set(by_ats[ats]))
    return by_ats


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="only probe the first N companies")
    parser.add_argument("--concurrency", type=int, default=10, help="max concurrent companies")
    parser.add_argument("--out", type=str, default=None, help="write env lines to this file")
    args = parser.parse_args()

    print(f"Fetching hiring companies from {HIRING_URL} ...", file=sys.stderr)
    async with httpx.AsyncClient(timeout=30.0, headers=_HEADERS) as client:
        resp = await client.get(HIRING_URL)
        resp.raise_for_status()
        companies = [c for c in resp.json() if c.get("isHiring")]
    if args.limit:
        companies = companies[: args.limit]
    print(
        f"Probing {len(companies)} companies across {len(ATS_ENDPOINTS)} ATSes ...", file=sys.stderr
    )

    by_ats = await resolve_all(companies, args.concurrency)

    env_var = {
        "greenhouse": "GREENHOUSE_COMPANIES",
        "lever": "LEVER_COMPANIES",
        "ashby": "ASHBY_COMPANIES",
    }
    lines = [f"{env_var[ats]}={','.join(slugs)}" for ats, slugs in by_ats.items()]
    output = "\n".join(lines) + "\n"

    counts = ", ".join(f"{ats}={len(slugs)}" for ats, slugs in by_ats.items())
    print(f"\nResolved: {counts}", file=sys.stderr)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(output)
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(output, end="")


if __name__ == "__main__":
    asyncio.run(_main())
