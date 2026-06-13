"""Tests for the resume export endpoints (.docx and .pdf)."""

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
        cover_letter_text="Dear Hiring Manager,\n\nI am excited to apply.",
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


def test_download_resume_returns_pdf(client: TestClient, session: Session):
    app = _create_test_application(session)
    response = client.get(f"/applications/{app.id}/resume.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    disposition = response.headers["content-disposition"]
    assert ".pdf" in disposition
    assert "Acme_Corp" in disposition
    assert "Software_Engineer" in disposition
    # PDF magic bytes
    assert response.content[:4] == b"%PDF"


def test_download_pdf_not_found(client: TestClient):
    response = client.get(f"/applications/{uuid.uuid4()}/resume.pdf")
    assert response.status_code == 404


def test_download_cover_letter_docx(client: TestClient, session: Session):
    app = _create_test_application(session)
    response = client.get(f"/applications/{app.id}/cover-letter.docx")
    assert response.status_code == 200
    assert "wordprocessingml" in response.headers["content-type"]
    disposition = response.headers["content-disposition"]
    assert "CoverLetter_Acme_Corp_Software_Engineer.docx" in disposition
    assert response.content[:4] == b"PK\x03\x04"


def test_download_cover_letter_pdf(client: TestClient, session: Session):
    app = _create_test_application(session)
    response = client.get(f"/applications/{app.id}/cover-letter.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "CoverLetter_" in response.headers["content-disposition"]
    assert response.content[:4] == b"%PDF"


def test_download_cover_letter_not_found(client: TestClient):
    response = client.get(f"/applications/{uuid.uuid4()}/cover-letter.pdf")
    assert response.status_code == 404
