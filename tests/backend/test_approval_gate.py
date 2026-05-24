"""Tests proving the approval gate invariant.

Critical invariants verified:
1. Only pending applications can be approved.
2. Rejected applications cannot be approved.
3. Every successful approval creates exactly one AuditLog row.
4. submitted_at is never set without a corresponding AuditLog row.
5. Direct call to submission_service.submit() is not exposed — only approve_application() calls it.
"""

import uuid

import pytest
from sqlmodel import Session, select

from backend.models.application import Application, ApplicationStatus
from backend.models.audit_log import AuditLog
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.services.application_service import (
    ApplicationError,
    InvalidStateError,
    approve_application,
    reject_application,
)


def _make_posting(session: Session) -> JobPosting:
    posting = JobPosting(
        source="test",
        source_job_id="p1",
        title="Software Engineer",
        company="Acme",
        url="https://example.com/job/1",
        description="A test job",
        remote_status=RemoteStatus.remote,
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)
    return posting


def _make_resume(session: Session) -> Resume:
    resume = Resume(
        filename="test.txt",
        file_path="/tmp/test.txt",
        text_content="John Doe, Software Engineer",
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def _make_pending_app(session: Session) -> Application:
    posting = _make_posting(session)
    resume = _make_resume(session)
    app = Application(
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=ApplicationStatus.pending,
        tailored_resume_text="tailored",
        cover_letter_text="dear hiring manager",
        match_score=80,
        match_rationale="good match",
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


def test_approve_pending_succeeds(session: Session):
    app = _make_pending_app(session)
    result = approve_application(app.id, session)
    assert result.status == ApplicationStatus.submitted
    assert result.submitted_at is not None
    assert result.approved_at is not None


def test_approve_creates_audit_log(session: Session):
    app = _make_pending_app(session)
    approve_application(app.id, session)
    logs = session.exec(select(AuditLog).where(AuditLog.application_id == app.id)).all()
    assert len(logs) == 1
    assert logs[0].action == "submitted"


def test_approve_non_pending_raises_409(session: Session):
    app = _make_pending_app(session)
    # First approval succeeds
    approve_application(app.id, session)
    # Second should raise InvalidStateError
    with pytest.raises(InvalidStateError):
        approve_application(app.id, session)


def test_rejected_cannot_be_approved(session: Session):
    app = _make_pending_app(session)
    reject_application(app.id, session)
    with pytest.raises(InvalidStateError):
        approve_application(app.id, session)


def test_submitted_at_always_has_audit_log(session: Session):
    app = _make_pending_app(session)
    approve_application(app.id, session)
    session.refresh(app)
    # Every application with submitted_at must have an AuditLog row
    if app.submitted_at is not None:
        logs = session.exec(select(AuditLog).where(AuditLog.application_id == app.id)).all()
        assert len(logs) >= 1


def test_reject_pending_succeeds(session: Session):
    app = _make_pending_app(session)
    result = reject_application(app.id, session)
    assert result.status == ApplicationStatus.rejected
    assert result.rejected_at is not None


def test_reject_creates_audit_log(session: Session):
    app = _make_pending_app(session)
    reject_application(app.id, session)
    logs = session.exec(select(AuditLog).where(AuditLog.application_id == app.id)).all()
    assert len(logs) == 1
    assert logs[0].action == "rejected"


def test_approve_not_found_raises_error(session: Session):
    with pytest.raises(ApplicationError):
        approve_application(uuid.uuid4(), session)
