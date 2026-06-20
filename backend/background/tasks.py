"""FastAPI BackgroundTasks wrappers for async work that needs a DB session."""

import asyncio
import logging
import uuid

from sqlmodel import Session

from backend.database import engine
from backend.models.job_posting import SearchCriteria
from backend.services.search_service import run_search

logger = logging.getLogger(__name__)


def start_search_task(
    search_job_id: uuid.UUID,
    criteria: SearchCriteria,
) -> None:
    """Synchronous wrapper called by FastAPI BackgroundTasks.

    FastAPI runs background tasks in a thread pool, so asyncio.run() is
    safe here — there is no running event loop in the worker thread.
    Each task opens its own session because the request session is closed
    before background tasks execute.
    """
    logger.info("task start: search search_job_id=%s query=%r", search_job_id, criteria.query)
    try:
        with Session(engine) as session:
            asyncio.run(run_search(search_job_id, criteria, session))
        logger.info("task done: search search_job_id=%s", search_job_id)
    except Exception:
        logger.exception("task error: search search_job_id=%s", search_job_id)


def prepare_application_task(
    job_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Sync wrapper for the async prepare_application pipeline."""
    from backend.services.application_service import prepare_application

    logger.info("task start: prepare_application job_id=%s user_id=%s", job_id, user_id)
    try:
        with Session(engine) as session:
            asyncio.run(prepare_application(job_id, user_id, session))
        logger.info("task done: prepare_application job_id=%s", job_id)
    except Exception:
        logger.exception("task error: prepare_application job_id=%s", job_id)
