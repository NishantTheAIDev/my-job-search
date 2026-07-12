"""add cancelled to applicationstatus enum

Revision ID: a1b2c3d4e5f6
Revises: 74d983f20c05
Create Date: 2026-06-28 17:15:00.000000

The baseline schema created the ``applicationstatus`` Postgres enum without the
``cancelled`` value (it was added to the Python ``ApplicationStatus`` model
later, for cooperative prepare-cancellation, but no migration ever taught the
DB about it). On Postgres, writing ``cancelled`` therefore fails with
``invalid input value for enum applicationstatus``. The test suite uses SQLite,
where enums are plain VARCHAR, so this gap was invisible in CI.

``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction block, so we use
Alembic's ``autocommit_block``. ``IF NOT EXISTS`` makes the migration safe to
re-run / idempotent across environments where the value may already be present.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "74d983f20c05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the 'cancelled' value to the applicationstatus enum (Postgres only)."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite (tests) stores the enum as VARCHAR — nothing to alter.
        return
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE applicationstatus ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    """No-op.

    Postgres does not support removing a value from an enum type without
    recreating the type and rewriting every dependent column, which is unsafe to
    automate here. Leaving 'cancelled' in place on downgrade is harmless.
    """
