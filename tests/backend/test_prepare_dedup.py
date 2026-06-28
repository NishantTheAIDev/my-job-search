"""Router-level tests for POST /jobs/{job_id}/prepare idempotency (dedup).

Re-clicking "Prepare application" on the same job — e.g. after going back to the
results list — must NOT spawn a second concurrent prepare pipeline while an
earlier one is still in flight (status=preparing) or awaiting review
(status=pending). Terminal/failed states (saved, rejected, prep_failed) fall
through so the user can deliberately re-prepare.
"""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.models.application import Application, ApplicationStatus
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.models.user import User


def _make_posting(session: Session, user_id: uuid.UUID) -> JobPosting:
    posting = JobPosting(
        user_id=user_id,
        source="test",
        source_job_id=str(uuid.uuid4()),
        title="Software Engineer",
        company="DedupCo",
        url="https://example.com/job/d",
        description="A dedup-test job",
        remote_status=RemoteStatus.remote,
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)
    return posting


def _make_resume(session: Session, user_id: uuid.UUID) -> Resume:
    resume = Resume(
        user_id=user_id,
        filename="resume.txt",
        file_path="/tmp/resume.txt",
        text_content="Jane Doe\nEngineer",
        is_active=True,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def _make_app(
    session: Session,
    user_id: uuid.UUID,
    posting: JobPosting,
    resume: Resume,
    status: ApplicationStatus,
) -> Application:
    app = Application(
        user_id=user_id,
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=status,
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


def test_prepare_reuses_in_flight_preparing_application(
    client: TestClient, session: Session, user: User
):
    """An existing preparing app → no new task queued, status echoed back."""
    posting = _make_posting(session, user.id)
    resume = _make_resume(session, user.id)
    _make_app(session, user.id, posting, resume, ApplicationStatus.preparing)

    with patch("backend.routers.jobs.prepare_application_task") as task:
        resp = client.post(f"/jobs/{posting.id}/prepare")

    assert resp.status_code == 200
    assert resp.json()["status"] == "preparing"
    task.assert_not_called()


def test_prepare_reuses_pending_application(client: TestClient, session: Session, user: User):
    """An existing pending (ready, un-actioned) app → no new task queued."""
    posting = _make_posting(session, user.id)
    resume = _make_resume(session, user.id)
    _make_app(session, user.id, posting, resume, ApplicationStatus.pending)

    with patch("backend.routers.jobs.prepare_application_task") as task:
        resp = client.post(f"/jobs/{posting.id}/prepare")

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
    task.assert_not_called()


def test_prepare_queues_task_when_no_existing_application(
    client: TestClient, session: Session, user: User
):
    """No prior app → the background prepare task is queued once."""
    posting = _make_posting(session, user.id)
    _make_resume(session, user.id)

    with patch("backend.routers.jobs.prepare_application_task") as task:
        resp = client.post(f"/jobs/{posting.id}/prepare")

    assert resp.status_code == 200
    assert resp.json()["status"] == "preparing"
    task.assert_called_once()


def test_prepare_requeues_after_terminal_state(client: TestClient, session: Session, user: User):
    """A terminal (rejected) app does not block a fresh prepare."""
    posting = _make_posting(session, user.id)
    resume = _make_resume(session, user.id)
    _make_app(session, user.id, posting, resume, ApplicationStatus.rejected)

    with patch("backend.routers.jobs.prepare_application_task") as task:
        resp = client.post(f"/jobs/{posting.id}/prepare")

    assert resp.status_code == 200
    assert resp.json()["status"] == "preparing"
    task.assert_called_once()


def test_prepare_requeues_after_prep_failed(client: TestClient, session: Session, user: User):
    """A prep_failed app does not block a retry."""
    posting = _make_posting(session, user.id)
    resume = _make_resume(session, user.id)
    _make_app(session, user.id, posting, resume, ApplicationStatus.prep_failed)

    with patch("backend.routers.jobs.prepare_application_task") as task:
        resp = client.post(f"/jobs/{posting.id}/prepare")

    assert resp.status_code == 200
    assert resp.json()["status"] == "preparing"
    task.assert_called_once()
