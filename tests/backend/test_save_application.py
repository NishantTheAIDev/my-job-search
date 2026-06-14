"""Tests for save_application and the save-gate invariant.

Critical invariants verified:
1. pending → saved sets status and saved_at.
2. save_application writes exactly one AuditLog row with action == "saved" in
   the same commit.
3. Non-pending applications cannot be saved (InvalidStateError / 409).
4. save_application MUST NOT call submission_service.submit — submission remains
   exclusively in approve_application.
5. approve_application is still the only path that calls submit.
"""

import uuid
from unittest.mock import MagicMock

import pytest
from sqlmodel import Session, select

from backend.models.application import Application, ApplicationStatus
from backend.models.audit_log import AuditLog
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.services.application_service import (
    ApplicationError,
    InvalidStateError,
    save_application,
)

# ---------------------------------------------------------------------------
# Helpers — mirror the pattern in test_approval_gate.py
# ---------------------------------------------------------------------------


def _make_posting(session: Session) -> JobPosting:
    posting = JobPosting(
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


def _make_resume(session: Session) -> Resume:
    resume = Resume(
        filename="test.txt",
        file_path="/tmp/test.txt",
        text_content="John Doe, Backend Engineer",
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
        match_score=77,
        match_rationale="good match",
        match_gaps='["Docker", "Kubernetes"]',
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


# ---------------------------------------------------------------------------
# save_application service tests
# ---------------------------------------------------------------------------


def test_save_pending_sets_status_to_saved(session: Session):
    app = _make_pending_app(session)
    result = save_application(app.id, session)
    assert result.status == ApplicationStatus.saved


def test_save_pending_sets_saved_at(session: Session):
    app = _make_pending_app(session)
    result = save_application(app.id, session)
    assert result.saved_at is not None


def test_save_creates_audit_log_with_saved_action(session: Session):
    app = _make_pending_app(session)
    save_application(app.id, session)
    logs = session.exec(select(AuditLog).where(AuditLog.application_id == app.id)).all()
    assert len(logs) == 1
    assert logs[0].action == "saved"


def test_save_non_pending_raises_invalid_state_error(session: Session):
    """A submitted application cannot be saved — only pending ones can."""
    app = _make_pending_app(session)
    # Manually push it to submitted state to simulate an already-processed app.
    app.status = ApplicationStatus.submitted
    session.add(app)
    session.commit()

    with pytest.raises(InvalidStateError):
        save_application(app.id, session)


def test_save_rejected_raises_invalid_state_error(session: Session):
    app = _make_pending_app(session)
    app.status = ApplicationStatus.rejected
    session.add(app)
    session.commit()

    with pytest.raises(InvalidStateError):
        save_application(app.id, session)


def test_save_already_saved_raises_invalid_state_error(session: Session):
    """Calling save twice on the same app must raise on the second call."""
    app = _make_pending_app(session)
    save_application(app.id, session)
    with pytest.raises(InvalidStateError):
        save_application(app.id, session)


def test_save_not_found_raises_application_error(session: Session):
    with pytest.raises(ApplicationError):
        save_application(uuid.uuid4(), session)


# ---------------------------------------------------------------------------
# Invariant: save_application MUST NOT call submission_service.submit
# ---------------------------------------------------------------------------


def test_save_does_not_call_submit(session: Session, monkeypatch):
    """The core save-gate invariant: save_application must never submit."""
    mock_submit = MagicMock()
    # Patch the symbol where it is imported inside approve_application's function body.
    import backend.services.submission_service as sub_svc

    monkeypatch.setattr(sub_svc, "submit", mock_submit)

    app = _make_pending_app(session)
    result = save_application(app.id, session)

    assert result.status == ApplicationStatus.saved
    mock_submit.assert_not_called()


def test_approve_calls_submit_but_save_does_not(session: Session, monkeypatch):
    """Confirm the two paths: approve calls submit; save does not."""
    call_log: list[str] = []

    def _fake_submit(app, posting, session):
        call_log.append("submit")

    import backend.services.submission_service as sub_svc

    monkeypatch.setattr(sub_svc, "submit", _fake_submit)

    # save path — must not invoke submit
    save_app = _make_pending_app(session)
    save_application(save_app.id, session)
    assert call_log == [], "save_application must not call submit"

    # approve path on a fresh pending app — must invoke submit exactly once
    from backend.services.application_service import approve_application

    approve_app = _make_pending_app(session)
    approve_application(approve_app.id, session)
    assert call_log == ["submit"], "approve_application must call submit exactly once"
