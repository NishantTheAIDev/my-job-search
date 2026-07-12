"""add ai draft snapshot columns

Revision ID: 23746613c8c7
Revises: d3a47bb1e460
Create Date: 2026-06-28 11:39:44.314272

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "23746613c8c7"
down_revision: str | Sequence[str] | None = "d3a47bb1e460"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Adds two AI-draft snapshot columns to the application table.  The columns
    default to '' so that:
      - Postgres can add them to existing (already-prepared) rows without a
        full-table rewrite when the table is non-empty.
      - The in-memory SQLite test DB (which runs SQLModel.metadata.create_all,
        not migrations) picks up the Python-level default from the model.

    After adding the columns we backfill existing rows from the current
    tailored text so already-prepared applications have a sensible AI-draft
    baseline for the revert feature.
    """
    application = sa.table(
        "application",
        sa.column("ai_tailored_resume_text", sa.String),
        sa.column("ai_cover_letter_text", sa.String),
        sa.column("tailored_resume_text", sa.String),
        sa.column("cover_letter_text", sa.String),
    )

    op.add_column(
        "application",
        sa.Column(
            "ai_tailored_resume_text",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "application",
        sa.Column(
            "ai_cover_letter_text",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="",
        ),
    )

    # Backfill: treat the current tailored text as the AI draft baseline for
    # any application that was prepared before this migration ran.
    op.execute(
        application.update().values(
            ai_tailored_resume_text=application.c.tailored_resume_text,
            ai_cover_letter_text=application.c.cover_letter_text,
        )
    )

    # Drop the server defaults now that all rows are populated — future inserts
    # will use the Python-level model default ("") instead.
    op.alter_column("application", "ai_tailored_resume_text", server_default=None)
    op.alter_column("application", "ai_cover_letter_text", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("application", "ai_cover_letter_text")
    op.drop_column("application", "ai_tailored_resume_text")
