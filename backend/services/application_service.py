"""Orchestrate the LLM pipeline and manage application state transitions."""

import json
import logging
import uuid
from datetime import UTC, datetime

import yaml
from sqlmodel import Session, select

from backend.adapters.registry import ADAPTERS
from backend.config import settings
from backend.llm import client as llm
from backend.llm.parsing import extract_json
from backend.llm.prompts import jd_parser as jd_parser_prompts
from backend.llm.prompts import reviser as reviser_prompts
from backend.llm.sanitize import sanitize_jd_text
from backend.models.application import Application, ApplicationStatus
from backend.models.audit_log import AuditLog
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.services import drafting_service, rendercv_service, scoring_service, tailoring_service

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    pass


class InvalidStateError(ApplicationError):
    pass


def _get_owned_application(app_id: uuid.UUID, user_id: uuid.UUID, session: Session) -> Application:
    """Load an application that belongs to user_id, else raise ApplicationError.

    A foreign application is treated as not-found (same error as a missing one) so
    callers can't probe for the existence of other users' applications.
    """
    app = session.get(Application, app_id)
    if not app or app.user_id != user_id:
        raise ApplicationError(f"Application {app_id} not found")
    return app


# Pipeline stage markers persisted on Application.prep_stage while status == preparing,
# so the UI can show real progress instead of inferring it from a timeout. The frontend
# maps these keys to user-facing labels.
PREP_STAGE_PARSING = "parsing"
PREP_STAGE_SCORING = "scoring"
PREP_STAGE_TAILORING = "tailoring"
PREP_STAGE_DRAFTING = "drafting"


def _parse_llm_json(raw: str, what: str) -> dict:
    """Parse a structured LLM response, raising a user-facing error on failure.

    Used by the interactive revise/edit paths so a malformed model response
    surfaces as a clean, retryable message instead of a 500.
    """
    try:
        return extract_json(raw)
    except json.JSONDecodeError as exc:
        logger.warning("%s: failed to parse LLM response: %s", what, exc)
        raise ApplicationError(
            f"The AI response for {what} was malformed — please try again."
        ) from exc


def _resume_diff_baseline(app: Application, session: Session) -> str:
    """Text the resume diff is computed against — always the ORIGINAL uploaded
    resume, matching the initial tailoring diff.

    Revising/editing must diff against the same baseline as the first tailoring
    (the uploaded resume), not against the previous tailored version. Otherwise
    each revise re-bases the diff and the "Resume Changes" view collapses to just
    the last tiny delta, making it look like the requested change wasn't applied.
    """
    resume = session.get(Resume, app.resume_id)
    return resume.text_content if resume else (app.tailored_resume_text or "")


async def _parse_jd(description: str) -> dict:
    sanitized = sanitize_jd_text(description)
    user = jd_parser_prompts.build_user_prompt(sanitized)
    raw = await llm.call_claude(
        system=jd_parser_prompts.SYSTEM,
        user=user,
        max_tokens=1024,
    )
    try:
        return extract_json(raw)
    except json.JSONDecodeError:
        logger.warning("jd_parser: failed to parse response, using empty dict")
        return {}


def _contact_from_cv(cv: dict) -> dict:
    """Extract contact fields from a cv dict for cover-letter YAML."""
    return {
        k: cv.get(k)
        for k in ("name", "headline", "location", "email", "phone", "website", "social_networks")
        if cv.get(k)
    }


async def prepare_application(
    job_id: uuid.UUID,
    user_id: uuid.UUID,
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
    # Load the active resume for this user
    resume = session.exec(
        select(Resume).where(
            Resume.user_id == user_id,
            Resume.is_active == True,  # noqa: E712
        )
    ).first()
    if not resume:
        raise ApplicationError("No active resume found — upload a resume first")

    # Load the job posting (must belong to the same user)
    posting = session.get(JobPosting, job_id)
    if not posting or posting.user_id != user_id:
        raise ApplicationError(f"Job posting {job_id} not found")

    # Create the row up front so the client's by-job poll resolves right away and
    # can render progress rather than waiting out a blind timeout.
    app = Application(
        user_id=user_id,
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
        # Some boards (e.g. LinkedIn) only return job cards at search time, leaving
        # the description empty. Fetch it on demand now — for the one job the user is
        # preparing — so the JD parse / scoring / tailoring run on real text. Persist
        # it so re-prepares and the UI reuse it. sanitize_jd_text still runs in
        # _parse_jd, so the prompt-injection invariant is unchanged.
        if not (posting.description or "").strip():
            adapter_cls = ADAPTERS.get(posting.source)
            if adapter_cls:
                fetched = await adapter_cls().fetch_description(posting)
                if fetched:
                    posting.description = fetched
                    session.add(posting)
                    session.commit()
                    logger.info(
                        "prepare_application: job=%s fetched description (%d chars)",
                        job_id,
                        len(fetched),
                    )

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
        app.match_gaps = json.dumps(gaps)
        posting.match_score = score
        session.add(posting)

        _advance(PREP_STAGE_TAILORING)
        (
            tailored_text,
            change_summary,
            diff_json,
            tailor_gaps,
            cv_dict,
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

        # Build resume YAML from the structured cv dict (best-effort; don't fail pipeline).
        try:
            if cv_dict:
                app.resume_data_yaml = rendercv_service.build_resume_yaml(
                    cv_dict, settings.rendercv_theme
                )
        except Exception as yaml_exc:  # noqa: BLE001
            logger.warning(
                "prepare_application: job=%s failed to build resume YAML: %s", job_id, yaml_exc
            )

        _advance(PREP_STAGE_DRAFTING)

        cover_letter, review_notes, paragraphs = await drafting_service.draft_cover_letter(
            tailored_text,
            parsed_jd,
            posting.title,
            posting.company,
        )
        logger.info("prepare_application: job=%s cover letter drafted", job_id)

        # Build cover-letter YAML (best-effort).
        try:
            if paragraphs:
                contact = _contact_from_cv(cv_dict) if cv_dict else {}
                app.cover_letter_data_yaml = rendercv_service.build_cover_letter_yaml(
                    contact, paragraphs, settings.rendercv_theme
                )
        except Exception as yaml_exc:  # noqa: BLE001
            logger.warning(
                "prepare_application: job=%s failed to build cover-letter YAML: %s",
                job_id,
                yaml_exc,
            )

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


def reject_application(app_id: uuid.UUID, user_id: uuid.UUID, session: Session) -> Application:
    """Transition an application from pending -> rejected."""
    app = _get_owned_application(app_id, user_id, session)
    if app.status not in (ApplicationStatus.pending,):
        raise InvalidStateError(f"Cannot reject application in status '{app.status}'")

    posting = session.get(JobPosting, app.job_posting_id)
    app.status = ApplicationStatus.rejected
    app.rejected_at = datetime.now(UTC)
    audit = AuditLog(
        user_id=user_id,
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


def save_application(app_id: uuid.UUID, user_id: uuid.UUID, session: Session) -> Application:
    """Transition an application from pending -> saved.

    'saved' is a terminal status meaning the user wants to keep this tailored
    result for reference. There is NO external job-board submission anywhere in
    this app — 'saved' is the terminal user action. Status update and AuditLog
    are written in a single commit (mirrors reject_application).
    """
    app = _get_owned_application(app_id, user_id, session)
    if app.status != ApplicationStatus.pending:
        raise InvalidStateError(
            f"Cannot save application in status '{app.status}' — must be 'pending'"
        )

    posting = session.get(JobPosting, app.job_posting_id)
    app.status = ApplicationStatus.saved
    app.saved_at = datetime.now(UTC)
    audit = AuditLog(
        user_id=user_id,
        application_id=app.id,
        action="saved",
        job_title=posting.title if posting else "unknown",
        company=posting.company if posting else None,
        board_url=posting.url if posting else "",
    )
    session.add(app)
    session.add(audit)
    session.commit()
    session.refresh(app)
    logger.info(
        "save_application: id=%s title=%r company=%r → saved",
        app_id,
        posting.title if posting else "unknown",
        posting.company if posting else None,
    )
    return app


def create_manual_application(
    jd_text: str,
    title: str | None,
    company: str | None,
    user_id: uuid.UUID,
    session: Session,
) -> JobPosting:
    """Create a synthetic JobPosting from a pasted job description.

    The returned posting can be passed straight into prepare_application_task so
    the entire existing LLM pipeline (parse → score → tailor → draft) runs
    unchanged. sanitize_jd_text() runs inside _parse_jd, so the prompt-injection
    invariant is preserved end-to-end.

    Raises ApplicationError if no active resume exists (fail-fast before queuing).
    """
    resume = session.exec(
        select(Resume).where(
            Resume.user_id == user_id,
            Resume.is_active == True,  # noqa: E712
        )
    ).first()
    if not resume:
        raise ApplicationError("No active resume found — upload a resume first")

    posting = JobPosting(
        user_id=user_id,
        source="manual",
        source_job_id=str(uuid.uuid4()),
        search_job_id=None,
        title=title or "Pasted job description",
        company=company or None,
        url="",
        description=jd_text,
        remote_status=RemoteStatus.unspecified,
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)
    logger.info(
        "create_manual_application: posting=%s title=%r company=%r",
        posting.id,
        posting.title,
        posting.company,
    )
    return posting


async def revise_application(
    app_id: uuid.UUID,
    target: str,
    instructions: str,
    user_id: uuid.UUID,
    session: Session,
) -> Application:
    """LLM-revise the resume or cover letter given natural-language instructions.

    Only allowed while status == pending.

    Note: unlike search/prepare, this awaits the LLM call inline within the request
    session rather than offloading to a background task. The request session stays
    open for the full LLM round-trip. This is acceptable for SQLite (no connection
    pool to exhaust) and keeps the revise/edit UX synchronous; revisit if migrating
    to a pooled database.
    """
    app = _get_owned_application(app_id, user_id, session)
    if app.status != ApplicationStatus.pending:
        raise InvalidStateError(
            f"Cannot revise application in status '{app.status}' — must be 'pending'"
        )

    if target == "resume":
        # Re-parse the stored YAML to get the current cv dict.
        current_cv: dict = {}
        if app.resume_data_yaml:
            try:
                doc = yaml.safe_load(app.resume_data_yaml)
                current_cv = doc.get("cv", {}) if isinstance(doc, dict) else {}
            except Exception as parse_exc:  # noqa: BLE001
                logger.warning("revise_application: failed to parse resume YAML: %s", parse_exc)

        current_cv_json = json.dumps(current_cv, indent=2)
        user = reviser_prompts.build_revise_cv_user_prompt(current_cv_json, instructions)
        raw = await llm.call_claude(
            system=reviser_prompts.REVISE_CV_SYSTEM,
            user=user,
            max_tokens=8192,
        )
        data = _parse_llm_json(raw, "the resume revision")
        new_cv: dict = dict(data["cv"])
        new_text = rendercv_service.cv_to_text(new_cv)

        # Diff against the original uploaded resume (same baseline as the initial
        # tailoring) so the "Resume Changes" view stays cumulative and the revision
        # is visible in full context rather than collapsing to the last delta.
        from backend.services.tailoring_service import compute_diff_json

        baseline = _resume_diff_baseline(app, session)
        app.resume_data_yaml = rendercv_service.build_resume_yaml(new_cv, settings.rendercv_theme)
        app.tailored_resume_text = new_text
        app.resume_diff_json = compute_diff_json(baseline, new_text)

    elif target == "cover_letter":
        current_paragraphs: list[str] = []
        if app.cover_letter_data_yaml:
            try:
                doc = yaml.safe_load(app.cover_letter_data_yaml)
                if isinstance(doc, dict):
                    sections = doc.get("cv", {}).get("sections", {})
                    for v in sections.values():
                        if isinstance(v, list):
                            current_paragraphs = [str(p) for p in v]
                            break
            except Exception as parse_exc:  # noqa: BLE001
                logger.warning(
                    "revise_application: failed to parse cover-letter YAML: %s", parse_exc
                )
        if not current_paragraphs and app.cover_letter_text:
            # Fall back to splitting stored text into paragraphs.
            current_paragraphs = [
                p.strip() for p in app.cover_letter_text.split("\n\n") if p.strip()
            ]

        current_para_json = json.dumps(current_paragraphs, indent=2)
        user = reviser_prompts.build_revise_cover_letter_user_prompt(
            current_para_json, instructions
        )
        raw = await llm.call_claude(
            system=reviser_prompts.REVISE_COVER_LETTER_SYSTEM,
            user=user,
            max_tokens=2048,
        )
        data = _parse_llm_json(raw, "the cover letter revision")
        new_paragraphs: list[str] = [str(p) for p in data["cover_letter"]["paragraphs"]]
        new_text = "\n\n".join(new_paragraphs)

        # Rebuild cover-letter YAML; contact comes from the resume YAML if available.
        contact: dict = {}
        if app.resume_data_yaml:
            try:
                doc = yaml.safe_load(app.resume_data_yaml)
                cv_doc = doc.get("cv", {}) if isinstance(doc, dict) else {}
                contact = _contact_from_cv(cv_doc)
            except Exception:  # noqa: BLE001
                pass

        app.cover_letter_data_yaml = rendercv_service.build_cover_letter_yaml(
            contact, new_paragraphs, settings.rendercv_theme
        )
        app.cover_letter_text = new_text

    else:
        raise ApplicationError(f"Unknown target '{target}' — must be 'resume' or 'cover_letter'")

    session.add(app)
    session.commit()
    session.refresh(app)
    logger.info("revise_application: id=%s target=%s revised", app_id, target)
    return app


async def edit_application_content(
    app_id: uuid.UUID,
    target: str,
    text: str,
    user_id: uuid.UUID,
    session: Session,
) -> Application:
    """Accept free-text edits, re-structure into rendercv format, rebuild YAML + diff.

    Only allowed while status == pending.
    """
    app = _get_owned_application(app_id, user_id, session)
    if app.status != ApplicationStatus.pending:
        raise InvalidStateError(
            f"Cannot edit application in status '{app.status}' — must be 'pending'"
        )

    if target == "resume":
        user = reviser_prompts.build_structure_cv_user_prompt(text)
        raw = await llm.call_claude(
            system=reviser_prompts.STRUCTURE_CV_SYSTEM,
            user=user,
            max_tokens=8192,
        )
        data = _parse_llm_json(raw, "the edited resume")
        new_cv: dict = dict(data["cv"])
        new_text = rendercv_service.cv_to_text(new_cv)

        from backend.services.tailoring_service import compute_diff_json

        baseline = _resume_diff_baseline(app, session)
        app.resume_data_yaml = rendercv_service.build_resume_yaml(new_cv, settings.rendercv_theme)
        app.tailored_resume_text = new_text
        app.resume_diff_json = compute_diff_json(baseline, new_text)

    elif target == "cover_letter":
        user = reviser_prompts.build_structure_cover_letter_user_prompt(text)
        raw = await llm.call_claude(
            system=reviser_prompts.STRUCTURE_COVER_LETTER_SYSTEM,
            user=user,
            max_tokens=2048,
        )
        data = _parse_llm_json(raw, "the edited cover letter")
        new_paragraphs: list[str] = [str(p) for p in data["cover_letter"]["paragraphs"]]
        new_text = "\n\n".join(new_paragraphs)

        contact: dict = {}
        if app.resume_data_yaml:
            try:
                doc = yaml.safe_load(app.resume_data_yaml)
                cv_doc = doc.get("cv", {}) if isinstance(doc, dict) else {}
                contact = _contact_from_cv(cv_doc)
            except Exception:  # noqa: BLE001
                pass

        app.cover_letter_data_yaml = rendercv_service.build_cover_letter_yaml(
            contact, new_paragraphs, settings.rendercv_theme
        )
        app.cover_letter_text = new_text

    else:
        raise ApplicationError(f"Unknown target '{target}' — must be 'resume' or 'cover_letter'")

    session.add(app)
    session.commit()
    session.refresh(app)
    logger.info("edit_application_content: id=%s target=%s updated", app_id, target)
    return app
