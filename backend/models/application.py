import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class ApplicationStatus(StrEnum):
    preparing = "preparing"  # LLM pipeline in flight; not yet reviewable or approvable
    prep_failed = "prep_failed"  # pipeline errored before producing a reviewable application
    pending = "pending"
    # NOTE: transitions go preparing -> pending -> submitted (or failed); "approved" is
    # intentionally absent so there is no intermediate state that a second call site could treat
    # as submission-ready. prep_failed is terminal for preparation and can never be approved.
    rejected = "rejected"
    submitted = "submitted"
    failed = "failed"


class Application(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_posting_id: uuid.UUID = Field(foreign_key="jobposting.id", index=True)
    resume_id: uuid.UUID = Field(foreign_key="resume.id")
    status: ApplicationStatus = ApplicationStatus.pending
    prep_stage: str = ""  # current pipeline stage while status == preparing (e.g. "tailoring")
    prep_error: str = ""  # populated when status == prep_failed
    tailored_resume_text: str = ""
    resume_diff_json: str = "[]"
    cover_letter_text: str = ""
    resume_data_yaml: str = ""
    cover_letter_data_yaml: str = ""
    match_score: int = 0
    match_rationale: str = ""
    tailoring_failed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None
    submitted_at: datetime | None = None
    rejected_at: datetime | None = None
