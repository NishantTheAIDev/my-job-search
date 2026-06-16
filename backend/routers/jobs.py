import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, nullslast
from sqlmodel import Session, select

from backend.auth.dependencies import get_current_user
from backend.background.tasks import prepare_application_task
from backend.database import get_session
from backend.limiter import limiter
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.models.user import User
from backend.services.application_service import ApplicationError, create_manual_application

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
    description: str
    compensation: str | None
    posted_date: str | None
    match_score: int | None
    relevance_score: int | None


class JobsListResponse(BaseModel):
    items: list[JobPostingResponse]
    total: int
    page: int
    page_size: int


class JobFiltersResponse(BaseModel):
    sources: list[str]
    companies: list[str]


def _to_response(p: JobPosting) -> JobPostingResponse:
    return JobPostingResponse(
        id=p.id,
        source=p.source,
        title=p.title,
        company=p.company,
        location=p.location,
        remote_status=p.remote_status,
        url=p.url,
        description=p.description,
        compensation=p.compensation,
        posted_date=p.posted_date,
        match_score=p.match_score,
        relevance_score=p.relevance_score,
    )


@router.get("", response_model=JobsListResponse)
def list_jobs(
    search_job_id: uuid.UUID,
    min_score: int | None = Query(default=None),
    min_relevance: int | None = Query(default=30),
    source: list[str] | None = Query(default=None),
    company: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    query = select(JobPosting).where(
        JobPosting.user_id == current_user.id,
        JobPosting.search_job_id == search_job_id,
    )
    if min_score is not None:
        query = query.where(JobPosting.match_score >= min_score)
    if min_relevance is not None:
        # Rows with NULL relevance_score are legacy/un-scored — let them through.
        # Only exclude rows that have a score AND it falls below the floor.
        query = query.where(
            (JobPosting.relevance_score == None)  # noqa: E711
            | (JobPosting.relevance_score >= min_relevance)
        )
    if source:
        query = query.where(JobPosting.source.in_(source))
    if company:
        query = query.where(JobPosting.company.in_(company))
    if source or company:
        logger.debug("list_jobs: filtering source=%s company=%s", source, company)

    # Sort by relevance descending; rows with no score fall to the end.
    query = query.order_by(nullslast(JobPosting.relevance_score.desc()))

    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    start = (page - 1) * page_size
    items = session.exec(query.offset(start).limit(page_size)).all()

    return JobsListResponse(
        items=[_to_response(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/filters", response_model=JobFiltersResponse)
def get_job_filters(
    search_job_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    postings = session.exec(
        select(JobPosting).where(
            JobPosting.user_id == current_user.id,
            JobPosting.search_job_id == search_job_id,
        )
    ).all()
    sources = sorted({p.source for p in postings})
    companies = sorted({p.company for p in postings if p.company})
    return JobFiltersResponse(sources=sources, companies=companies)


class ManualJobRequest(BaseModel):
    jd_text: str = Field(min_length=1, max_length=30_000)
    title: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)


@router.post("/manual")
@limiter.limit("5/minute")
async def create_manual_job(
    request: Request,
    body: ManualJobRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a synthetic job posting from a pasted JD and kick off the prepare pipeline.

    Defined before GET /{job_id} so the literal path segment "manual" is not
    parsed as a UUID (which would return 422).

    jd_text flows into sanitize_jd_text() inside _parse_jd() — the existing
    prompt-injection defence is preserved end-to-end without any additional handling here.
    """
    # Fail fast if no active resume exists (same pattern as POST /{job_id}/prepare).
    resume = session.exec(
        select(Resume).where(
            Resume.user_id == current_user.id,
            Resume.is_active == True,  # noqa: E712
        )
    ).first()
    if not resume:
        raise HTTPException(status_code=400, detail="No active resume — upload a resume first")

    try:
        posting = create_manual_application(
            body.jd_text, body.title, body.company, current_user.id, session
        )
    except ApplicationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    background_tasks.add_task(prepare_application_task, posting.id, current_user.id)
    logger.info("manual prepare queued: posting_id=%s title=%r", posting.id, posting.title)
    return {"status": "preparing", "job_id": str(posting.id)}


@router.get("/{job_id}", response_model=JobPostingResponse)
def get_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    posting = session.get(JobPosting, job_id)
    if not posting or posting.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return _to_response(posting)


@router.post("/{job_id}/prepare")
async def prepare_application(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Verify job exists and belongs to the caller
    posting = session.get(JobPosting, job_id)
    if not posting or posting.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job posting not found")

    # Verify there is an active resume before queueing — otherwise the background
    # task can't create an Application row and the client would poll a never-
    # appearing row. Fail fast with a clear error instead.
    resume = session.exec(
        select(Resume).where(
            Resume.user_id == current_user.id,
            Resume.is_active == True,  # noqa: E712
        )
    ).first()
    if not resume:
        raise HTTPException(status_code=400, detail="No active resume — upload a resume first")

    background_tasks.add_task(prepare_application_task, job_id, current_user.id)
    logger.info("prepare queued: job_id=%s title=%r", job_id, posting.title)
    return {"status": "preparing", "job_id": str(job_id)}
