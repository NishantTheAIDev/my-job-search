"""Resume export endpoints (.docx and .pdf)."""

import io
import logging
import re
import uuid
from html import escape

from docx import Document
from docx.shared import Pt
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlmodel import Session

from backend.database import get_session
from backend.models.application import Application
from backend.models.job_posting import JobPosting
from backend.services.rendercv_service import RENDERCV_THEMES, RenderError, apply_theme
from backend.services.rendercv_service import render_pdf as _rendercv_render_pdf

logger = logging.getLogger(__name__)
router = APIRouter()


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    # All-caps short line (section header like "EXPERIENCE", "EDUCATION")
    if stripped == stripped.upper() and len(stripped) <= 40 and stripped.isalpha():
        return True
    # Short line ending with colon
    return stripped.endswith(":") and len(stripped) <= 40


def _sanitize_filename_part(text: str, max_len: int = 20) -> str:
    # Restrict to printable ASCII word characters only — prevents header encoding issues
    sanitized = re.sub(r"[^A-Za-z0-9]", "_", text)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return sanitized[:max_len]


def _build_docx(resume_text: str) -> bytes:
    doc = Document()

    # Remove default styles that add unwanted spacing
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    for line in resume_text.splitlines():
        stripped = line.strip()
        if not stripped:
            doc.add_paragraph("")
            continue
        if _looks_like_heading(stripped):
            p = doc.add_paragraph(stripped)
            run = p.runs[0]
            run.bold = True
            run.font.size = Pt(13)
        else:
            doc.add_paragraph(stripped)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def _build_pdf(resume_text: str) -> bytes:
    # ATS-safe: single column, selectable text, standard font, no tables/images.
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    body_style = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=11, leading=14, alignment=TA_LEFT
    )
    heading_style = ParagraphStyle(
        "Heading",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        spaceBefore=6,
        spaceAfter=2,
        alignment=TA_LEFT,
    )

    flowables = []
    for line in resume_text.splitlines():
        stripped = line.strip()
        if not stripped:
            flowables.append(Spacer(1, 8))
            continue
        # escape() keeps reportlab from interpreting &, <, > as inline markup
        text = escape(stripped)
        style = heading_style if _looks_like_heading(stripped) else body_style
        flowables.append(Paragraph(text, style))

    doc.build(flowables)
    buf.seek(0)
    return buf.read()


_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _document_filename(app: Application, session: Session, prefix: str, ext: str) -> str:
    posting = session.get(JobPosting, app.job_posting_id)
    company_part = _sanitize_filename_part(posting.company or "Company") if posting else "Company"
    title_part = _sanitize_filename_part(posting.title or "Role") if posting else "Role"
    return f"{prefix}_{company_part}_{title_part}.{ext}"


def _get_app_or_404(app_id: uuid.UUID, session: Session) -> Application:
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


def _attachment(content: bytes, media_type: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{app_id}/resume.docx")
def download_resume_docx(app_id: uuid.UUID, session: Session = Depends(get_session)):
    app = _get_app_or_404(app_id, session)
    filename = _document_filename(app, session, "Resume", "docx")
    return _attachment(_build_docx(app.tailored_resume_text or ""), _DOCX_MEDIA_TYPE, filename)


def _render_pdf_with_fallback(yaml_str: str | None, fallback_text: str) -> bytes:
    """Try rendercv; fall back to reportlab if YAML is empty or render fails."""
    if yaml_str:
        try:
            return _rendercv_render_pdf(yaml_str)
        except RenderError as exc:
            logger.warning("rendercv render failed, falling back to reportlab: %s", exc)
    return _build_pdf(fallback_text)


@router.get("/{app_id}/resume.pdf")
def download_resume_pdf(
    app_id: uuid.UUID,
    theme: str | None = Query(None),
    session: Session = Depends(get_session),
):
    app = _get_app_or_404(app_id, session)
    if theme is not None and theme not in RENDERCV_THEMES:
        raise HTTPException(status_code=400, detail=f"Unknown rendercv theme: {theme}")
    filename = _document_filename(app, session, "Resume", "pdf")
    resume_yaml = app.resume_data_yaml or None
    if resume_yaml and theme is not None:
        resume_yaml = apply_theme(resume_yaml, theme)
    pdf_bytes = _render_pdf_with_fallback(resume_yaml, app.tailored_resume_text or "")
    return _attachment(pdf_bytes, "application/pdf", filename)


@router.get("/{app_id}/cover-letter.docx")
def download_cover_letter_docx(app_id: uuid.UUID, session: Session = Depends(get_session)):
    app = _get_app_or_404(app_id, session)
    filename = _document_filename(app, session, "CoverLetter", "docx")
    return _attachment(_build_docx(app.cover_letter_text or ""), _DOCX_MEDIA_TYPE, filename)


@router.get("/{app_id}/cover-letter.pdf")
def download_cover_letter_pdf(app_id: uuid.UUID, session: Session = Depends(get_session)):
    app = _get_app_or_404(app_id, session)
    filename = _document_filename(app, session, "CoverLetter", "pdf")
    pdf_bytes = _render_pdf_with_fallback(
        app.cover_letter_data_yaml or None, app.cover_letter_text or ""
    )
    return _attachment(pdf_bytes, "application/pdf", filename)
