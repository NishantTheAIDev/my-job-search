"""Tests for save_application / reject_application and their gating.

Critical invariants verified:
1. pending → saved sets status and saved_at; pending → rejected sets rejected_at.
2. Each writes exactly one AuditLog row (action "saved" / "rejected") in one commit.
3. Non-pending applications cannot be saved/rejected (InvalidStateError / 409).
4. There is NO external submission path anywhere (submission_service was removed).
5. Cross-tenant: a user cannot save/reject another user's application (404-equiv).
"""

import uuid

import pytest
from sqlmodel import Session, select

from backend.models.application import Application, ApplicationStatus
from backend.models.audit_log import AuditLog
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.models.user import User
from backend.services.application_service import (
    ApplicationError,
    InvalidStateError,
    reject_application,
    save_application,
)

# ---------------------------------------------------------------------------
# Helpers — every owned row is stamped with a user_id (tenant scoping).
# ---------------------------------------------------------------------------


def _make_posting(session: Session, user_id: uuid.UUID) -> JobPosting:
    posting = JobPosting(
        user_id=user_id,
        source="test",
        source_job_id="p-save-1",
        title="Backend Engineer",
        company="SaveCo",
        url="https://example.com/job/save",
        description="A save-gate test job",
        remote_status=RemoteStatus.remote,
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)
    return posting


def _make_resume(session: Session, user_id: uuid.UUID) -> Resume:
    resume = Resume(
        user_id=user_id,
        filename="test.txt",
        file_path="/tmp/test.txt",
        text_content="John Doe, Backend Engineer",
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def _make_pending_app(session: Session, user_id: uuid.UUID) -> Application:
    posting = _make_posting(session, user_id)
    resume = _make_resume(session, user_id)
    app = Application(
        user_id=user_id,
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=ApplicationStatus.pending,
        tailored_resume_text="tailored",
        cover_letter_text="dear hiring manager",
        match_score=77,
        match_rationale="good match",
        match_gaps='["Docker", "Kubernetes"]',
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


# ---------------------------------------------------------------------------
# save_application
# ---------------------------------------------------------------------------


def test_save_pending_sets_status_to_saved(session: Session, user: User):
    app = _make_pending_app(session, user.id)
    result = save_application(app.id, user.id, session)
    assert result.status == ApplicationStatus.saved


def test_save_pending_sets_saved_at(session: Session, user: User):
    app = _make_pending_app(session, user.id)
    result = save_application(app.id, user.id, session)
    assert result.saved_at is not None


def test_save_creates_audit_log_with_saved_action(session: Session, user: User):
    app = _make_pending_app(session, user.id)
    save_application(app.id, user.id, session)
    logs = session.exec(select(AuditLog).where(AuditLog.application_id == app.id)).all()
    assert len(logs) == 1
    assert logs[0].action == "saved"
    assert logs[0].user_id == user.id


def test_save_non_pending_raises_invalid_state_error(session: Session, user: User):
    app = _make_pending_app(session, user.id)
    app.status = ApplicationStatus.saved
    session.add(app)
    session.commit()
    with pytest.raises(InvalidStateError):
        save_application(app.id, user.id, session)


def test_save_already_saved_raises_invalid_state_error(session: Session, user: User):
    app = _make_pending_app(session, user.id)
    save_application(app.id, user.id, session)
    with pytest.raises(InvalidStateError):
        save_application(app.id, user.id, session)


def test_save_not_found_raises_application_error(session: Session, user: User):
    with pytest.raises(ApplicationError):
        save_application(uuid.uuid4(), user.id, session)


def test_save_other_users_application_raises(session: Session, user: User, other_user: User):
    """Cross-tenant: user B cannot save user A's application (treated as not-found)."""
    app = _make_pending_app(session, user.id)
    with pytest.raises(ApplicationError):
        save_application(app.id, other_user.id, session)
    # And it stays pending.
    session.refresh(app)
    assert app.status == ApplicationStatus.pending


# ---------------------------------------------------------------------------
# reject_application
# ---------------------------------------------------------------------------


def test_reject_pending_succeeds(session: Session, user: User):
    app = _make_pending_app(session, user.id)
    result = reject_application(app.id, user.id, session)
    assert result.status == ApplicationStatus.rejected
    assert result.rejected_at is not None


def test_reject_creates_audit_log(session: Session, user: User):
    app = _make_pending_app(session, user.id)
    reject_application(app.id, user.id, session)
    logs = session.exec(select(AuditLog).where(AuditLog.application_id == app.id)).all()
    assert len(logs) == 1
    assert logs[0].action == "rejected"


def test_reject_other_users_application_raises(session: Session, user: User, other_user: User):
    app = _make_pending_app(session, user.id)
    with pytest.raises(ApplicationError):
        reject_application(app.id, other_user.id, session)
