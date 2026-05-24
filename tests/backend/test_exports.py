"""Tests for the resume .docx export endpoint."""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.models.application import Application, ApplicationStatus
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume


def _create_test_application(session: Session) -> Application:
    posting = JobPosting(
        source="test",
        source_job_id="e1",
        title="Software Engineer",
        company="Acme Corp",
        url="https://example.com",
        description="Test job",
        remote_status=RemoteStatus.remote,
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)

    resume = Resume(
        filename="test.txt",
        file_path="/tmp/test.txt",
        text_content="John Doe\nSoftware Engineer",
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)

    app = Application(
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=ApplicationStatus.pending,
        tailored_resume_text="EXPERIENCE\n\nSoftware Engineer at Acme\n- Built APIs with FastAPI",
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


def test_download_resume_returns_docx(client: TestClient, session: Session):
    app = _create_test_application(session)
    response = client.get(f"/applications/{app.id}/resume.docx")
    assert response.status_code == 200
    assert "wordprocessingml" in response.headers["content-type"]
    assert ".docx" in response.headers["content-disposition"]


def test_download_resume_not_found(client: TestClient):
    random_id = uuid.uuid4()
    response = client.get(f"/applications/{random_id}/resume.docx")
    assert response.status_code == 404


def test_filename_contains_company_and_title(client: TestClient, session: Session):
    app = _create_test_application(session)
    response = client.get(f"/applications/{app.id}/resume.docx")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "Acme_Corp" in disposition
    assert "Software_Engineer" in disposition


def test_docx_is_valid_zip(client: TestClient, session: Session):
    app = _create_test_application(session)
    response = client.get(f"/applications/{app.id}/resume.docx")
    assert response.status_code == 200
    # All .docx files are ZIP archives; magic bytes are PK\x03\x04
    assert response.content[:4] == b"PK\x03\x04"
