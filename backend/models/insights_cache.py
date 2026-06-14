import uuid
from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class InsightsCache(SQLModel, table=True):
    """Persisted cache for insights sections keyed by (section, region)."""

    __tablename__ = "insightscache"
    __table_args__ = (
        UniqueConstraint("section", "region", name="uq_insightscache_section_region"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    section: str = Field(index=True)
    region: str = Field(index=True)
    # JSON-encoded payload stored as a text column
    payload: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
