import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class SearchJobStatus(StrEnum):
    queued = "queued"
    running = "running"
    complete = "complete"
    failed = "failed"


class SearchJob(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    criteria_json: str
    status: SearchJobStatus = SearchJobStatus.queued
    total_results: int = 0
    completed_adapters: int = 0
    total_adapters: int = 0
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    # SHA-256 hex digest of the normalized search criteria; used to detect
    # same-day duplicate searches and return cached results without re-hitting
    # adapter APIs.  Empty string on rows created before this column existed.
    criteria_fingerprint: str = Field(default="", index=True)
