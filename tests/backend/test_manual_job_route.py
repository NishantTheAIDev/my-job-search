"""Router-level tests for POST /jobs/manual (create-manual-application endpoint).

Covers:
- Happy path: creates a JobPosting with source=="manual", search_job_id is None,
  description == jd_text, and returns {status:"preparing", job_id:...}.
- 400 when no active resume exists.
- 422 when jd_text is empty (min_length=1 violated).
- 422 when jd_text exceeds 30 000 chars (max_length=30_000 violated).
- Background prepare task is queued (not executed) — patched via monkeypatch.
"""

import io
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.models.job_posting import JobPosting

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload_resume(client: TestClient) -> None:
    content = b"John Doe\nSoftware Engineer\n5 years Python"
    client.post(
        "/resume/upload",
        files={"file": ("resume.txt", io.BytesIO(content), "text/plain")},
    )


SAMPLE_JD = (
    "We are looking for a Senior Python Engineer to join our team. "
    "You will work on backend services, APIs, and infrastructure. "
    "Requirements: 5+ years Python, FastAPI, Docker, AWS."
)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCreateManualJobHappyPath:
    def test_returns_preparing_status_and_job_id(self, client: TestClient):
        _upload_resume(client)
        with patch("backend.routers.jobs.prepare_application_task"):
            response = client.post("/jobs/manual", json={"jd_text": SAMPLE_JD})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "preparing"
        assert "job_id" in data
        # job_id must be a valid UUID string
        uuid.UUID(data["job_id"])

    def test_creates_posting_with_source_manual(self, client: TestClient, session: Session):
        _upload_resume(client)
        with patch("backend.routers.jobs.prepare_application_task"):
            response = client.post("/jobs/manual", json={"jd_text": SAMPLE_JD})
        job_id = uuid.UUID(response.json()["job_id"])
        posting = session.get(JobPosting, job_id)
        assert posting is not None
        assert posting.source == "manual"

    def test_posting_has_null_search_job_id(self, client: TestClient, session: Session):
        _upload_resume(client)
        with patch("backend.routers.jobs.prepare_application_task"):
            response = client.post("/jobs/manual", json={"jd_text": SAMPLE_JD})
        job_id = uuid.UUID(response.json()["job_id"])
        posting = session.get(JobPosting, job_id)
        assert posting.search_job_id is None

    def test_posting_description_equals_jd_text(self, client: TestClient, session: Session):
        _upload_resume(client)
        with patch("backend.routers.jobs.prepare_application_task"):
            response = client.post("/jobs/manual", json={"jd_text": SAMPLE_JD})
        job_id = uuid.UUID(response.json()["job_id"])
        posting = session.get(JobPosting, job_id)
        assert posting.description == SAMPLE_JD

    def test_optional_title_and_company_persisted(self, client: TestClient, session: Session):
        _upload_resume(client)
        with patch("backend.routers.jobs.prepare_application_task"):
            response = client.post(
                "/jobs/manual",
                json={"jd_text": SAMPLE_JD, "title": "Python Engineer", "company": "TestCorp"},
            )
        job_id = uuid.UUID(response.json()["job_id"])
        posting = session.get(JobPosting, job_id)
        assert posting.title == "Python Engineer"
        assert posting.company == "TestCorp"

    def test_title_defaults_when_omitted(self, client: TestClient, session: Session):
        _upload_resume(client)
        with patch("backend.routers.jobs.prepare_application_task"):
            response = client.post("/jobs/manual", json={"jd_text": SAMPLE_JD})
        job_id = uuid.UUID(response.json()["job_id"])
        posting = session.get(JobPosting, job_id)
        # Falls back to the default title set in create_manual_application
        assert posting.title  # non-empty

    def test_background_task_is_queued(self, client: TestClient):
        """The task is added via BackgroundTasks — verified by patching."""
        _upload_resume(client)
        with patch("backend.routers.jobs.prepare_application_task") as mock_task:
            # The route calls background_tasks.add_task(prepare_application_task, posting.id).
            # FastAPI's TestClient runs background tasks synchronously after the response,
            # so the patched task is invoked once with the new posting's id.
            response = client.post("/jobs/manual", json={"jd_text": SAMPLE_JD})
        assert response.status_code == 200
        assert response.json()["status"] == "preparing"
        mock_task.assert_called_once_with(uuid.UUID(response.json()["job_id"]))


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestCreateManualJobErrors:
    def test_400_when_no_active_resume(self, client: TestClient):
        response = client.post("/jobs/manual", json={"jd_text": SAMPLE_JD})
        assert response.status_code == 400
        assert "resume" in response.json()["detail"].lower()

    def test_422_on_empty_jd_text(self, client: TestClient):
        _upload_resume(client)
        response = client.post("/jobs/manual", json={"jd_text": ""})
        assert response.status_code == 422

    def test_422_on_oversized_jd_text(self, client: TestClient):
        _upload_resume(client)
        # max_length=30_000 chars; send 30_001
        big_jd = "x" * 30_001
        response = client.post("/jobs/manual", json={"jd_text": big_jd})
        assert response.status_code == 422

    def test_exactly_at_max_length_is_accepted(self, client: TestClient):
        """30 000 chars is the boundary — must be accepted."""
        _upload_resume(client)
        boundary_jd = "A" * 30_000
        with patch("backend.routers.jobs.prepare_application_task"):
            response = client.post("/jobs/manual", json={"jd_text": boundary_jd})
        assert response.status_code == 200

    def test_missing_jd_text_field_returns_422(self, client: TestClient):
        _upload_resume(client)
        response = client.post("/jobs/manual", json={"title": "Engineer"})
        assert response.status_code == 422
