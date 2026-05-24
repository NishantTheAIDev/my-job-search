import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class RemoteStatus(StrEnum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"
    unspecified = "unspecified"


class SearchCriteria(SQLModel):
    query: str
    location: str | None = None
    remote_only: bool = False
    employment_type: str | None = None
    seniority: str | None = None
    posted_within_days: int | None = None
    page: int = Field(default=1, ge=1, le=50)


class JobPosting(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    search_job_id: uuid.UUID | None = Field(default=None, foreign_key="searchjob.id", index=True)
    source: str
    source_job_id: str
    title: str
    company: str | None = None
    location: str | None = None
    remote_status: RemoteStatus = RemoteStatus.unspecified
    url: str
    description: str
    compensation: str | None = None
    posted_date: str | None = None
    match_score: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
