import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.auth.dependencies import get_current_user
from backend.background.tasks import start_search_task
from backend.database import get_session
from backend.limiter import limiter
from backend.models.job_posting import SearchCriteria
from backend.models.search_job import SearchJob, SearchJobStatus
from backend.models.user import User
from backend.services.search_service import compute_criteria_fingerprint

logger = logging.getLogger(__name__)
router = APIRouter()


class SearchResponse(BaseModel):
    job_id: uuid.UUID
    status: SearchJobStatus
    # True when the response is served from a same-day cached SearchJob rather
    # than a freshly queued one.  The frontend can use this to show a "cached"
    # badge and offer a force-refresh button.
    cached: bool = False


class SearchStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: SearchJobStatus
    total_results: int
    completed_adapters: int
    total_adapters: int
    error: str | None


@router.post("", response_model=SearchResponse)
@limiter.limit("5/minute")
async def create_search(
    request: Request,
    criteria: SearchCriteria,
    background_tasks: BackgroundTasks,
    force: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Queue a new fan-out search across all board adapters.

    Same-day cache (force=False, default):
      If the user already ran an identical search today (same criteria, same
      page) and it completed successfully, return that existing SearchJob
      immediately with cached=true — no adapters are re-queried.
      Day boundary is UTC midnight (noted here for transparency).

    Force re-search (force=True):
      Always creates a new SearchJob and queues adapters regardless of any
      cached result from earlier today.
    """
    fingerprint = compute_criteria_fingerprint(criteria)

    if not force:
        # Day boundary: start of today in UTC (midnight UTC).
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        cached_job = session.exec(
            select(SearchJob)
            .where(
                SearchJob.user_id == current_user.id,
                SearchJob.status == SearchJobStatus.complete,
                SearchJob.criteria_fingerprint == fingerprint,
                SearchJob.created_at >= today_start,
            )
            .order_by(SearchJob.created_at.desc())
        ).first()

        if cached_job:
            logger.info(
                "search cache hit: id=%s query=%r fingerprint=%s",
                cached_job.id,
                criteria.query,
                fingerprint,
            )
            return SearchResponse(
                job_id=cached_job.id,
                status=cached_job.status,
                cached=True,
            )

    search_job = SearchJob(
        user_id=current_user.id,
        criteria_json=criteria.model_dump_json(),
        criteria_fingerprint=fingerprint,
        created_at=datetime.now(UTC),
    )
    session.add(search_job)
    session.commit()
    session.refresh(search_job)

    background_tasks.add_task(start_search_task, search_job.id, criteria)
    logger.info(
        "search queued: id=%s query=%r remote_only=%s fingerprint=%s",
        search_job.id,
        criteria.query,
        criteria.remote_only,
        fingerprint,
    )

    return SearchResponse(job_id=search_job.id, status=search_job.status, cached=False)


@router.get("/{job_id}/status", response_model=SearchStatusResponse)
def get_search_status(
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    job = session.get(SearchJob, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Search job not found")
    return SearchStatusResponse(
        job_id=job.id,
        status=job.status,
        total_results=job.total_results,
        completed_adapters=job.completed_adapters,
        total_adapters=job.total_adapters,
        error=job.error,
    )
