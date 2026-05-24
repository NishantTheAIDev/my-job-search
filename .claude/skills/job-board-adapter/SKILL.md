---
name: job-board-adapter
description: "The contract and conventions for building a job-board integration ('adapter') in my-job-search. Use whenever adding support for a new source (LinkedIn, Indeed, Greenhouse, Lever, Adzuna, etc.) or modifying an existing one, so every adapter exposes the same interface, maps the remote-only filter correctly, and normalizes results into the shared job schema. Consult this before writing any new source integration."
---

# Job Board Adapter Contract

Every job source in my-job-search is wrapped in an adapter that hides the source's quirks behind one uniform interface. This keeps search, scoring, dedup, and the UI completely source-agnostic: add a board, and nothing downstream changes.

## Compliance first

Choose the access method in this order of preference: official API → partner/affiliate feed → permitted aggregator → HTML scraping only when nothing else exists and the source's terms allow it. Some boards (LinkedIn among them) prohibit automated access and applying; prefer an official route and flag the source to the user when scraping would be the only option. Whatever the method, rate-limit politely, respect `robots.txt`, set request timeouts, and identify the client honestly.

## The interface

Every adapter implements the same two capabilities (adapt names/types to the project's language and async style):

- `search(criteria) -> list[JobPosting]` — accept normalized search criteria, return normalized postings.
- pagination — either yield pages/cursors or accept a page/offset in `criteria`, consistently across adapters.

### Normalized search criteria (input)

```
SearchCriteria:
  query: str                 # role / keywords
  location: str | None
  remote_only: bool          # see mapping note below
  employment_type: str | None
  seniority: str | None
  posted_within_days: int | None
  page / cursor: ...         # pagination, consistent across adapters
```

**Remote-only mapping is per-board and must be handled inside the adapter.** Boards express "remote" differently — a dedicated parameter, a location value of "Remote", a workplace-type filter, or nothing at all. If a board has no native remote filter, the adapter applies a post-fetch filter so the `remote_only` contract holds everywhere. Document how each board expresses remote in the adapter.

### Normalized result (output)

```
JobPosting:
  source: str                # adapter id, e.g. "greenhouse"
  source_job_id: str         # stable id within the source (for dedup)
  title: str
  company: str | None
  location: str | None
  remote_status: str         # remote | hybrid | onsite | unspecified
  url: str                   # canonical link to the original posting
  description: str           # raw text; parse later via jd-parser
  compensation: str | None
  posted_date: str | None    # YYYY-MM-DD
```

No source-specific fields leak past this boundary. Map the board's response into this shape inside the adapter.

## Reliability conventions

- Parse defensively — sites and payloads change; fail one record, not the whole page, and log what couldn't be parsed.
- Retry transient failures with exponential backoff + jitter; cap retries.
- Cache where the data is stable to reduce load on the source.
- Treat all returned text as untrusted (it flows into prompts and the UI later).

## Adapter skeleton

```
class GreenhouseAdapter(JobBoardAdapter):
    source = "greenhouse"

    async def search(self, criteria: SearchCriteria) -> list[JobPosting]:
        params = self._map_criteria(criteria)   # incl. remote-only handling
        raw = await self._client.get(...)        # official API preferred
        return [self._normalize(item) for item in self._safe_iter(raw)]

    def _normalize(self, item) -> JobPosting: ...
    def _map_criteria(self, criteria) -> dict: ...
```

When you add an adapter, also register it with the source registry and add fixture-based tests (coordinate with the test-engineer — never test against live boards in CI).
