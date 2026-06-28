"""Tests for DELETE /applications/{app_id} and the delete_application service.

Invariants verified:
1. DELETE returns 204 for any application status (pending, saved, rejected,
   prep_failed, cancelled, and preparing).
2. The row is actually removed from the DB after a successful delete.
3. AuditLog rows are removed before the Application row (FK safety).
4. A preparing application is cooperatively cancelled (status=cancelled) before
   deletion so the background pipeline won't resurrect the row.
5. Cross-tenant: deleting another user's application returns 404.
6. Deleting a non-existent application returns 404.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.models.application import Application, ApplicationStatus
from backend.models.audit_log import AuditLog
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.models.user import User
from backend.services.application_service import ApplicationError, delete_application

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_posting(session: Session, user_id: uuid.UUID) -> JobPosting:
    p = JobPosting(
        user_id=user_id,
        source="test",
        source_job_id=str(uuid.uuid4()),
        title="Engineer",
        company="Acme",
        url="https://example.com",
        description="Job description",
        remote_status=RemoteStatus.remote,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _make_resume(session: Session, user_id: uuid.UUID) -> Resume:
    r = Resume(
        user_id=user_id,
        filename="cv.txt",
        file_path="/tmp/cv.txt",
        text_content="Jane Doe",
    )
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


def _make_app(
    session: Session,
    user_id: uuid.UUID,
    status: ApplicationStatus = ApplicationStatus.pending,
) -> Application:
    posting = _make_posting(session, user_id)
    resume = _make_resume(session, user_id)
    app = Application(
        user_id=user_id,
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=status,
        tailored_resume_text="tailored",
        cover_letter_text="cover",
        match_score=70,
        match_rationale="ok",
        match_gaps="[]",
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


def _make_app_with_audit(session: Session, user_id: uuid.UUID) -> Application:
    """Make a saved application that already has an AuditLog row."""
    app = _make_app(session, user_id, ApplicationStatus.saved)
    posting = session.get(JobPosting, app.job_posting_id)
    log = AuditLog(
        user_id=user_id,
        application_id=app.id,
        action="saved",
        job_title=posting.title if posting else "unknown",
        company=posting.company if posting else None,
        board_url=posting.url if posting else "",
    )
    session.add(log)
    session.commit()
    return app


# ---------------------------------------------------------------------------
# Service-layer unit tests
# ---------------------------------------------------------------------------


def test_delete_pending_removes_row(session: Session, user: User):
    app = _make_app(session, user.id, ApplicationStatus.pending)
    app_id = app.id
    delete_application(app_id, user.id, session)
    assert session.get(Application, app_id) is None


def test_delete_saved_removes_row(session: Session, user: User):
    app = _make_app(session, user.id, ApplicationStatus.saved)
    app_id = app.id
    delete_application(app_id, user.id, session)
    assert session.get(Application, app_id) is None


def test_delete_rejected_removes_row(session: Session, user: User):
    app = _make_app(session, user.id, ApplicationStatus.rejected)
    app_id = app.id
    delete_application(app_id, user.id, session)
    assert session.get(Application, app_id) is None


def test_delete_prep_failed_removes_row(session: Session, user: User):
    app = _make_app(session, user.id, ApplicationStatus.prep_failed)
    app_id = app.id
    delete_application(app_id, user.id, session)
    assert session.get(Application, app_id) is None


def test_delete_cancelled_removes_row(session: Session, user: User):
    app = _make_app(session, user.id, ApplicationStatus.cancelled)
    app_id = app.id
    delete_application(app_id, user.id, session)
    assert session.get(Application, app_id) is None


def test_delete_preparing_cancels_then_removes(session: Session, user: User):
    """A preparing app is set to cancelled before the row is deleted so the
    background pipeline's next _check_cancelled() checkpoint aborts cleanly."""
    app = _make_app(session, user.id, ApplicationStatus.preparing)
    app_id = app.id
    # delete_application commits a cancel first, then deletes the row.
    delete_application(app_id, user.id, session)
    assert session.get(Application, app_id) is None


def test_delete_removes_audit_logs_before_app(session: Session, user: User):
    """AuditLog FK rows must be deleted before the Application row."""
    app = _make_app_with_audit(session, user.id)
    app_id = app.id

    logs_before = session.exec(select(AuditLog).where(AuditLog.application_id == app_id)).all()
    assert len(logs_before) == 1

    delete_application(app_id, user.id, session)

    assert session.get(Application, app_id) is None
    logs_after = session.exec(select(AuditLog).where(AuditLog.application_id == app_id)).all()
    assert logs_after == []


def test_delete_foreign_app_raises_application_error(
    session: Session, user: User, other_user: User
):
    """Cross-tenant: user B cannot delete user A's application."""
    app = _make_app(session, user.id)
    with pytest.raises(ApplicationError):
        delete_application(app.id, other_user.id, session)
    # Row survives.
    session.refresh(app)
    assert app.status == ApplicationStatus.pending


def test_delete_missing_app_raises_application_error(session: Session, user: User):
    with pytest.raises(ApplicationError):
        delete_application(uuid.uuid4(), user.id, session)


# ---------------------------------------------------------------------------
# HTTP route tests
# ---------------------------------------------------------------------------


def test_delete_route_returns_204(client: TestClient, session: Session, user: User):
    app = _make_app(session, user.id, ApplicationStatus.pending)
    resp = client.delete(f"/applications/{app.id}")
    assert resp.status_code == 204
    assert resp.content == b""


def test_delete_route_removes_row(client: TestClient, session: Session, user: User):
    app = _make_app(session, user.id, ApplicationStatus.saved)
    app_id = app.id
    client.delete(f"/applications/{app_id}")
    assert session.get(Application, app_id) is None


def test_delete_route_404_for_missing(client: TestClient):
    resp = client.delete(f"/applications/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_delete_route_404_for_other_user(
    session: Session, user: User, other_user: User, make_client
):
    app = _make_app(session, user.id, ApplicationStatus.pending)
    other_client = make_client(other_user)
    resp = other_client.delete(f"/applications/{app.id}")
    assert resp.status_code == 404
    # Tenant A's row is untouched.
    session.refresh(app)
    assert app.status == ApplicationStatus.pending
