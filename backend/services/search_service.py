"""Fan-out search across all board adapters, dedup, and persist results."""

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime

from sqlmodel import Session

from backend.adapters.registry import get_all_adapters
from backend.models.job_posting import JobPosting, SearchCriteria
from backend.models.search_job import SearchJob, SearchJobStatus
from backend.services.relevance import score_relevance

logger = logging.getLogger(__name__)


def compute_criteria_fingerprint(criteria: SearchCriteria) -> str:
    """Return a stable SHA-256 hex digest of the normalised search criteria.

    All fields that affect search results are included.  Normalisation rules:
      - query: strip whitespace + lowercase
      - location: strip whitespace + lowercase, or None when absent/blank
      - booleans / ints / None values are included as-is
      - keys are sorted so dict ordering never affects the digest

    The resulting fingerprint is stored on SearchJob so same-day duplicate
    searches can be detected and served from the DB without re-hitting adapter
    APIs.
    """
    normalised = {
        "query": (criteria.query or "").strip().lower(),
        "location": (criteria.location.strip().lower() if criteria.location else None),
        "remote_only": criteria.remote_only,
        "employment_type": criteria.employment_type,
        "seniority": criteria.seniority,
        "posted_within_days": criteria.posted_within_days,
        "page": criteria.page,
    }
    canonical = json.dumps(normalised, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _deduplicate(postings: list[JobPosting]) -> list[JobPosting]:
    """Remove duplicates by (source, source_job_id)."""
    seen: set[tuple[str, str]] = set()
    unique: list[JobPosting] = []
    for p in postings:
        key = (p.source, p.source_job_id)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


async def _run_one(
    adapter,
    criteria: SearchCriteria,
) -> tuple:
    """Run a single adapter and return (adapter, postings, exc) — never raises."""
    try:
        return adapter, await adapter.search(criteria), None
    except Exception as exc:  # noqa: BLE001
        return adapter, None, exc


async def run_search(
    search_job_id: uuid.UUID,
    criteria: SearchCriteria,
    session: Session,
) -> None:
    """Run search across all adapters incrementally, dedup, and persist results."""
    job = session.get(SearchJob, search_job_id)
    if not job:
        logger.error("search job %s not found", search_job_id)
        return

    adapters = get_all_adapters()
    job.status = SearchJobStatus.running
    job.total_adapters = len(adapters)
    job.completed_adapters = 0
    job.total_results = 0
    session.add(job)
    session.commit()

    try:
        logger.info(
            "search %s: running query=%r adapters=%s",
            search_job_id,
            criteria.query,
            [a.source for a in adapters],
        )

        # in-memory dedup carried across all adapter chunks within this run
        seen: set[tuple[str, str]] = set()
        running_total = 0

        futs = [asyncio.ensure_future(_run_one(a, criteria)) for a in adapters]
        for fut in asyncio.as_completed(futs):
            adapter, result, exc = await fut

            if exc is not None:
                logger.error(
                    "search %s: adapter=%s failed: %s",
                    search_job_id,
                    adapter.source,
                    exc,
                )
                job.completed_adapters += 1
                session.add(job)
                session.commit()
                continue

            logger.info(
                "search %s: adapter=%s returned %d results",
                search_job_id,
                adapter.source,
                len(result),
            )

            # dedup against already-persisted postings from earlier adapters
            new_postings: list[JobPosting] = []
            for posting in result:
                key = (posting.source, posting.source_job_id)
                if key not in seen:
                    seen.add(key)
                    new_postings.append(posting)

            for posting in new_postings:
                posting.search_job_id = search_job_id
                posting.user_id = job.user_id
                posting.relevance_score = score_relevance(
                    posting.title, posting.description, criteria.query
                )
                session.add(posting)

            running_total += len(new_postings)
            job.completed_adapters += 1
            job.total_results = running_total
            session.add(job)
            session.commit()

        job.status = SearchJobStatus.complete
        job.completed_at = datetime.now(UTC)
        session.add(job)
        session.commit()
        logger.info("search %s: complete — %d jobs saved", search_job_id, running_total)

    except Exception as exc:
        logger.exception("search %s: failed: %s", search_job_id, exc)
        job.status = SearchJobStatus.failed
        job.error = str(exc)
        session.add(job)
        session.commit()
