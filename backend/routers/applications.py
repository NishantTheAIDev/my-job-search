"""Application management endpoints."""

import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.auth.dependencies import get_current_user
from backend.database import get_session
from backend.limiter import limiter
from backend.models.application import Application, ApplicationStatus
from backend.models.job_posting import JobPosting
from backend.models.user import User
from backend.services.application_service import (
    ApplicationError,
    InvalidStateError,
    cancel_preparing_application,
    delete_application,
    edit_application_content,
    reject_application,
    revert_application_content,
    revise_application,
    save_application,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# cancel_preparing_application is referenced below at POST /{app_id}/cancel
# ---------------------------------------------------------------------------


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    job_posting_id: uuid.UUID
    status: ApplicationStatus
    prep_stage: str
    prep_error: str
    match_score: int
    match_rationale: str
    match_gaps: list[str]
    tailored_resume_text: str
    ai_tailored_resume_text: str
    resume_diff_json: str
    cover_letter_text: str
    ai_cover_letter_text: str
    resume_data_yaml: str
    cover_letter_data_yaml: str
    tailoring_failed: bool
    created_at: str
    approved_at: str | None
    submitted_at: str | None
    rejected_at: str | None
    saved_at: str | None


class SavedApplicationItem(BaseModel):
    id: uuid.UUID
    job_title: str
    company: str | None
    location: str | None
    match_score: int
    saved_at: str | None


class InProgressApplicationItem(BaseModel):
    """Summary item for an application that is still preparing or awaiting review.

    Returned by GET /applications/in-progress so a user who navigated away
    from a prepare can find and resume it. job_posting_id is required because
    the frontend workspace is keyed by that id.
    """

    id: uuid.UUID
    job_posting_id: uuid.UUID
    job_title: str
    company: str | None
    location: str | None
    status: ApplicationStatus
    match_score: int
    created_at: str


def _to_response(app: Application) -> ApplicationResponse:
    try:
        gaps: list[str] = json.loads(app.match_gaps)
        if not isinstance(gaps, list):
            gaps = []
    except json.JSONDecodeError, TypeError:
        gaps = []
    return ApplicationResponse(
        id=app.id,
        job_posting_id=app.job_posting_id,
        status=app.status,
        prep_stage=app.prep_stage,
        prep_error=app.prep_error,
        match_score=app.match_score,
        match_rationale=app.match_rationale,
        match_gaps=gaps,
        tailored_resume_text=app.tailored_resume_text,
        ai_tailored_resume_text=app.ai_tailored_resume_text,
        resume_diff_json=app.resume_diff_json,
        cover_letter_text=app.cover_letter_text,
        ai_cover_letter_text=app.ai_cover_letter_text,
        resume_data_yaml=app.resume_data_yaml,
        cover_letter_data_yaml=app.cover_letter_data_yaml,
        tailoring_failed=app.tailoring_failed,
        created_at=app.created_at.isoformat(),
        approved_at=app.approved_at.isoformat() if app.approved_at else None,
        submitted_at=app.submitted_at.isoformat() if app.submitted_at else None,
        rejected_at=app.rejected_at.isoformat() if app.rejected_at else None,
        saved_at=app.saved_at.isoformat() if app.saved_at else None,
    )


@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    status: ApplicationStatus | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    query = select(Application).where(Application.user_id == current_user.id)
    if status:
        query = query.where(Application.status == status)
    return [_to_response(a) for a in session.exec(query).all()]


@router.get("/saved", response_model=list[SavedApplicationItem])
def list_saved_applications(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return the user's saved applications ordered by saved_at descending.

    Defined before GET /{app_id} and GET /by-job/... so the literal path
    segment "saved" is not shadowed by the UUID catch-all route.
    """
    apps = session.exec(
        select(Application)
        .where(
            Application.user_id == current_user.id,
            Application.status == ApplicationStatus.saved,
        )
        .order_by(Application.saved_at.desc())
    ).all()
    items: list[SavedApplicationItem] = []
    for app in apps:
        posting = session.get(JobPosting, app.job_posting_id)
        items.append(
            SavedApplicationItem(
                id=app.id,
                job_title=posting.title if posting else "Unknown",
                company=posting.company if posting else None,
                location=posting.location if posting else None,
                match_score=app.match_score,
                saved_at=app.saved_at.isoformat() if app.saved_at else None,
            )
        )
    return items


@router.get("/in-progress", response_model=list[InProgressApplicationItem])
def list_in_progress_applications(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return applications in preparing or pending state, ordered by created_at desc.

    Lets a user who navigated away from a Tailor-from-JD prepare find it again.
    Does NOT include cancelled, prep_failed, saved, or rejected rows.
    Defined before GET /{app_id} so the literal segment is not parsed as a UUID.
    """
    apps = session.exec(
        select(Application)
        .where(
            Application.user_id == current_user.id,
            Application.status.in_(  # type: ignore[attr-defined]
                [ApplicationStatus.preparing, ApplicationStatus.pending]
            ),
        )
        .order_by(Application.created_at.desc())
    ).all()
    items: list[InProgressApplicationItem] = []
    for app in apps:
        posting = session.get(JobPosting, app.job_posting_id)
        items.append(
            InProgressApplicationItem(
                id=app.id,
                job_posting_id=app.job_posting_id,
                job_title=posting.title if posting else "Unknown",
                company=posting.company if posting else None,
                location=posting.location if posting else None,
                status=app.status,
                match_score=app.match_score,
                created_at=app.created_at.isoformat(),
            )
        )
    return items


@router.get("/by-job/{job_posting_id}", response_model=ApplicationResponse)
def get_application_by_job(
    job_posting_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Resolve the most recent application for a job posting.

    The prepare pipeline runs in the background and creates the Application row
    only when it finishes, so the client polls this endpoint (keyed by the job
    posting id it already has) until the row exists, then uses the returned
    application id for save/reject. Defined before ``/{app_id}`` so the
    literal "by-job" segment is not parsed as a UUID.
    """
    app = session.exec(
        select(Application)
        .where(
            Application.user_id == current_user.id,
            Application.job_posting_id == job_posting_id,
        )
        .order_by(Application.created_at.desc())
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return _to_response(app)


@router.get("/{app_id}", response_model=ApplicationResponse)
def get_application(
    app_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    app = session.get(Application, app_id)
    if not app or app.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Application not found")
    return _to_response(app)


@router.post("/{app_id}/reject", response_model=ApplicationResponse)
def reject(
    app_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    try:
        app = reject_application(app_id, current_user.id, session)
        return _to_response(app)
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ApplicationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{app_id}/save", response_model=ApplicationResponse)
@limiter.limit("20/minute")
def save(
    request: Request,
    app_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Approve & Save — persist the tailored result. This is the terminal user
    action; the app never submits to an external job board.

    Transitions pending → saved (terminal). Writes an AuditLog row in the same
    commit.
    """
    try:
        app = save_application(app_id, current_user.id, session)
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
    current_user: User = Depends(get_current_user),
):
    """LLM-revise resume or cover letter given natural-language instructions."""
    try:
        app = await revise_application(
            app_id, body.target, body.instructions, current_user.id, session
        )
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
    current_user: User = Depends(get_current_user),
):
    """Accept free-text edits, re-structure, and rebuild YAML + diff."""
    try:
        app = await edit_application_content(
            app_id, body.target, body.text, current_user.id, session
        )
        return _to_response(app)
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ApplicationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class RevertRequest(BaseModel):
    target: Literal["resume", "cover_letter"]
    to: Literal["original", "ai_draft"]


@router.post("/{app_id}/revert", response_model=ApplicationResponse)
@limiter.limit("10/minute")
def revert(
    request: Request,
    app_id: uuid.UUID,
    body: RevertRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Revert the current resume or cover letter text to a prior baseline.

    ``target=resume, to=original``  — restores the originally uploaded resume text.
    ``target=resume, to=ai_draft``  — restores the last AI-generated tailored resume.
    ``target=cover_letter, to=ai_draft`` — restores the last AI-generated cover letter.
    ``target=cover_letter, to=original`` is invalid (422) — no cover-letter original exists.

    Only callable while the application is in ``pending`` status.
    """
    if body.target == "cover_letter" and body.to == "original":
        raise HTTPException(
            status_code=422,
            detail=(
                "Cannot revert cover letter to 'original' — cover letters have no uploaded original"
            ),
        )
    try:
        app = revert_application_content(app_id, body.target, body.to, current_user.id, session)
        return _to_response(app)
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ApplicationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{app_id}/cancel", response_model=ApplicationResponse)
@limiter.limit("20/minute")
def cancel(
    request: Request,
    app_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Cooperative cancellation of an in-flight prepare pipeline.

    Sets status=cancelled so the background task's next _check_cancelled()
    checkpoint aborts before the next LLM call. Only valid while status==preparing;
    any other status returns 409. A cancelled application falls through the prepare
    dedup guard, so the user can re-prepare after cancelling.
    """
    try:
        app = cancel_preparing_application(app_id, current_user.id, session)
        return _to_response(app)
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ApplicationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{app_id}", status_code=204)
@limiter.limit("20/minute")
def delete(
    request: Request,
    app_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete an application regardless of status.

    If the application is currently preparing, cooperatively cancels it first
    so the background pipeline aborts at its next _check_cancelled() checkpoint
    rather than overwriting the deletion with a pending transition.

    AuditLog rows are deleted before the Application row to satisfy the FK
    constraint. Returns 204 No Content on success; 404 if the application does
    not exist or belongs to another user.
    """
    try:
        delete_application(app_id, current_user.id, session)
        return Response(status_code=204)
    except ApplicationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
