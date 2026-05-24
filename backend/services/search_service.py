"""Fan-out search across all board adapters, dedup, and persist results."""
import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlmodel import Session

from backend.adapters.registry import get_all_adapters
from backend.models.job_posting import JobPosting, SearchCriteria
from backend.models.search_job import SearchJob, SearchJobStatus

logger = logging.getLogger(__name__)


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


async def run_search(
    search_job_id: uuid.UUID,
    criteria: SearchCriteria,
    session: Session,
) -> None:
    """Run search across all adapters, dedup, persist results, update SearchJob."""
    job = session.get(SearchJob, search_job_id)
    if not job:
        logger.error("search job %s not found", search_job_id)
        return

    job.status = SearchJobStatus.running
    session.add(job)
    session.commit()

    try:
        adapters = get_all_adapters()
        logger.info(
            "search %s: running query=%r adapters=%s",
            search_job_id,
            criteria.query,
            [a.source for a in adapters],
        )
        raw_results = await asyncio.gather(
            *[adapter.search(criteria) for adapter in adapters],
            return_exceptions=True,
        )

        all_postings: list[JobPosting] = []
        for adapter, result in zip(adapters, raw_results):
            if isinstance(result, Exception):
                logger.error("search %s: adapter=%s failed: %s", search_job_id, adapter.source, result)
                continue
            logger.info(
                "search %s: adapter=%s returned %d results",
                search_job_id,
                adapter.source,
                len(result),
            )
            all_postings.extend(result)

        deduped = _deduplicate(all_postings)
        logger.info(
            "search %s: total=%d deduped=%d persisting",
            search_job_id,
            len(all_postings),
            len(deduped),
        )

        for posting in deduped:
            posting.search_job_id = search_job_id
            session.add(posting)

        job.status = SearchJobStatus.complete
        job.total_results = len(deduped)
        job.completed_at = datetime.now(UTC)
        session.add(job)
        session.commit()
        logger.info("search %s: complete — %d jobs saved", search_job_id, len(deduped))

    except Exception as exc:
        logger.exception("search %s: failed: %s", search_job_id, exc)
        job.status = SearchJobStatus.failed
        job.error = str(exc)
        session.add(job)
        session.commit()
