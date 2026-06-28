import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class ApplicationStatus(StrEnum):
    preparing = "preparing"  # LLM pipeline in flight; not yet reviewable or approvable
    prep_failed = "prep_failed"  # pipeline errored before producing a reviewable application
    pending = "pending"
    # NOTE: live transitions are preparing -> pending -> saved (or rejected). prep_failed is
    # terminal for preparation. "submitted"/"failed" below are legacy from a removed
    # submit-to-board path and are no longer produced — see CLAUDE.md. Do not reintroduce a
    # submission path without revisiting the no-external-submission invariant.
    rejected = "rejected"
    submitted = "submitted"
    failed = "failed"
    # Terminal status reached only via save_application(). Represents "keep this tailored
    # result for reference" without submitting to any board.
    saved = "saved"
    # Set by cancel_preparing_application(); signals the background pipeline's cooperative
    # checkpoints to abort before the next LLM call. Falls through the prepare dedup guard
    # (only preparing/pending are reused) so the user can re-prepare after cancelling.
    cancelled = "cancelled"


class Application(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    job_posting_id: uuid.UUID = Field(foreign_key="jobposting.id", index=True)
    resume_id: uuid.UUID = Field(foreign_key="resume.id")
    status: ApplicationStatus = ApplicationStatus.pending
    prep_stage: str = ""  # current pipeline stage while status == preparing (e.g. "tailoring")
    prep_error: str = ""  # populated when status == prep_failed
    tailored_resume_text: str = ""
    ai_tailored_resume_text: str = ""
    resume_diff_json: str = "[]"
    cover_letter_text: str = ""
    ai_cover_letter_text: str = ""
    resume_data_yaml: str = ""
    cover_letter_data_yaml: str = ""
    match_score: int = 0
    match_rationale: str = ""
    match_gaps: str = "[]"  # JSON-encoded list[str] of skill/experience gaps from the scorer
    tailoring_failed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None
    submitted_at: datetime | None = None
    rejected_at: datetime | None = None
    saved_at: datetime | None = None
