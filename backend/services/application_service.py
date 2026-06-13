"""Orchestrate the LLM pipeline and manage application state transitions."""

import json
import logging
import uuid
from datetime import UTC, datetime

from sqlmodel import Session, select

from backend.llm import client as llm
from backend.llm.prompts import jd_parser as jd_parser_prompts
from backend.llm.sanitize import sanitize_jd_text
from backend.models.application import Application, ApplicationStatus
from backend.models.audit_log import AuditLog
from backend.models.job_posting import JobPosting
from backend.models.resume import Resume
from backend.services import drafting_service, scoring_service, tailoring_service

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    pass


class InvalidStateError(ApplicationError):
    pass


# Pipeline stage markers persisted on Application.prep_stage while status == preparing,
# so the UI can show real progress instead of inferring it from a timeout. The frontend
# maps these keys to user-facing labels.
PREP_STAGE_PARSING = "parsing"
PREP_STAGE_SCORING = "scoring"
PREP_STAGE_TAILORING = "tailoring"
PREP_STAGE_DRAFTING = "drafting"


async def _parse_jd(description: str) -> dict:
    sanitized = sanitize_jd_text(description)
    user = jd_parser_prompts.build_user_prompt(sanitized)
    raw = await llm.call_claude(
        system=jd_parser_prompts.SYSTEM,
        user=user,
        max_tokens=1024,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("jd_parser: failed to parse response, using empty dict")
        return {}


async def prepare_application(
    job_id: uuid.UUID,
    session: Session,
) -> Application:
    """Run the full LLM pipeline, surfacing progress on a persisted Application.

    The Application row is created immediately in the ``preparing`` state and its
    ``prep_stage`` is advanced (and committed) before each LLM call, so the client
    can poll it for real-time progress. On success the row transitions to
    ``pending``; on failure it transitions to ``prep_failed`` with ``prep_error``
    set, so the UI detects failure immediately instead of inferring it from a
    timeout.

    Steps: get active resume → get job posting → create preparing row →
    parse JD → score → tailor → draft → mark pending.
    """
    # Load the active resume
    resume = session.exec(
        select(Resume).where(Resume.is_active == True)  # noqa: E712
    ).first()
    if not resume:
        raise ApplicationError("No active resume found — upload a resume first")

    # Load the job posting
    posting = session.get(JobPosting, job_id)
    if not posting:
        raise ApplicationError(f"Job posting {job_id} not found")

    # Create the row up front so the client's by-job poll resolves right away and
    # can render progress rather than waiting out a blind timeout.
    app = Application(
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=ApplicationStatus.preparing,
        prep_stage=PREP_STAGE_PARSING,
    )
    session.add(app)
    session.commit()
    session.refresh(app)

    logger.info(
        "prepare_application: job=%s starting pipeline (resume=%s app=%s)",
        job_id,
        resume.id,
        app.id,
    )

    def _advance(stage: str) -> None:
        app.prep_stage = stage
        session.add(app)
        session.commit()

    try:
        parsed_jd = await _parse_jd(posting.description)
        logger.info(
            "prepare_application: job=%s JD parsed — keys=%s",
            job_id,
            list(parsed_jd.keys()),
        )

        _advance(PREP_STAGE_SCORING)
        score, rationale, gaps = await scoring_service.score_resume(resume.text_content, parsed_jd)
        logger.info(
            "prepare_application: job=%s score=%d gaps=%d",
            job_id,
            score,
            len(gaps),
        )
        # Persist the score and propagate it to the posting as soon as we have it.
        app.match_score = score
        app.match_rationale = rationale
        posting.match_score = score
        session.add(posting)

        _advance(PREP_STAGE_TAILORING)
        (
            tailored_text,
            change_summary,
            diff_json,
            tailor_gaps,
        ) = await tailoring_service.tailor_resume(resume.text_content, parsed_jd)
        tailoring_failed = tailored_text == resume.text_content and not change_summary
        logger.info(
            "prepare_application: job=%s resume tailored (failed=%s gaps=%d)",
            job_id,
            tailoring_failed,
            len(tailor_gaps),
        )
        # Persist the tailored resume now so it can be reviewed/downloaded while
        # the cover letter is still drafting (status stays `preparing`).
        app.tailored_resume_text = tailored_text
        app.resume_diff_json = diff_json
        app.tailoring_failed = tailoring_failed
        _advance(PREP_STAGE_DRAFTING)

        cover_letter, review_notes = await drafting_service.draft_cover_letter(
            tailored_text,
            parsed_jd,
            posting.title,
            posting.company,
        )
        logger.info("prepare_application: job=%s cover letter drafted", job_id)

        app.status = ApplicationStatus.pending
        app.prep_stage = ""
        app.cover_letter_text = cover_letter
        session.add(app)
        session.commit()
        session.refresh(app)
        logger.info(
            "prepare_application: job=%s application ready id=%s status=%s",
            job_id,
            app.id,
            app.status,
        )
        return app

    except Exception as exc:
        logger.exception("prepare_application: job=%s pipeline failed: %s", job_id, exc)
        # Mark the row failed so the client sees it immediately. Use a fresh
        # rollback first in case the failing call left the session dirty.
        session.rollback()
        app.status = ApplicationStatus.prep_failed
        app.prep_stage = ""
        app.prep_error = str(exc)
        session.add(app)
        session.commit()
        raise ApplicationError(f"Pipeline failed: {exc}") from exc


def approve_application(app_id: uuid.UUID, session: Session) -> Application:
    """Transition an application from pending -> submitted.

    This is the ONLY function that may call submission_service.submit().
    Approval and audit log write happen atomically in one commit.
    """
    app = session.get(Application, app_id)
    if not app:
        raise ApplicationError(f"Application {app_id} not found")
    if app.status != ApplicationStatus.pending:
        raise InvalidStateError(
            f"Cannot approve application in status '{app.status}' — must be 'pending'"
        )

    posting = session.get(JobPosting, app.job_posting_id)
    now = datetime.now(UTC)

    logger.info(
        "approve_application: id=%s title=%r company=%r",
        app_id,
        posting.title if posting else "unknown",
        posting.company if posting else None,
    )

    # Import here to avoid circular deps and make the ONLY call site explicit
    from backend.services.submission_service import submit

    try:
        submit(app, posting, session)
        app.status = ApplicationStatus.submitted
        app.approved_at = now
        app.submitted_at = now
        audit = AuditLog(
            application_id=app.id,
            action="submitted",
            job_title=posting.title if posting else "unknown",
            company=posting.company if posting else None,
            board_url=posting.url if posting else "",
        )
        logger.info("approve_application: id=%s → submitted", app_id)
    except Exception as exc:
        logger.error("approve_application: id=%s submission failed: %s", app_id, exc)
        app.status = ApplicationStatus.failed
        audit = AuditLog(
            application_id=app.id,
            action="failed",
            job_title=posting.title if posting else "unknown",
            company=posting.company if posting else None,
            board_url=posting.url if posting else "",
            metadata_json=json.dumps({"error": str(exc)}),
        )

    session.add(app)
    session.add(audit)
    session.commit()
    session.refresh(app)
    return app


def reject_application(app_id: uuid.UUID, session: Session) -> Application:
    """Transition an application from pending -> rejected."""
    app = session.get(Application, app_id)
    if not app:
        raise ApplicationError(f"Application {app_id} not found")
    if app.status not in (ApplicationStatus.pending,):
        raise InvalidStateError(f"Cannot reject application in status '{app.status}'")

    posting = session.get(JobPosting, app.job_posting_id)
    app.status = ApplicationStatus.rejected
    app.rejected_at = datetime.now(UTC)
    audit = AuditLog(
        application_id=app.id,
        action="rejected",
        job_title=posting.title if posting else "unknown",
        company=posting.company if posting else None,
        board_url=posting.url if posting else "",
    )
    session.add(app)
    session.add(audit)
    session.commit()
    session.refresh(app)
    logger.info(
        "reject_application: id=%s title=%r company=%r → rejected",
        app_id,
        posting.title if posting else "unknown",
        posting.company if posting else None,
    )
    return app
