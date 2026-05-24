import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session

from backend.background.tasks import start_search_task
from backend.database import get_session
from backend.limiter import limiter
from backend.models.job_posting import SearchCriteria
from backend.models.search_job import SearchJob, SearchJobStatus

logger = logging.getLogger(__name__)
router = APIRouter()


class SearchResponse(BaseModel):
    job_id: uuid.UUID
    status: SearchJobStatus


class SearchStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: SearchJobStatus
    total_results: int
    error: str | None


@router.post("", response_model=SearchResponse)
@limiter.limit("5/minute")
async def create_search(
    request: Request,
    criteria: SearchCriteria,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    search_job = SearchJob(
        criteria_json=criteria.model_dump_json(),
        created_at=datetime.now(UTC),
    )
    session.add(search_job)
    session.commit()
    session.refresh(search_job)

    background_tasks.add_task(start_search_task, search_job.id, criteria)
    logger.info(
        "search queued: id=%s query=%r remote_only=%s",
        search_job.id,
        criteria.query,
        criteria.remote_only,
    )

    return SearchResponse(job_id=search_job.id, status=search_job.status)


@router.get("/{job_id}/status", response_model=SearchStatusResponse)
def get_search_status(
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    job = session.get(SearchJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")
    return SearchStatusResponse(
        job_id=job.id,
        status=job.status,
        total_results=job.total_results,
        error=job.error,
    )
