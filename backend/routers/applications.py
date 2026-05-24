"""Application management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.limiter import limiter
from backend.models.application import Application, ApplicationStatus
from backend.services.application_service import (
    ApplicationError,
    InvalidStateError,
    approve_application,
    reject_application,
)

router = APIRouter()


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    job_posting_id: uuid.UUID
    status: ApplicationStatus
    match_score: int
    match_rationale: str
    tailored_resume_text: str
    resume_diff_json: str
    cover_letter_text: str
    tailoring_failed: bool
    created_at: str
    approved_at: str | None
    submitted_at: str | None
    rejected_at: str | None


def _to_response(app: Application) -> ApplicationResponse:
    return ApplicationResponse(
        id=app.id,
        job_posting_id=app.job_posting_id,
        status=app.status,
        match_score=app.match_score,
        match_rationale=app.match_rationale,
        tailored_resume_text=app.tailored_resume_text,
        resume_diff_json=app.resume_diff_json,
        cover_letter_text=app.cover_letter_text,
        tailoring_failed=app.tailoring_failed,
        created_at=app.created_at.isoformat(),
        approved_at=app.approved_at.isoformat() if app.approved_at else None,
        submitted_at=app.submitted_at.isoformat() if app.submitted_at else None,
        rejected_at=app.rejected_at.isoformat() if app.rejected_at else None,
    )


@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    status: ApplicationStatus | None = None,
    session: Session = Depends(get_session),
):
    query = select(Application)
    if status:
        query = query.where(Application.status == status)
    return [_to_response(a) for a in session.exec(query).all()]


@router.get("/{app_id}", response_model=ApplicationResponse)
def get_application(app_id: uuid.UUID, session: Session = Depends(get_session)):
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return _to_response(app)


@router.post("/{app_id}/approve", response_model=ApplicationResponse)
@limiter.limit("20/minute")
def approve(request: Request, app_id: uuid.UUID, session: Session = Depends(get_session)):
    try:
        app = approve_application(app_id, session)
        return _to_response(app)
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ApplicationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{app_id}/reject", response_model=ApplicationResponse)
def reject(app_id: uuid.UUID, session: Session = Depends(get_session)):
    try:
        app = reject_application(app_id, session)
        return _to_response(app)
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ApplicationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
