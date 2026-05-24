"""Submit an approved application to a job board.

Called ONLY from application_service.approve_application().
For MVP, this is a stub that logs the submission — real board-specific
submission (form-fill, email, API) is a future enhancement.
"""

import logging

from sqlmodel import Session

from backend.models.application import Application
from backend.models.job_posting import JobPosting

logger = logging.getLogger(__name__)


def submit(app: Application, posting: JobPosting | None, session: Session) -> None:
    """Log the submission. Future: post to board API or send email."""
    title = posting.title if posting else "unknown role"
    company = posting.company if posting else "unknown company"
    url = posting.url if posting else ""
    logger.info(
        "APPLICATION SUBMITTED: application_id=%s title=%r company=%r url=%s",
        app.id,
        title,
        company,
        url,
    )
    # Future: dispatch to board-specific submission handler based on posting.source
