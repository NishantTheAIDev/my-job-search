import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class ApplicationStatus(StrEnum):
    pending = "pending"
    # NOTE: transitions go pending -> submitted (or failed); "approved" is intentionally absent
    # so there is no intermediate state that a second call site could treat as submission-ready.
    rejected = "rejected"
    submitted = "submitted"
    failed = "failed"


class Application(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_posting_id: uuid.UUID = Field(foreign_key="jobposting.id", index=True)
    resume_id: uuid.UUID = Field(foreign_key="resume.id")
    status: ApplicationStatus = ApplicationStatus.pending
    tailored_resume_text: str = ""
    resume_diff_json: str = "[]"
    cover_letter_text: str = ""
    match_score: int = 0
    match_rationale: str = ""
    tailoring_failed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None
    submitted_at: datetime | None = None
    rejected_at: datetime | None = None
