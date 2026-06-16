import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Resume(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    filename: str
    file_path: str
    text_content: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True
