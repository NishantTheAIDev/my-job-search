import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class RemoteStatus(str, Enum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"
    unspecified = "unspecified"


class SearchCriteria(SQLModel):
    query: str
    location: Optional[str] = None
    remote_only: bool = False
    employment_type: Optional[str] = None
    seniority: Optional[str] = None
    posted_within_days: Optional[int] = None
    page: int = Field(default=1, ge=1, le=50)


class JobPosting(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    search_job_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="searchjob.id", index=True
    )
    source: str
    source_job_id: str
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    remote_status: RemoteStatus = RemoteStatus.unspecified
    url: str
    description: str
    compensation: Optional[str] = None
    posted_date: Optional[str] = None
    match_score: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
