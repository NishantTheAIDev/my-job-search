import logging

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from backend.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url, echo=False)

# Columns added after the initial schema shipped. SQLModel.create_all() only
# creates missing tables, never adds columns to existing ones, and the project
# has no migration tool — so apply these additive, idempotent ALTERs by hand to
# preserve existing dev data (resumes, searches, prior applications).
_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "application": {
        "prep_stage": "VARCHAR NOT NULL DEFAULT ''",
        "prep_error": "VARCHAR NOT NULL DEFAULT ''",
        "resume_data_yaml": "VARCHAR NOT NULL DEFAULT ''",
        "cover_letter_data_yaml": "VARCHAR NOT NULL DEFAULT ''",
        "tailoring_failed": "BOOLEAN NOT NULL DEFAULT 0",
        "match_gaps": "VARCHAR NOT NULL DEFAULT '[]'",
        "saved_at": "DATETIME",
    },
    "jobposting": {
        # Phase 1 relevance scoring — nullable, so no NOT NULL/default needed.
        "relevance_score": "INTEGER",
    },
    "searchjob": {
        # Phase 2 progress counters.
        "completed_adapters": "INTEGER NOT NULL DEFAULT 0",
        "total_adapters": "INTEGER NOT NULL DEFAULT 0",
    },
}


def _apply_additive_migrations() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDITIVE_COLUMNS.items():
            if table not in existing_tables:
                continue  # create_all() just made it with every column
            present = {col["name"] for col in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name in present:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                logger.info("migration: added column %s.%s", table, name)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _apply_additive_migrations()


def get_session():
    with Session(engine) as session:
        yield session
