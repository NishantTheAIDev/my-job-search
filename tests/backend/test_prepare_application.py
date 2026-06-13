"""Tests for the staged prepare pipeline.

Verifies that prepare_application:
1. Creates the Application row up front in the `preparing` state.
2. Transitions to `pending` with populated fields on success.
3. Transitions to `prep_failed` (with prep_error) when a stage raises, and
   re-raises ApplicationError.
4. Raises (without orphaning a row) when there is no active resume.
"""

import uuid

import pytest
from sqlmodel import Session, select

from backend.models.application import Application, ApplicationStatus
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.services import (
    application_service,
    drafting_service,
    scoring_service,
    tailoring_service,
)
from backend.services.application_service import ApplicationError, prepare_application


def _seed(session: Session) -> JobPosting:
    resume = Resume(
        filename="r.txt", file_path="/tmp/r.txt", text_content="original resume", is_active=True
    )
    posting = JobPosting(
        source="test",
        source_job_id="p1",
        title="Software Engineer",
        company="Acme",
        url="https://example.com/job/1",
        description="A test job description",
        remote_status=RemoteStatus.remote,
    )
    session.add(resume)
    session.add(posting)
    session.commit()
    session.refresh(posting)
    return posting


def _patch_pipeline(monkeypatch, *, fail_stage: str | None = None) -> None:
    async def fake_parse_jd(description):
        if fail_stage == "parsing":
            raise RuntimeError("parse boom")
        return {"title": "Software Engineer"}

    async def fake_score(resume_text, parsed):
        if fail_stage == "scoring":
            raise RuntimeError("score boom")
        return (75, "solid match", ["a gap"])

    async def fake_tailor(resume_text, parsed):
        if fail_stage == "tailoring":
            raise RuntimeError("tailor boom")
        return ("tailored resume", "made changes", '[{"type":"added","text":"x","line":1}]', [])

    async def fake_draft(text, parsed, title, company):
        if fail_stage == "drafting":
            raise RuntimeError("draft boom")
        return ("Dear hiring manager", [])

    monkeypatch.setattr(application_service, "_parse_jd", fake_parse_jd)
    monkeypatch.setattr(scoring_service, "score_resume", fake_score)
    monkeypatch.setattr(tailoring_service, "tailor_resume", fake_tailor)
    monkeypatch.setattr(drafting_service, "draft_cover_letter", fake_draft)


@pytest.mark.asyncio
async def test_prepare_success_transitions_to_pending(session: Session, monkeypatch):
    posting = _seed(session)
    _patch_pipeline(monkeypatch)

    app = await prepare_application(posting.id, session)

    assert app.status == ApplicationStatus.pending
    assert app.prep_stage == ""
    assert app.prep_error == ""
    assert app.tailored_resume_text == "tailored resume"
    assert app.cover_letter_text == "Dear hiring manager"
    assert app.match_score == 75
    # match_score is also propagated back to the posting
    session.refresh(posting)
    assert posting.match_score == 75


@pytest.mark.asyncio
async def test_prepare_failure_transitions_to_prep_failed(session: Session, monkeypatch):
    posting = _seed(session)
    _patch_pipeline(monkeypatch, fail_stage="tailoring")

    with pytest.raises(ApplicationError):
        await prepare_application(posting.id, session)

    # Exactly one row exists and it records the failure for the client to see.
    app = session.exec(
        select(Application).where(Application.job_posting_id == posting.id)
    ).one()
    assert app.status == ApplicationStatus.prep_failed
    assert "tailor boom" in app.prep_error
    assert app.prep_stage == ""


@pytest.mark.asyncio
async def test_tailored_resume_persisted_before_drafting(session: Session, monkeypatch):
    # If drafting fails, the tailored resume produced by the earlier stage must
    # still be persisted (it is committed before drafting begins) so it remains
    # reviewable/downloadable.
    posting = _seed(session)
    _patch_pipeline(monkeypatch, fail_stage="drafting")

    with pytest.raises(ApplicationError):
        await prepare_application(posting.id, session)

    app = session.exec(
        select(Application).where(Application.job_posting_id == posting.id)
    ).one()
    assert app.status == ApplicationStatus.prep_failed
    assert app.tailored_resume_text == "tailored resume"
    assert app.cover_letter_text == ""


@pytest.mark.asyncio
async def test_prepare_without_active_resume_raises_and_creates_no_row(
    session: Session, monkeypatch
):
    posting = _seed(session)
    # Deactivate the only resume.
    resume = session.exec(select(Resume)).one()
    resume.is_active = False
    session.add(resume)
    session.commit()
    _patch_pipeline(monkeypatch)

    with pytest.raises(ApplicationError):
        await prepare_application(posting.id, session)

    rows = session.exec(select(Application)).all()
    assert rows == []


@pytest.mark.asyncio
async def test_prepare_missing_posting_raises(session: Session, monkeypatch):
    _seed(session)
    _patch_pipeline(monkeypatch)

    with pytest.raises(ApplicationError):
        await prepare_application(uuid.uuid4(), session)
