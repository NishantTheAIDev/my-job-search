import io
import logging
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.config import settings
from backend.database import get_session
from backend.limiter import limiter
from backend.models.resume import Resume

logger = logging.getLogger(__name__)
router = APIRouter()


def _extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".docx":
        from docx import Document  # type: ignore[import-untyped]

        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    elif suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        return content.decode("utf-8", errors="replace")


class ResumeResponse(BaseModel):
    id: uuid.UUID
    filename: str
    uploaded_at: str
    text_preview: str


_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("/upload", response_model=ResumeResponse)
@limiter.limit("10/minute")
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    filename = file.filename or "resume.txt"
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(_ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Allowed: {allowed}",
        )

    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 5 MB.")

    text = _extract_text(filename, content)

    storage_dir = Path(settings.resume_storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4()
    safe_name = f"{file_id}_{filename}"
    file_path = storage_dir / safe_name

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    existing = session.exec(select(Resume).where(Resume.is_active == True)).all()  # noqa: E712
    for r in existing:
        r.is_active = False
        session.add(r)

    resume = Resume(
        filename=filename,
        file_path=str(file_path.resolve()),
        text_content=text,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    logger.info(
        "resume uploaded: id=%s filename=%r size=%d bytes text_len=%d",
        resume.id,
        filename,
        len(content),
        len(text),
    )

    return ResumeResponse(
        id=resume.id,
        filename=resume.filename,
        uploaded_at=resume.uploaded_at.isoformat(),
        text_preview=text[:500],
    )


@router.get("", response_model=ResumeResponse)
def get_resume(session: Session = Depends(get_session)):
    resume = session.exec(select(Resume).where(Resume.is_active == True)).first()  # noqa: E712
    if not resume:
        raise HTTPException(status_code=404, detail="No resume uploaded yet")
    return ResumeResponse(
        id=resume.id,
        filename=resume.filename,
        uploaded_at=resume.uploaded_at.isoformat(),
        text_preview=resume.text_content[:500],
    )
