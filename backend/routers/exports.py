"""Resume .docx export endpoint."""

import io
import re
import uuid

from docx import Document
from docx.shared import Pt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from backend.database import get_session
from backend.models.application import Application
from backend.models.job_posting import JobPosting

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


@router.get("/{app_id}/resume.docx")
def download_resume(
    app_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    posting = session.get(JobPosting, app.job_posting_id)
    company_part = _sanitize_filename_part(posting.company or "Company") if posting else "Company"
    title_part = _sanitize_filename_part(posting.title or "Role") if posting else "Role"
    filename = f"Resume_{company_part}_{title_part}.docx"

    content = _build_docx(app.tailored_resume_text or "")

    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
