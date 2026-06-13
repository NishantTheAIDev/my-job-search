"""Application management endpoints."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.database import get_session
from backend.limiter import limiter
from backend.models.application import Application, ApplicationStatus
from backend.services.application_service import (
    ApplicationError,
    InvalidStateError,
    approve_application,
    edit_application_content,
    reject_application,
    revise_application,
)

router = APIRouter()


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    job_posting_id: uuid.UUID
    status: ApplicationStatus
    prep_stage: str
    prep_error: str
    match_score: int
    match_rationale: str
    tailored_resume_text: str
    resume_diff_json: str
    cover_letter_text: str
    resume_data_yaml: str
    cover_letter_data_yaml: str
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
        prep_stage=app.prep_stage,
        prep_error=app.prep_error,
        match_score=app.match_score,
        match_rationale=app.match_rationale,
        tailored_resume_text=app.tailored_resume_text,
        resume_diff_json=app.resume_diff_json,
        cover_letter_text=app.cover_letter_text,
        resume_data_yaml=app.resume_data_yaml,
        cover_letter_data_yaml=app.cover_letter_data_yaml,
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


@router.get("/by-job/{job_posting_id}", response_model=ApplicationResponse)
def get_application_by_job(job_posting_id: uuid.UUID, session: Session = Depends(get_session)):
    """Resolve the most recent application for a job posting.

    The prepare pipeline runs in the background and creates the Application row
    only when it finishes, so the client polls this endpoint (keyed by the job
    posting id it already has) until the row exists, then uses the returned
    application id for approve/reject. Defined before ``/{app_id}`` so the
    literal "by-job" segment is not parsed as a UUID.
    """
    app = session.exec(
        select(Application)
        .where(Application.job_posting_id == job_posting_id)
        .order_by(Application.created_at.desc())
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return _to_response(app)


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


# Length caps bound LLM token cost per request (the rate limit alone does not cap
# payload size). Instructions are short directives; edited text is a full document.
class ReviseRequest(BaseModel):
    target: Literal["resume", "cover_letter"]
    instructions: str = Field(min_length=1, max_length=4_000)


class EditContentRequest(BaseModel):
    target: Literal["resume", "cover_letter"]
    text: str = Field(max_length=30_000)


@router.post("/{app_id}/revise", response_model=ApplicationResponse)
@limiter.limit("10/minute")
async def revise(
    request: Request,
    app_id: uuid.UUID,
    body: ReviseRequest,
    session: Session = Depends(get_session),
):
    """LLM-revise resume or cover letter given natural-language instructions."""
    try:
        app = await revise_application(app_id, body.target, body.instructions, session)
        return _to_response(app)
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ApplicationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{app_id}/content", response_model=ApplicationResponse)
@limiter.limit("10/minute")
async def edit_content(
    request: Request,
    app_id: uuid.UUID,
    body: EditContentRequest,
    session: Session = Depends(get_session),
):
    """Accept free-text edits, re-structure, and rebuild YAML + diff."""
    try:
        app = await edit_application_content(app_id, body.target, body.text, session)
        return _to_response(app)
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ApplicationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
