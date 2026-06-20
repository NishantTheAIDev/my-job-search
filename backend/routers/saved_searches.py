import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.auth.dependencies import get_current_user
from backend.background.tasks import start_search_task
from backend.database import get_session
from backend.limiter import limiter
from backend.models.job_posting import SearchCriteria
from backend.models.saved_search import SavedSearch
from backend.models.search_job import SearchJob, SearchJobStatus
from backend.models.user import User
from backend.services.saved_search_service import diff_run

logger = logging.getLogger(__name__)
router = APIRouter()


class SavedSearchResponse(BaseModel):
    id: uuid.UUID
    name: str
    criteria: SearchCriteria
    created_at: datetime
    last_run_at: datetime | None
    last_search_job_id: uuid.UUID | None


class CreateSavedSearchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    criteria: SearchCriteria


class RunSavedSearchResponse(BaseModel):
    saved_search_id: uuid.UUID
    search_job_id: uuid.UUID
    status: SearchJobStatus


class SavedSearchDiffResponse(BaseModel):
    search_job_id: uuid.UUID
    new_count: int
    new_posting_ids: list[uuid.UUID]
    is_first_run: bool


def _to_response(s: SavedSearch) -> SavedSearchResponse:
    return SavedSearchResponse(
        id=s.id,
        name=s.name,
        criteria=SearchCriteria.model_validate_json(s.criteria_json),
        created_at=s.created_at,
        last_run_at=s.last_run_at,
        last_search_job_id=s.last_search_job_id,
    )


@router.post("", response_model=SavedSearchResponse)
def create_saved_search(
    body: CreateSavedSearchRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    saved = SavedSearch(
        user_id=current_user.id,
        name=body.name.strip(),
        criteria_json=body.criteria.model_dump_json(),
    )
    session.add(saved)
    session.commit()
    session.refresh(saved)
    logger.info("saved search created: id=%s name=%r", saved.id, saved.name)
    return _to_response(saved)


@router.get("", response_model=list[SavedSearchResponse])
def list_saved_searches(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rows = session.exec(
        select(SavedSearch)
        .where(SavedSearch.user_id == current_user.id)
        .order_by(SavedSearch.created_at.desc())
    ).all()
    return [_to_response(s) for s in rows]


@router.post("/{saved_search_id}/run", response_model=RunSavedSearchResponse)
@limiter.limit("5/minute")
async def run_saved_search(
    request: Request,
    saved_search_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    saved = session.get(SavedSearch, saved_search_id)
    if not saved or saved.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Saved search not found")

    criteria = SearchCriteria.model_validate_json(saved.criteria_json)
    # Always start a re-run from page 1 — the saved criteria's page is irrelevant.
    criteria.page = 1

    search_job = SearchJob(
        user_id=current_user.id,
        criteria_json=criteria.model_dump_json(),
        created_at=datetime.now(UTC),
    )
    session.add(search_job)
    session.commit()
    session.refresh(search_job)

    saved.last_run_at = datetime.now(UTC)
    saved.last_search_job_id = search_job.id
    session.add(saved)
    session.commit()

    background_tasks.add_task(start_search_task, search_job.id, criteria)
    logger.info(
        "saved search re-run: id=%s search_job_id=%s query=%r",
        saved.id,
        search_job.id,
        criteria.query,
    )
    return RunSavedSearchResponse(
        saved_search_id=saved.id,
        search_job_id=search_job.id,
        status=search_job.status,
    )


@router.post("/{saved_search_id}/diff", response_model=SavedSearchDiffResponse)
def diff_saved_search(
    saved_search_id: uuid.UUID,
    search_job_id: uuid.UUID = Query(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Diff a completed run against the baseline and advance the baseline.

    Idempotent per `search_job_id` — safe to call on every poll-to-complete.
    """
    saved = session.get(SavedSearch, saved_search_id)
    if not saved or saved.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Saved search not found")

    job = session.get(SearchJob, search_job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Search job not found")
    if job.status != SearchJobStatus.complete:
        raise HTTPException(status_code=409, detail="Search is not complete yet")

    new_ids, is_first_run = diff_run(saved, search_job_id, session)
    return SavedSearchDiffResponse(
        search_job_id=search_job_id,
        new_count=len(new_ids),
        new_posting_ids=new_ids,
        is_first_run=is_first_run,
    )


@router.delete("/{saved_search_id}")
def delete_saved_search(
    saved_search_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    saved = session.get(SavedSearch, saved_search_id)
    if not saved or saved.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Saved search not found")
    session.delete(saved)
    session.commit()
    logger.info("saved search deleted: id=%s", saved_search_id)
    return {"status": "deleted", "id": str(saved_search_id)}
