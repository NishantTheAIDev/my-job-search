import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.background.tasks import prepare_application_task
from backend.database import get_session
from backend.models.job_posting import JobPosting, RemoteStatus

logger = logging.getLogger(__name__)
router = APIRouter()


class JobPostingResponse(BaseModel):
    id: uuid.UUID
    source: str
    title: str
    company: str | None
    location: str | None
    remote_status: RemoteStatus
    url: str
    compensation: str | None
    posted_date: str | None
    match_score: int | None


class JobsListResponse(BaseModel):
    items: list[JobPostingResponse]
    total: int
    page: int
    page_size: int


def _to_response(p: JobPosting) -> JobPostingResponse:
    return JobPostingResponse(
        id=p.id,
        source=p.source,
        title=p.title,
        company=p.company,
        location=p.location,
        remote_status=p.remote_status,
        url=p.url,
        compensation=p.compensation,
        posted_date=p.posted_date,
        match_score=p.match_score,
    )


@router.get("", response_model=JobsListResponse)
def list_jobs(
    search_job_id: uuid.UUID,
    min_score: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    query = select(JobPosting).where(JobPosting.search_job_id == search_job_id)
    if min_score is not None:
        query = query.where(JobPosting.match_score >= min_score)

    all_items = session.exec(query).all()
    total = len(all_items)
    start = (page - 1) * page_size
    items = all_items[start : start + page_size]

    return JobsListResponse(
        items=[_to_response(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=JobPostingResponse)
def get_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    posting = session.get(JobPosting, job_id)
    if not posting:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return _to_response(posting)


@router.post("/{job_id}/prepare")
async def prepare_application(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    # Verify job exists
    posting = session.get(JobPosting, job_id)
    if not posting:
        raise HTTPException(status_code=404, detail="Job posting not found")

    background_tasks.add_task(prepare_application_task, job_id)
    logger.info("prepare queued: job_id=%s title=%r", job_id, posting.title)
    return {"status": "preparing", "job_id": str(job_id)}
