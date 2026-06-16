"""Router-level tests for:

- POST /applications/{app_id}/save
- GET  /applications/saved
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.models.application import Application, ApplicationStatus
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.models.user import User

# ---------------------------------------------------------------------------
# Seed helpers — rows are stamped with the user the client authenticates as.
# ---------------------------------------------------------------------------


def _make_posting(
    session: Session,
    user_id: uuid.UUID,
    *,
    title: str = "Software Engineer",
    company: str = "Acme",
) -> JobPosting:
    posting = JobPosting(
        user_id=user_id,
        source="test",
        source_job_id=str(uuid.uuid4()),
        title=title,
        company=company,
        location="Remote",
        url="https://example.com/job/1",
        description="A test job",
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
        text_content="John Doe, Software Engineer",
        is_active=True,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def _make_pending_app(session: Session, user_id: uuid.UUID, *, match_score: int = 80) -> Application:
    posting = _make_posting(session, user_id)
    resume = _make_resume(session, user_id)
    app = Application(
        user_id=user_id,
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=ApplicationStatus.pending,
        tailored_resume_text="tailored",
        cover_letter_text="dear hiring manager",
        match_score=match_score,
        match_rationale="good match",
        match_gaps='["Docker"]',
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


def _make_saved_app(
    session: Session,
    user_id: uuid.UUID,
    *,
    match_score: int = 75,
    title: str = "Software Engineer",
    company: str = "Acme",
) -> Application:
    posting = _make_posting(session, user_id, title=title, company=company)
    resume = _make_resume(session, user_id)
    app = Application(
        user_id=user_id,
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=ApplicationStatus.saved,
        tailored_resume_text="tailored",
        cover_letter_text="dear hiring manager",
        match_score=match_score,
        match_rationale="great fit",
        match_gaps="[]",
        saved_at=datetime.now(UTC),
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


# ---------------------------------------------------------------------------
# POST /applications/{app_id}/save
# ---------------------------------------------------------------------------


class TestSaveRoute:
    def test_save_pending_returns_200_and_saved_status(
        self, client: TestClient, session: Session, user: User
    ):
        app = _make_pending_app(session, user.id)
        response = client.post(f"/applications/{app.id}/save")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"
        assert data["saved_at"] is not None

    def test_save_pending_match_gaps_decoded_in_response(
        self, client: TestClient, session: Session, user: User
    ):
        """ApplicationResponse.match_gaps must be a list, not a raw JSON string."""
        app = _make_pending_app(session, user.id)
        response = client.post(f"/applications/{app.id}/save")
        assert response.status_code == 200
        gaps = response.json()["match_gaps"]
        assert isinstance(gaps, list)
        assert gaps == ["Docker"]

    def test_save_non_pending_returns_409(self, client: TestClient, session: Session, user: User):
        app = _make_pending_app(session, user.id)
        client.post(f"/applications/{app.id}/save")
        response = client.post(f"/applications/{app.id}/save")
        assert response.status_code == 409

    def test_save_unknown_id_returns_404(self, client: TestClient):
        response = client.post(f"/applications/{uuid.uuid4()}/save")
        assert response.status_code == 404

    def test_save_other_users_app_returns_404(
        self, session: Session, user: User, other_user: User, make_client: object
    ):
        """Cross-tenant: B saving A's application gets 404, and it stays pending."""
        app = _make_pending_app(session, user.id)
        client_b = make_client(other_user)
        response = client_b.post(f"/applications/{app.id}/save")
        assert response.status_code == 404
        session.refresh(app)
        assert app.status == ApplicationStatus.pending


# ---------------------------------------------------------------------------
# GET /applications/saved
# ---------------------------------------------------------------------------


class TestListSavedRoute:
    def test_empty_list_when_no_saved_apps(self, client: TestClient):
        response = client.get("/applications/saved")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_saved_apps_only(self, client: TestClient, session: Session, user: User):
        _make_saved_app(session, user.id, title="ML Engineer", company="BrainCo")
        _make_pending_app(session, user.id)

        response = client.get("/applications/saved")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert items[0]["job_title"] == "ML Engineer"
        assert items[0]["company"] == "BrainCo"

    def test_response_shape(self, client: TestClient, session: Session, user: User):
        _make_saved_app(session, user.id, match_score=88, title="Data Engineer", company="DataCo")

        response = client.get("/applications/saved")
        assert response.status_code == 200
        item = response.json()[0]
        assert {"id", "job_title", "company", "match_score", "saved_at"} <= item.keys()
        assert item["match_score"] == 88

    def test_newest_saved_first(self, client: TestClient, session: Session, user: User):
        """Saved apps must be ordered by saved_at descending (newest first)."""
        posting1 = _make_posting(session, user.id, title="First Job", company="Alpha")
        resume = _make_resume(session, user.id)
        posting2 = _make_posting(session, user.id, title="Second Job", company="Beta")
        resume2 = _make_resume(session, user.id)

        earlier = datetime.now(UTC) - timedelta(hours=2)
        later = datetime.now(UTC)

        app1 = Application(
            user_id=user.id,
            job_posting_id=posting1.id,
            resume_id=resume.id,
            status=ApplicationStatus.saved,
            tailored_resume_text="t",
            cover_letter_text="c",
            match_score=60,
            match_rationale="ok",
            match_gaps="[]",
            saved_at=earlier,
        )
        app2 = Application(
            user_id=user.id,
            job_posting_id=posting2.id,
            resume_id=resume2.id,
            status=ApplicationStatus.saved,
            tailored_resume_text="t",
            cover_letter_text="c",
            match_score=70,
            match_rationale="great",
            match_gaps="[]",
            saved_at=later,
        )
        session.add(app1)
        session.add(app2)
        session.commit()

        response = client.get("/applications/saved")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2
        assert items[0]["job_title"] == "Second Job"
        assert items[1]["job_title"] == "First Job"

    def test_saved_list_is_per_user(
        self, session: Session, user: User, other_user: User, make_client: object
    ):
        """User B must not see user A's saved applications."""
        _make_saved_app(session, user.id, title="A's job", company="ACo")
        client_b = make_client(other_user)
        response = client_b.get("/applications/saved")
        assert response.status_code == 200
        assert response.json() == []
