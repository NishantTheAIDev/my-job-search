"""Router-level tests for:

- POST /applications/{app_id}/save
- GET  /applications/saved
"""

import io
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.models.application import Application, ApplicationStatus
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume

# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _upload_resume(client: TestClient) -> None:
    content = b"John Doe\nSoftware Engineer"
    client.post(
        "/resume/upload",
        files={"file": ("resume.txt", io.BytesIO(content), "text/plain")},
    )


def _make_posting(session: Session, *, title: str = "Software Engineer", company: str = "Acme") -> JobPosting:
    posting = JobPosting(
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


def _make_resume(session: Session) -> Resume:
    resume = Resume(
        filename="test.txt",
        file_path="/tmp/test.txt",
        text_content="John Doe, Software Engineer",
        is_active=True,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def _make_pending_app(session: Session, *, match_score: int = 80) -> Application:
    posting = _make_posting(session)
    resume = _make_resume(session)
    app = Application(
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


def _make_saved_app(session: Session, *, match_score: int = 75, title: str = "Software Engineer", company: str = "Acme") -> Application:
    """Create a posting + resume + application already in saved state."""
    posting = _make_posting(session, title=title, company=company)
    resume = _make_resume(session)
    from datetime import UTC, datetime

    app = Application(
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
        self, client: TestClient, session: Session
    ):
        app = _make_pending_app(session)
        response = client.post(f"/applications/{app.id}/save")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"
        assert data["saved_at"] is not None

    def test_save_pending_match_gaps_decoded_in_response(
        self, client: TestClient, session: Session
    ):
        """ApplicationResponse.match_gaps must be a list, not a raw JSON string."""
        app = _make_pending_app(session)
        response = client.post(f"/applications/{app.id}/save")
        assert response.status_code == 200
        gaps = response.json()["match_gaps"]
        assert isinstance(gaps, list)
        assert gaps == ["Docker"]

    def test_save_non_pending_returns_409(self, client: TestClient, session: Session):
        app = _make_pending_app(session)
        # First save succeeds.
        client.post(f"/applications/{app.id}/save")
        # Second call is a 409 (already saved / non-pending).
        response = client.post(f"/applications/{app.id}/save")
        assert response.status_code == 409

    def test_save_submitted_app_returns_409(self, client: TestClient, session: Session):
        app = _make_pending_app(session)
        app.status = ApplicationStatus.submitted
        session.add(app)
        session.commit()

        response = client.post(f"/applications/{app.id}/save")
        assert response.status_code == 409

    def test_save_unknown_id_returns_404(self, client: TestClient):
        response = client.post(f"/applications/{uuid.uuid4()}/save")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /applications/saved
# ---------------------------------------------------------------------------


class TestListSavedRoute:
    def test_empty_list_when_no_saved_apps(self, client: TestClient):
        response = client.get("/applications/saved")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_saved_apps_only(self, client: TestClient, session: Session):
        _make_saved_app(session, title="ML Engineer", company="BrainCo")
        # Also create a pending app — must not appear in the saved list.
        _make_pending_app(session)

        response = client.get("/applications/saved")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert items[0]["job_title"] == "ML Engineer"
        assert items[0]["company"] == "BrainCo"

    def test_response_shape(self, client: TestClient, session: Session):
        _make_saved_app(session, match_score=88, title="Data Engineer", company="DataCo")

        response = client.get("/applications/saved")
        assert response.status_code == 200
        item = response.json()[0]
        assert "id" in item
        assert "job_title" in item
        assert "company" in item
        assert "match_score" in item
        assert "saved_at" in item
        assert item["match_score"] == 88

    def test_newest_saved_first(self, client: TestClient, session: Session):
        """Saved apps must be ordered by saved_at descending (newest first)."""
        from datetime import UTC, datetime, timedelta

        posting1 = _make_posting(session, title="First Job", company="Alpha")
        resume = _make_resume(session)
        posting2 = _make_posting(session, title="Second Job", company="Beta")
        resume2 = _make_resume(session)

        earlier = datetime.now(UTC) - timedelta(hours=2)
        later = datetime.now(UTC)

        app1 = Application(
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
        # Newest (Second Job / Beta) must come first
        assert items[0]["job_title"] == "Second Job"
        assert items[1]["job_title"] == "First Job"
