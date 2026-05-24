import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    application_id: uuid.UUID = Field(foreign_key="application.id", index=True)
    action: str
    actor: str = "user"
    job_title: str
    company: Optional[str] = None
    board_url: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata_json: Optional[str] = None
