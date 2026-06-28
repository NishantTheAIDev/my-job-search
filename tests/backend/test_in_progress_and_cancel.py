"""Tests for GET /applications/in-progress and POST /applications/{id}/cancel.

Also covers the service-level cooperative cancellation inside prepare_application.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.models.application import Application, ApplicationStatus
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.models.user import User
from backend.services import (
    application_service,
    drafting_service,
    scoring_service,
    tailoring_service,
)
from backend.services.application_service import (
    ApplicationError,
    InvalidStateError,
    cancel_preparing_application,
    prepare_application,
)

# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _make_posting(
    session: Session,
    user_id: uuid.UUID,
    *,
    title: str = "Software Engineer",
    company: str = "Acme",
    location: str = "Remote",
) -> JobPosting:
    posting = JobPosting(
        user_id=user_id,
        source="test",
        source_job_id=str(uuid.uuid4()),
        title=title,
        company=company,
        location=location,
        url="https://example.com/job/1",
        description="A test job description",
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
        text_content="Original resume text",
        is_active=True,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def _make_app(
    session: Session,
    user_id: uuid.UUID,
    status: ApplicationStatus,
    *,
    title: str = "Software Engineer",
    company: str = "Acme",
    location: str = "Remote",
    match_score: int = 75,
) -> Application:
    posting = _make_posting(session, user_id, title=title, company=company, location=location)
    resume = _make_resume(session, user_id)
    app = Application(
        user_id=user_id,
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=status,
        match_score=match_score,
        tailored_resume_text="tailored",
        cover_letter_text="cover letter",
        match_rationale="good match",
        match_gaps="[]",
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


def _make_preparing_app(
    session: Session,
    user_id: uuid.UUID,
    *,
    title: str = "Software Engineer",
    company: str = "Acme",
) -> Application:
    return _make_app(session, user_id, ApplicationStatus.preparing, title=title, company=company)


def _make_pending_app(session: Session, user_id: uuid.UUID) -> Application:
    return _make_app(session, user_id, ApplicationStatus.pending)


# ---------------------------------------------------------------------------
# GET /applications/in-progress
# ---------------------------------------------------------------------------


class TestListInProgress:
    def test_empty_list_when_none(self, client: TestClient):
        response = client.get("/applications/in-progress")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_preparing_and_pending(self, client: TestClient, session: Session, user: User):
        preparing = _make_preparing_app(session, user.id, title="Dev A", company="Corp A")
        pending = _make_pending_app(session, user.id)
        response = client.get("/applications/in-progress")
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()}
        assert str(preparing.id) in ids
        assert str(pending.id) in ids

    def test_excludes_saved(self, client: TestClient, session: Session, user: User):
        saved = _make_app(session, user.id, ApplicationStatus.saved)
        response = client.get("/applications/in-progress")
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()}
        assert str(saved.id) not in ids

    def test_excludes_rejected(self, client: TestClient, session: Session, user: User):
        rejected = _make_app(session, user.id, ApplicationStatus.rejected)
        response = client.get("/applications/in-progress")
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()}
        assert str(rejected.id) not in ids

    def test_excludes_prep_failed(self, client: TestClient, session: Session, user: User):
        failed = _make_app(session, user.id, ApplicationStatus.prep_failed)
        response = client.get("/applications/in-progress")
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()}
        assert str(failed.id) not in ids

    def test_excludes_cancelled(self, client: TestClient, session: Session, user: User):
        cancelled = _make_app(session, user.id, ApplicationStatus.cancelled)
        response = client.get("/applications/in-progress")
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()}
        assert str(cancelled.id) not in ids

    def test_item_shape_includes_required_fields(
        self, client: TestClient, session: Session, user: User
    ):
        app = _make_preparing_app(session, user.id, title="ML Engineer", company="BrainCo")
        response = client.get("/applications/in-progress")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        item = items[0]
        # The frontend workspace is keyed by job_posting_id
        assert "job_posting_id" in item
        assert item["job_posting_id"] == str(app.job_posting_id)
        assert item["status"] in ("preparing", "pending")
        assert item["job_title"] == "ML Engineer"
        assert item["company"] == "BrainCo"
        assert "match_score" in item
        assert "created_at" in item

    def test_newest_first(self, client: TestClient, session: Session, user: User):
        from datetime import UTC, datetime, timedelta

        # Create two apps and manually set created_at so we control ordering
        older = _make_preparing_app(session, user.id, title="Older Job", company="Alpha")
        newer = _make_pending_app(session, user.id)

        older.created_at = datetime.now(UTC) - timedelta(hours=2)
        newer.created_at = datetime.now(UTC)
        session.add(older)
        session.add(newer)
        session.commit()

        response = client.get("/applications/in-progress")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2
        assert items[0]["id"] == str(newer.id)
        assert items[1]["id"] == str(older.id)

    def test_tenant_scoped_other_user_rows_absent(
        self,
        session: Session,
        user: User,
        other_user: User,
        make_client: object,
    ):
        """User B's in-progress apps must not appear in user A's response."""
        _make_preparing_app(session, other_user.id, title="Other's Job", company="OtherCo")
        client_a = make_client(user)
        response = client_a.get("/applications/in-progress")
        assert response.status_code == 200
        assert response.json() == []

    def test_only_own_rows_returned(
        self,
        session: Session,
        user: User,
        other_user: User,
        make_client: object,
    ):
        """User A's apps appear for A even when user B also has in-progress apps."""
        own_app = _make_pending_app(session, user.id)
        _make_preparing_app(session, other_user.id)
        client_a = make_client(user)
        response = client_a.get("/applications/in-progress")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert items[0]["id"] == str(own_app.id)


# ---------------------------------------------------------------------------
# POST /applications/{id}/cancel — HTTP route
# ---------------------------------------------------------------------------


class TestCancelRoute:
    def test_cancel_preparing_returns_200_and_cancelled_status(
        self, client: TestClient, session: Session, user: User
    ):
        app = _make_preparing_app(session, user.id)
        response = client.post(f"/applications/{app.id}/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    def test_cancel_clears_prep_stage(self, client: TestClient, session: Session, user: User):
        app = _make_preparing_app(session, user.id)
        app.prep_stage = "tailoring"
        session.add(app)
        session.commit()
        response = client.post(f"/applications/{app.id}/cancel")
        assert response.status_code == 200
        assert response.json()["prep_stage"] == ""

    def test_cancel_pending_returns_409(self, client: TestClient, session: Session, user: User):
        app = _make_pending_app(session, user.id)
        response = client.post(f"/applications/{app.id}/cancel")
        assert response.status_code == 409

    def test_cancel_saved_returns_409(self, client: TestClient, session: Session, user: User):
        app = _make_app(session, user.id, ApplicationStatus.saved)
        response = client.post(f"/applications/{app.id}/cancel")
        assert response.status_code == 409

    def test_cancel_rejected_returns_409(self, client: TestClient, session: Session, user: User):
        app = _make_app(session, user.id, ApplicationStatus.rejected)
        response = client.post(f"/applications/{app.id}/cancel")
        assert response.status_code == 409

    def test_cancel_prep_failed_returns_409(self, client: TestClient, session: Session, user: User):
        app = _make_app(session, user.id, ApplicationStatus.prep_failed)
        response = client.post(f"/applications/{app.id}/cancel")
        assert response.status_code == 409

    def test_cancel_unknown_id_returns_404(self, client: TestClient):
        response = client.post(f"/applications/{uuid.uuid4()}/cancel")
        assert response.status_code == 404

    def test_cancel_other_users_app_returns_404(
        self,
        session: Session,
        user: User,
        other_user: User,
        make_client: object,
    ):
        """Cross-tenant: B cannot cancel A's application."""
        app = _make_preparing_app(session, user.id)
        client_b = make_client(other_user)
        response = client_b.post(f"/applications/{app.id}/cancel")
        assert response.status_code == 404
        # App must still be preparing
        session.refresh(app)
        assert app.status == ApplicationStatus.preparing


# ---------------------------------------------------------------------------
# cancel_preparing_application — service-layer unit tests
# ---------------------------------------------------------------------------


class TestCancelService:
    def test_preparing_transitions_to_cancelled(self, session: Session, user: User):
        app = _make_preparing_app(session, user.id)
        result = cancel_preparing_application(app.id, user.id, session)
        assert result.status == ApplicationStatus.cancelled
        assert result.prep_stage == ""

    def test_pending_raises_invalid_state_error(self, session: Session, user: User):
        app = _make_pending_app(session, user.id)
        with pytest.raises(InvalidStateError):
            cancel_preparing_application(app.id, user.id, session)

    def test_saved_raises_invalid_state_error(self, session: Session, user: User):
        app = _make_app(session, user.id, ApplicationStatus.saved)
        with pytest.raises(InvalidStateError):
            cancel_preparing_application(app.id, user.id, session)

    def test_rejected_raises_invalid_state_error(self, session: Session, user: User):
        app = _make_app(session, user.id, ApplicationStatus.rejected)
        with pytest.raises(InvalidStateError):
            cancel_preparing_application(app.id, user.id, session)

    def test_prep_failed_raises_invalid_state_error(self, session: Session, user: User):
        app = _make_app(session, user.id, ApplicationStatus.prep_failed)
        with pytest.raises(InvalidStateError):
            cancel_preparing_application(app.id, user.id, session)

    def test_foreign_app_raises_application_error(
        self, session: Session, user: User, other_user: User
    ):
        app = _make_preparing_app(session, other_user.id)
        with pytest.raises(ApplicationError):
            cancel_preparing_application(app.id, user.id, session)

    def test_missing_app_raises_application_error(self, session: Session, user: User):
        with pytest.raises(ApplicationError):
            cancel_preparing_application(uuid.uuid4(), user.id, session)


# ---------------------------------------------------------------------------
# Cooperative cancellation inside prepare_application (service-level)
# ---------------------------------------------------------------------------


def _seed_for_prepare(session: Session, user_id: uuid.UUID) -> JobPosting:
    """Set up active resume + job posting; return the posting."""
    resume = Resume(
        user_id=user_id,
        filename="r.txt",
        file_path="/tmp/r.txt",
        text_content="original resume",
        is_active=True,
    )
    posting = JobPosting(
        user_id=user_id,
        source="test",
        source_job_id=str(uuid.uuid4()),
        title="Data Engineer",
        company="DataCo",
        url="https://example.com/job/de",
        description="A data engineering job",
        remote_status=RemoteStatus.remote,
    )
    session.add(resume)
    session.add(posting)
    session.commit()
    session.refresh(posting)
    return posting


def _patch_pipeline(monkeypatch, *, cancel_after: str | None = None, session_ref=None) -> dict:
    """Patch all four LLM stages.

    If cancel_after is set (e.g. "parsing"), the patch for that stage will flip
    the in-flight application's status to cancelled via a secondary session write
    (simulating the cancel endpoint running concurrently), and the patch for the
    *next* stage records whether it was called so we can assert it was skipped.
    """
    calls: dict[str, int] = {
        "parse": 0,
        "score": 0,
        "tailor": 0,
        "draft": 0,
    }

    async def fake_parse_jd(description):
        calls["parse"] += 1
        if cancel_after == "parsing" and session_ref is not None:
            # Simulate the cancel endpoint committing cancelled status before the
            # next _check_cancelled() call.
            app = session_ref.exec(
                select(Application).where(Application.status == ApplicationStatus.preparing)
            ).first()
            if app:
                app.status = ApplicationStatus.cancelled
                session_ref.add(app)
                session_ref.commit()
        return {"title": "Data Engineer"}

    async def fake_score(resume_text, parsed):
        calls["score"] += 1
        return (80, "solid match", ["a gap"])

    async def fake_tailor(resume_text, parsed):
        calls["tailor"] += 1
        return ("tailored", "changes", '[{"type":"added","text":"x","line":1}]', [], {})

    async def fake_draft(text, parsed, title, company):
        calls["draft"] += 1
        if cancel_after == "drafting" and session_ref is not None:
            # Simulate the cancel endpoint committing cancelled status while the
            # final drafting LLM call is in flight — mirrors the "parsing" branch.
            app = session_ref.exec(
                select(Application).where(Application.status == ApplicationStatus.preparing)
            ).first()
            if app:
                app.status = ApplicationStatus.cancelled
                session_ref.add(app)
                session_ref.commit()
        return ("Dear Hiring Manager", "", ["Dear Hiring Manager"])

    monkeypatch.setattr(application_service, "_parse_jd", fake_parse_jd)
    monkeypatch.setattr(scoring_service, "score_resume", fake_score)
    monkeypatch.setattr(tailoring_service, "tailor_resume", fake_tailor)
    monkeypatch.setattr(drafting_service, "draft_cover_letter", fake_draft)

    return calls


@pytest.mark.asyncio
async def test_cooperative_cancellation_after_parse_returns_cancelled(
    session: Session, user: User, monkeypatch
):
    """After parse completes and cancel is committed, prepare returns with status=cancelled.

    - No PrepCancelled leaks out (it is caught internally).
    - status is cancelled, NOT prep_failed.
    - prep_error is NOT set.
    - Stages after the cancellation point (score, tailor, draft) are not called.
    """
    posting = _seed_for_prepare(session, user.id)
    calls = _patch_pipeline(monkeypatch, cancel_after="parsing", session_ref=session)

    result = await prepare_application(posting.id, user.id, session)

    # Returns cleanly — no exception
    assert result.status == ApplicationStatus.cancelled
    # prep_error must NOT be populated (not a failure, just a cancellation)
    assert result.prep_error == ""
    # parse ran (it was the stage that triggered cancel)
    assert calls["parse"] == 1
    # Stages after the checkpoint (score/tailor/draft) must NOT have run.
    # Note: _advance("scoring") fires before _check_cancelled detects the cancel,
    # so prep_stage may be "scoring" — that is expected and not asserted here.
    # What matters is that the LLM call for scoring never happened.
    assert calls["score"] == 0
    assert calls["tailor"] == 0
    assert calls["draft"] == 0


@pytest.mark.asyncio
async def test_cooperative_cancellation_does_not_set_prep_failed(
    session: Session, user: User, monkeypatch
):
    """Cancellation must leave the row in cancelled state, never flip to prep_failed."""
    posting = _seed_for_prepare(session, user.id)
    _patch_pipeline(monkeypatch, cancel_after="parsing", session_ref=session)

    result = await prepare_application(posting.id, user.id, session)

    # Refresh from DB to make sure the write was committed correctly
    session.refresh(result)
    assert result.status == ApplicationStatus.cancelled
    assert result.status != ApplicationStatus.prep_failed


@pytest.mark.asyncio
async def test_cooperative_cancellation_during_drafting_does_not_flip_to_pending(
    session: Session, user: User, monkeypatch
):
    """Regression: a cancel that arrives DURING the final draft_cover_letter call must
    not be overwritten by the pending transition that follows it.

    Before the fix, prepare_application unconditionally set app.status = pending after
    drafting completed, silently ignoring any cancel committed concurrently during that
    LLM call. The fix added a _check_cancelled() checkpoint immediately before the
    status = pending block so the cancel is honoured and the row stays cancelled.

    All four pipeline stages must still run (the cancel is only detected after drafting
    returns), and the result must NOT be a prep_failed row — a cancel is a clean exit.
    """
    posting = _seed_for_prepare(session, user.id)
    calls = _patch_pipeline(monkeypatch, cancel_after="drafting", session_ref=session)

    result = await prepare_application(posting.id, user.id, session)

    # Core regression assertion: status must be cancelled, NOT pending.
    session.refresh(result)
    assert result.status == ApplicationStatus.cancelled, (
        f"Expected cancelled but got {result.status!r} — "
        "the post-draft pending transition overwrote the concurrent cancel"
    )
    assert result.status != ApplicationStatus.pending

    # A cancellation is not a failure — prep_error must remain empty.
    assert result.prep_error == ""

    # All four stages ran; the cancel only fires inside fake_draft (the last stage).
    assert calls["parse"] == 1
    assert calls["score"] == 1
    assert calls["tailor"] == 1
    assert calls["draft"] == 1
