"""Tests for the PDF export paths with rendercv integration.

Covers:
- resume.pdf and cover-letter.pdf return 200 application/pdf when resume_data_yaml is empty
  (reportlab fallback path).
- resume.pdf returns 200 application/pdf when resume_data_yaml is populated and rendercv
  is mocked to return valid PDF bytes (rendercv path).
- RenderError from rendercv triggers the reportlab fallback (still returns 200 PDF).
"""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.models.application import Application, ApplicationStatus
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.models.user import User
from backend.routers.exports import _DOCX_MEDIA_TYPE
from backend.services.rendercv_service import RenderError

# A minimal YAML that the real rendercv could render, used as a non-empty string to
# trigger the rendercv code path even when rendercv itself is mocked.
_FAKE_RESUME_YAML = "cv:\n  name: Test\n  sections: {}\ndesign:\n  theme: classic\n"
_FAKE_CL_YAML = "cv:\n  name: Test\n  sections:\n    Cover Letter:\n      - Para one.\ndesign:\n  theme: classic\n"


def _make_full_app(
    session: Session,
    user_id,
    resume_data_yaml: str = "",
    cover_letter_data_yaml: str = "",
) -> Application:
    posting = JobPosting(
        user_id=user_id,
        source="test",
        source_job_id=str(uuid.uuid4()),
        title="Backend Engineer",
        company="Globex",
        url="https://globex.example.com",
        description="Test job",
        remote_status=RemoteStatus.remote,
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)

    resume = Resume(
        user_id=user_id,
        filename="r.txt",
        file_path="/tmp/r.txt",
        text_content="Test resume text",
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)

    app = Application(
        user_id=user_id,
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=ApplicationStatus.pending,
        tailored_resume_text="EXPERIENCE\n\nBackend Engineer at Globex\n- Built systems",
        cover_letter_text="Dear Hiring Manager,\n\nI am excited to apply.",
        resume_data_yaml=resume_data_yaml,
        cover_letter_data_yaml=cover_letter_data_yaml,
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


# ---------------------------------------------------------------------------
# resume.pdf — reportlab fallback (empty YAML)
# ---------------------------------------------------------------------------


def test_resume_pdf_reportlab_fallback_when_yaml_empty(client: TestClient, session: Session, user: User):
    """When resume_data_yaml is empty the reportlab path must still produce a PDF."""
    app = _make_full_app(session, user.id, resume_data_yaml="")
    response = client.get(f"/applications/{app.id}/resume.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# resume.pdf — rendercv path (non-empty YAML, rendercv mocked)
# ---------------------------------------------------------------------------


def test_resume_pdf_uses_rendercv_when_yaml_present(client: TestClient, session: Session, user: User):
    """When resume_data_yaml is non-empty, render_pdf should be called and its bytes returned."""
    fake_pdf = b"%PDF-1.4 rendercv-produced-content"
    app = _make_full_app(session, user.id, resume_data_yaml=_FAKE_RESUME_YAML)

    with patch(
        "backend.routers.exports._rendercv_render_pdf", return_value=fake_pdf
    ) as mock_render:
        response = client.get(f"/applications/{app.id}/resume.pdf")

    mock_render.assert_called_once()
    assert response.status_code == 200
    assert response.content == fake_pdf
    assert response.headers["content-type"] == "application/pdf"


# ---------------------------------------------------------------------------
# resume.pdf — RenderError triggers reportlab fallback (still 200)
# ---------------------------------------------------------------------------


def test_resume_pdf_falls_back_to_reportlab_on_render_error(client: TestClient, session: Session, user: User):
    """If rendercv raises RenderError the route must fall back to reportlab, not 500."""
    app = _make_full_app(session, user.id, resume_data_yaml=_FAKE_RESUME_YAML)

    with patch(
        "backend.routers.exports._rendercv_render_pdf",
        side_effect=RenderError("subprocess failed"),
    ):
        response = client.get(f"/applications/{app.id}/resume.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    # reportlab fallback also produces valid PDF bytes
    assert response.content[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# resume.pdf — theme selection swaps design.theme before rendering
# ---------------------------------------------------------------------------


def test_resume_pdf_theme_swaps_design_theme(client: TestClient, session: Session, user: User):
    """A valid ?theme= must rewrite design.theme in the YAML passed to rendercv."""
    import yaml

    fake_pdf = b"%PDF-1.4 themed"
    app = _make_full_app(session, user.id, resume_data_yaml=_FAKE_RESUME_YAML)

    with patch(
        "backend.routers.exports._rendercv_render_pdf", return_value=fake_pdf
    ) as mock_render:
        response = client.get(f"/applications/{app.id}/resume.pdf?theme=moderncv")

    assert response.status_code == 200
    assert response.content == fake_pdf
    rendered_yaml = mock_render.call_args.args[0]
    assert yaml.safe_load(rendered_yaml)["design"]["theme"] == "moderncv"


def test_resume_pdf_rejects_unknown_theme(client: TestClient, session: Session, user: User):
    app = _make_full_app(session, user.id, resume_data_yaml=_FAKE_RESUME_YAML)
    response = client.get(f"/applications/{app.id}/resume.pdf?theme=not-a-real-theme")
    assert response.status_code == 400


def test_resume_pdf_no_theme_keeps_stored_yaml(client: TestClient, session: Session, user: User):
    """Without ?theme=, the stored YAML is passed through unchanged."""
    fake_pdf = b"%PDF-1.4 default"
    app = _make_full_app(session, user.id, resume_data_yaml=_FAKE_RESUME_YAML)

    with patch(
        "backend.routers.exports._rendercv_render_pdf", return_value=fake_pdf
    ) as mock_render:
        response = client.get(f"/applications/{app.id}/resume.pdf")

    assert response.status_code == 200
    assert mock_render.call_args.args[0] == _FAKE_RESUME_YAML


def test_resume_docx_ignores_theme(client: TestClient, session: Session, user: User):
    """The .docx export has no theme concept; a theme param must not break it."""
    app = _make_full_app(session, user.id, resume_data_yaml=_FAKE_RESUME_YAML)
    response = client.get(f"/applications/{app.id}/resume.docx?theme=moderncv")
    assert response.status_code == 200
    assert response.headers["content-type"] == _DOCX_MEDIA_TYPE


# ---------------------------------------------------------------------------
# cover-letter.pdf — reportlab fallback (empty YAML)
# ---------------------------------------------------------------------------


def test_cover_letter_pdf_reportlab_fallback_when_yaml_empty(client: TestClient, session: Session, user: User):
    app = _make_full_app(session, user.id, cover_letter_data_yaml="")
    response = client.get(f"/applications/{app.id}/cover-letter.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# cover-letter.pdf — rendercv path
# ---------------------------------------------------------------------------


def test_cover_letter_pdf_uses_rendercv_when_yaml_present(client: TestClient, session: Session, user: User):
    fake_pdf = b"%PDF-1.4 cl-content"
    app = _make_full_app(session, user.id, cover_letter_data_yaml=_FAKE_CL_YAML)

    with patch(
        "backend.routers.exports._rendercv_render_pdf", return_value=fake_pdf
    ) as mock_render:
        response = client.get(f"/applications/{app.id}/cover-letter.pdf")

    mock_render.assert_called_once()
    assert response.status_code == 200
    assert response.content == fake_pdf


# ---------------------------------------------------------------------------
# cover-letter.pdf — RenderError fallback
# ---------------------------------------------------------------------------


def test_cover_letter_pdf_falls_back_on_render_error(client: TestClient, session: Session, user: User):
    app = _make_full_app(session, user.id, cover_letter_data_yaml=_FAKE_CL_YAML)

    with patch(
        "backend.routers.exports._rendercv_render_pdf",
        side_effect=RenderError("render boom"),
    ):
        response = client.get(f"/applications/{app.id}/cover-letter.pdf")

    assert response.status_code == 200
    assert response.content[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# 404 for non-existent apps
# ---------------------------------------------------------------------------


def test_resume_pdf_not_found(client: TestClient):
    response = client.get(f"/applications/{uuid.uuid4()}/resume.pdf")
    assert response.status_code == 404


def test_cover_letter_pdf_not_found(client: TestClient):
    response = client.get(f"/applications/{uuid.uuid4()}/cover-letter.pdf")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Filename contains company and title
# ---------------------------------------------------------------------------


def test_resume_pdf_filename_contains_company_and_title(client: TestClient, session: Session, user: User):
    app = _make_full_app(session, user.id, resume_data_yaml="")
    response = client.get(f"/applications/{app.id}/resume.pdf")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "Globex" in disposition
    assert "Backend_Engineer" in disposition


def test_cover_letter_pdf_filename_contains_company_and_title(client: TestClient, session: Session, user: User):
    app = _make_full_app(session, user.id, cover_letter_data_yaml="")
    response = client.get(f"/applications/{app.id}/cover-letter.pdf")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert "Globex" in disposition
    assert "Backend_Engineer" in disposition
