from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context
from backend.config import settings

# Import every model module so its table registers on SQLModel.metadata before
# autogenerate compares metadata to the database.
from backend.models import application as _application  # noqa: F401
from backend.models import audit_log as _audit_log  # noqa: F401
from backend.models import insights_cache as _insights_cache  # noqa: F401
from backend.models import job_posting as _job_posting  # noqa: F401
from backend.models import resume as _resume  # noqa: F401
from backend.models import saved_search as _saved_search  # noqa: F401
from backend.models import search_job as _search_job  # noqa: F401
from backend.models import user as _user  # noqa: F401

config = context.config

# Drive the connection from app settings rather than a hardcoded alembic.ini URL,
# so local Docker and deployed Postgres both work via DATABASE_URL.
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
