import logging

from sqlmodel import Session, SQLModel, create_engine

from backend.config import settings

logger = logging.getLogger(__name__)

# Postgres connection pool tuned for concurrent multi-user load. pool_pre_ping
# recycles connections dropped by the server (and by serverless Postgres that
# scales to zero, e.g. Supabase/Neon) instead of handing out a dead one.
engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
)


def create_db_and_tables() -> None:
    """Create tables directly from SQLModel metadata.

    Dev/prod schema is owned by Alembic (`alembic upgrade head`); this is kept
    for the in-memory SQLite test fixture, which builds the schema from metadata.
    """
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
