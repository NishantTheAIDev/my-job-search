"""Tests for revert_application_content and POST /applications/{id}/revert.

Critical invariants verified:
1. resume→original restores Resume.text_content; diff is recomputed; ai snapshot unchanged.
2. resume→ai_draft restores ai_tailored_resume_text; the snapshot itself is not mutated.
3. cover_letter→ai_draft restores ai_cover_letter_text; snapshot unchanged; resume diff untouched.
4. cover_letter+original is rejected: ApplicationError at service layer, HTTP 422 at route layer.
5. Non-pending applications cannot be reverted (InvalidStateError → HTTP 409).
6. Foreign / missing application → ApplicationError → HTTP 404 (tenant isolation).
7. Snapshot invariant: edit_application_content does NOT touch ai_* fields;
   revise_application DOES update them; prepare_application sets them on first run.
8. ApplicationResponse includes ai_tailored_resume_text and ai_cover_letter_text.
"""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.models.application import Application, ApplicationStatus
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.models.user import User
from backend.services import (
    application_service,
    drafting_service,
    scoring_service,
    tailoring_service,
)
from backend.services.application_service import (
    ApplicationError,
    InvalidStateError,
    edit_application_content,
    prepare_application,
    revert_application_content,
    revise_application,
)

# ---------------------------------------------------------------------------
# Fixture text constants
# ---------------------------------------------------------------------------

_ORIGINAL_RESUME = "John Doe — Software Engineer\n\nFive years of Python experience."
_AI_TAILORED_RESUME = "John Doe — Senior Python Engineer\n\nAI-tailored highlights."
_MANUAL_RESUME = "John Doe — Engineer\n\nManually written content."

_AI_COVER_LETTER = "Dear Hiring Manager,\n\nAI-drafted letter.\n\nSincerely, John"
_MANUAL_COVER_LETTER = "Dear Sir/Madam,\n\nManually written letter.\n\nBest, John"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_posting(session: Session, user_id: uuid.UUID) -> JobPosting:
    posting = JobPosting(
        user_id=user_id,
        source="test",
        source_job_id=str(uuid.uuid4()),
        title="Software Engineer",
        company="RevertCo",
        url="https://example.com/job/r",
        description="A revert-test job",
        remote_status=RemoteStatus.remote,
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)
    return posting


def _make_resume(
    session: Session,
    user_id: uuid.UUID,
    text_content: str = _ORIGINAL_RESUME,
) -> Resume:
    resume = Resume(
        user_id=user_id,
        filename="resume.txt",
        file_path="/tmp/resume.txt",
        text_content=text_content,
        is_active=True,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def _make_app(
    session: Session,
    user_id: uuid.UUID,
    status: ApplicationStatus = ApplicationStatus.pending,
    tailored_resume_text: str = _AI_TAILORED_RESUME,
    ai_tailored_resume_text: str = _AI_TAILORED_RESUME,
    cover_letter_text: str = _AI_COVER_LETTER,
    ai_cover_letter_text: str = _AI_COVER_LETTER,
) -> Application:
    posting = _make_posting(session, user_id)
    resume = _make_resume(session, user_id)
    app = Application(
        user_id=user_id,
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=status,
        tailored_resume_text=tailored_resume_text,
        ai_tailored_resume_text=ai_tailored_resume_text,
        cover_letter_text=cover_letter_text,
        ai_cover_letter_text=ai_cover_letter_text,
        match_score=75,
        match_rationale="solid match",
        match_gaps='["Docker"]',
        resume_diff_json='[{"type":"added","text":"+ tailored line","line":1}]',
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


def _patch_llm(response_text: str):
    """Stub the LLM client so no real API calls are made."""
    return patch(
        "backend.llm.client.get_client",
        return_value=AsyncMock(
            messages=AsyncMock(
                create=AsyncMock(return_value=AsyncMock(content=[AsyncMock(text=response_text)]))
            )
        ),
    )


# ---------------------------------------------------------------------------
# 1. revert resume → original
# ---------------------------------------------------------------------------


def test_revert_resume_to_original_sets_tailored_text_to_uploaded_resume(
    session: Session, user: User
):
    """tailored_resume_text must become the original uploaded Resume.text_content."""
    app = _make_app(
        session,
        user.id,
        tailored_resume_text=_MANUAL_RESUME,
        ai_tailored_resume_text=_AI_TAILORED_RESUME,
    )
    result = revert_application_content(app.id, "resume", "original", user.id, session)
    assert result.tailored_resume_text == _ORIGINAL_RESUME


def test_revert_resume_to_original_recomputes_diff_json(session: Session, user: User):
    """resume_diff_json is recomputed and different from the pre-revert AI diff."""
    app = _make_app(
        session,
        user.id,
        tailored_resume_text=_MANUAL_RESUME,
        ai_tailored_resume_text=_AI_TAILORED_RESUME,
    )
    old_diff = app.resume_diff_json
    result = revert_application_content(app.id, "resume", "original", user.id, session)
    hunks = json.loads(result.resume_diff_json)
    assert isinstance(hunks, list)
    # Diff must have changed from the pre-revert state.
    assert result.resume_diff_json != old_diff


def test_revert_resume_to_original_does_not_mutate_ai_snapshot(session: Session, user: User):
    """ai_tailored_resume_text is never touched by a revert-to-original."""
    app = _make_app(
        session,
        user.id,
        tailored_resume_text=_MANUAL_RESUME,
        ai_tailored_resume_text=_AI_TAILORED_RESUME,
    )
    result = revert_application_content(app.id, "resume", "original", user.id, session)
    assert result.ai_tailored_resume_text == _AI_TAILORED_RESUME


def test_revert_resume_to_original_status_remains_pending(session: Session, user: User):
    app = _make_app(session, user.id, tailored_resume_text=_MANUAL_RESUME)
    result = revert_application_content(app.id, "resume", "original", user.id, session)
    assert result.status == ApplicationStatus.pending


# ---------------------------------------------------------------------------
# 2. revert resume → ai_draft
# ---------------------------------------------------------------------------


def test_revert_resume_to_ai_draft_restores_snapshot_text(session: Session, user: User):
    """tailored_resume_text must become ai_tailored_resume_text (the AI snapshot)."""
    app = _make_app(
        session,
        user.id,
        tailored_resume_text=_MANUAL_RESUME,  # live = manually edited
        ai_tailored_resume_text=_AI_TAILORED_RESUME,  # snapshot = AI draft
    )
    result = revert_application_content(app.id, "resume", "ai_draft", user.id, session)
    assert result.tailored_resume_text == _AI_TAILORED_RESUME


def test_revert_resume_to_ai_draft_does_not_mutate_ai_snapshot(session: Session, user: User):
    """The ai_tailored_resume_text snapshot itself must not change after a revert."""
    app = _make_app(
        session,
        user.id,
        tailored_resume_text=_MANUAL_RESUME,
        ai_tailored_resume_text=_AI_TAILORED_RESUME,
    )
    result = revert_application_content(app.id, "resume", "ai_draft", user.id, session)
    assert result.ai_tailored_resume_text == _AI_TAILORED_RESUME


def test_revert_resume_to_ai_draft_recomputes_diff_json(session: Session, user: User):
    """resume_diff_json is a valid JSON list after revert to ai_draft."""
    app = _make_app(
        session,
        user.id,
        tailored_resume_text=_MANUAL_RESUME,
        ai_tailored_resume_text=_AI_TAILORED_RESUME,
    )
    result = revert_application_content(app.id, "resume", "ai_draft", user.id, session)
    hunks = json.loads(result.resume_diff_json)
    assert isinstance(hunks, list)


# ---------------------------------------------------------------------------
# 3. revert cover_letter → ai_draft
# ---------------------------------------------------------------------------


def test_revert_cover_letter_to_ai_draft_restores_snapshot_text(session: Session, user: User):
    app = _make_app(
        session,
        user.id,
        cover_letter_text=_MANUAL_COVER_LETTER,
        ai_cover_letter_text=_AI_COVER_LETTER,
    )
    result = revert_application_content(app.id, "cover_letter", "ai_draft", user.id, session)
    assert result.cover_letter_text == _AI_COVER_LETTER


def test_revert_cover_letter_to_ai_draft_does_not_mutate_ai_snapshot(session: Session, user: User):
    app = _make_app(
        session,
        user.id,
        cover_letter_text=_MANUAL_COVER_LETTER,
        ai_cover_letter_text=_AI_COVER_LETTER,
    )
    result = revert_application_content(app.id, "cover_letter", "ai_draft", user.id, session)
    assert result.ai_cover_letter_text == _AI_COVER_LETTER


def test_revert_cover_letter_to_ai_draft_does_not_touch_resume_diff(session: Session, user: User):
    """Reverting a cover letter must leave resume_diff_json unchanged."""
    app = _make_app(
        session,
        user.id,
        cover_letter_text=_MANUAL_COVER_LETTER,
        ai_cover_letter_text=_AI_COVER_LETTER,
    )
    pre_diff = app.resume_diff_json
    result = revert_application_content(app.id, "cover_letter", "ai_draft", user.id, session)
    assert result.resume_diff_json == pre_diff


# ---------------------------------------------------------------------------
# 4. cover_letter + original → rejected by service before ownership check
# ---------------------------------------------------------------------------


def test_revert_cover_letter_to_original_raises_application_error(session: Session, user: User):
    """Service-level: cover_letter+original raises ApplicationError (no uploaded original)."""
    app = _make_app(session, user.id)
    with pytest.raises(ApplicationError, match="no uploaded original"):
        revert_application_content(app.id, "cover_letter", "original", user.id, session)


def test_revert_cover_letter_to_original_rejected_before_ownership_check(
    session: Session, user: User, other_user: User
):
    """cover_letter+original raises ApplicationError even for a foreign app —
    the cover-letter check happens before the ownership/status check."""
    app = _make_app(session, user.id)
    with pytest.raises(ApplicationError, match="no uploaded original"):
        revert_application_content(app.id, "cover_letter", "original", other_user.id, session)


# ---------------------------------------------------------------------------
# 5. Non-pending application → InvalidStateError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_status",
    [
        ApplicationStatus.saved,
        ApplicationStatus.rejected,
        ApplicationStatus.preparing,
        ApplicationStatus.prep_failed,
    ],
)
def test_revert_resume_non_pending_raises_invalid_state_error(
    session: Session, user: User, bad_status: ApplicationStatus
):
    app = _make_app(session, user.id, status=bad_status)
    with pytest.raises(InvalidStateError):
        revert_application_content(app.id, "resume", "original", user.id, session)


def test_revert_cover_letter_saved_status_raises_invalid_state_error(session: Session, user: User):
    app = _make_app(session, user.id, status=ApplicationStatus.saved)
    with pytest.raises(InvalidStateError):
        revert_application_content(app.id, "cover_letter", "ai_draft", user.id, session)


# ---------------------------------------------------------------------------
# 6. Foreign / missing application → ApplicationError (tenant isolation → 404)
# ---------------------------------------------------------------------------


def test_revert_missing_application_raises_application_error(session: Session, user: User):
    with pytest.raises(ApplicationError):
        revert_application_content(uuid.uuid4(), "resume", "ai_draft", user.id, session)


def test_revert_other_users_application_raises_application_error(
    session: Session, user: User, other_user: User
):
    """Cross-tenant: user B cannot revert user A's application (returns same error as missing)."""
    app = _make_app(session, user.id)
    with pytest.raises(ApplicationError):
        revert_application_content(app.id, "resume", "ai_draft", other_user.id, session)


def test_revert_other_users_application_leaves_row_unchanged(
    session: Session, user: User, other_user: User
):
    """A failed cross-tenant revert attempt must not mutate the original application."""
    app = _make_app(session, user.id, tailored_resume_text=_AI_TAILORED_RESUME)
    with pytest.raises(ApplicationError):
        revert_application_content(app.id, "resume", "original", other_user.id, session)
    session.refresh(app)
    assert app.tailored_resume_text == _AI_TAILORED_RESUME


# ---------------------------------------------------------------------------
# 7a. Snapshot invariant: edit_application_content does NOT touch ai_* fields
# ---------------------------------------------------------------------------

_EDIT_CV_RESPONSE = json.dumps(
    {
        "cv": {
            "name": "John Doe",
            "sections": {
                "Experience": [
                    {
                        "company": "Acme",
                        "position": "Engineer",
                        "start_date": "2020",
                        "end_date": "2023",
                        "highlights": ["Built Python APIs"],
                    }
                ]
            },
        },
        "review_notes": "Structured.",
    }
)

_EDIT_CL_RESPONSE = json.dumps(
    {
        "cover_letter": {
            "paragraphs": [
                "Dear Hiring Manager,",
                "I am excited about this role.",
                "Sincerely, John",
            ]
        },
        "review_notes": "Structured.",
    }
)


@pytest.mark.asyncio
async def test_edit_resume_does_not_change_ai_tailored_resume_snapshot(
    session: Session, user: User
):
    """edit_application_content updates tailored_resume_text but NOT ai_tailored_resume_text."""
    app = _make_app(
        session,
        user.id,
        tailored_resume_text=_AI_TAILORED_RESUME,
        ai_tailored_resume_text=_AI_TAILORED_RESUME,
    )
    saved_snapshot = app.ai_tailored_resume_text

    with _patch_llm(_EDIT_CV_RESPONSE):
        updated = await edit_application_content(
            app.id,
            "resume",
            "John Doe\n\nEngineer at Acme, built Python APIs.",
            user.id,
            session,
        )

    assert updated.ai_tailored_resume_text == saved_snapshot


@pytest.mark.asyncio
async def test_edit_cover_letter_does_not_change_ai_cover_letter_snapshot(
    session: Session, user: User
):
    """edit_application_content does NOT touch ai_cover_letter_text."""
    app = _make_app(
        session,
        user.id,
        cover_letter_text=_AI_COVER_LETTER,
        ai_cover_letter_text=_AI_COVER_LETTER,
    )
    saved_snapshot = app.ai_cover_letter_text

    with _patch_llm(_EDIT_CL_RESPONSE):
        updated = await edit_application_content(
            app.id,
            "cover_letter",
            "Dear Sir, I am interested. Regards, John",
            user.id,
            session,
        )

    assert updated.ai_cover_letter_text == saved_snapshot


# ---------------------------------------------------------------------------
# 7b. Snapshot invariant: revise_application DOES update ai_* snapshots
# ---------------------------------------------------------------------------

_REVISE_CV_RESPONSE = json.dumps(
    {
        "cv": {
            "name": "John Doe",
            "sections": {
                "Experience": [
                    {
                        "company": "Acme",
                        "position": "Senior Engineer",
                        "start_date": "2020",
                        "end_date": "2023",
                        "highlights": ["Built REST APIs serving 10 M req/day"],
                    }
                ]
            },
        },
        "review_notes": "Added metric.",
    }
)

_REVISE_CL_RESPONSE = json.dumps(
    {
        "cover_letter": {
            "paragraphs": [
                "Revised opening paragraph.",
                "Strong body paragraph.",
                "Confident closing.",
            ]
        },
        "review_notes": "Sharpened tone.",
    }
)


@pytest.mark.asyncio
async def test_revise_resume_updates_ai_tailored_resume_snapshot(session: Session, user: User):
    """revise_application DOES update ai_tailored_resume_text to the new LLM output."""
    app = _make_app(
        session,
        user.id,
        tailored_resume_text="Old AI output",
        ai_tailored_resume_text="Old AI output",
    )

    with _patch_llm(_REVISE_CV_RESPONSE):
        updated = await revise_application(
            app.id, "resume", "Add more impact to bullet points.", user.id, session
        )

    # After a revise, the live text and the AI snapshot should both be updated.
    assert updated.tailored_resume_text == updated.ai_tailored_resume_text
    assert updated.ai_tailored_resume_text != "Old AI output"


@pytest.mark.asyncio
async def test_revise_cover_letter_updates_ai_cover_letter_snapshot(session: Session, user: User):
    """revise_application DOES update ai_cover_letter_text."""
    app = _make_app(
        session,
        user.id,
        cover_letter_text="Old cover letter",
        ai_cover_letter_text="Old cover letter",
    )

    with _patch_llm(_REVISE_CL_RESPONSE):
        updated = await revise_application(
            app.id, "cover_letter", "Make the opening punchier.", user.id, session
        )

    assert updated.cover_letter_text == updated.ai_cover_letter_text
    assert updated.ai_cover_letter_text != "Old cover letter"


# ---------------------------------------------------------------------------
# 7c. Snapshot invariant: prepare_application sets both ai_* fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_sets_ai_tailored_resume_and_cover_letter_snapshots(
    session: Session, user: User, monkeypatch
):
    """After prepare_application, ai_tailored_resume_text and ai_cover_letter_text
    must both equal the live fields (initial AI output, before any user edits)."""
    resume = Resume(
        user_id=user.id,
        filename="r.txt",
        file_path="/tmp/r.txt",
        text_content="original uploaded resume",
        is_active=True,
    )
    posting = JobPosting(
        user_id=user.id,
        source="test",
        source_job_id=str(uuid.uuid4()),
        title="Engineer",
        company="Acme",
        url="https://example.com",
        description="A job description",
        remote_status=RemoteStatus.remote,
    )
    session.add(resume)
    session.add(posting)
    session.commit()
    session.refresh(posting)

    async def _fake_parse(description):
        return {"title": "Engineer"}

    async def _fake_score(resume_text, parsed):
        return (80, "good match", [])

    async def _fake_tailor(resume_text, parsed):
        return (
            "AI-tailored resume text",
            "made changes",
            '[{"type":"added","text":"+ line","line":1}]',
            [],
            {},
        )

    async def _fake_draft(text, parsed, title, company):
        return ("AI-drafted cover letter", "", ["AI-drafted cover letter"])

    monkeypatch.setattr(application_service, "_parse_jd", _fake_parse)
    monkeypatch.setattr(scoring_service, "score_resume", _fake_score)
    monkeypatch.setattr(tailoring_service, "tailor_resume", _fake_tailor)
    monkeypatch.setattr(drafting_service, "draft_cover_letter", _fake_draft)

    app = await prepare_application(posting.id, user.id, session)

    assert app.ai_tailored_resume_text == "AI-tailored resume text"
    assert app.ai_cover_letter_text == "AI-drafted cover letter"
    # On first prepare the snapshot must equal the live text.
    assert app.ai_tailored_resume_text == app.tailored_resume_text
    assert app.ai_cover_letter_text == app.cover_letter_text


# ---------------------------------------------------------------------------
# 8. ApplicationResponse includes ai_tailored_resume_text + ai_cover_letter_text
# ---------------------------------------------------------------------------


def test_get_application_response_includes_ai_snapshot_fields(
    client: TestClient, session: Session, user: User
):
    """GET /applications/{id} must return ai_tailored_resume_text and ai_cover_letter_text."""
    app = _make_app(
        session,
        user.id,
        tailored_resume_text="Live resume",
        ai_tailored_resume_text="AI resume snapshot",
        cover_letter_text="Live cover letter",
        ai_cover_letter_text="AI cover letter snapshot",
    )
    response = client.get(f"/applications/{app.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["ai_tailored_resume_text"] == "AI resume snapshot"
    assert body["ai_cover_letter_text"] == "AI cover letter snapshot"


# ---------------------------------------------------------------------------
# HTTP route: POST /applications/{id}/revert
# ---------------------------------------------------------------------------


def test_revert_route_cover_letter_original_returns_422(
    client: TestClient, session: Session, user: User
):
    """Router rejects cover_letter+original before calling the service → HTTP 422."""
    app = _make_app(session, user.id)
    resp = client.post(
        f"/applications/{app.id}/revert",
        json={"target": "cover_letter", "to": "original"},
    )
    assert resp.status_code == 422


def test_revert_route_non_pending_returns_409(client: TestClient, session: Session, user: User):
    app = _make_app(session, user.id, status=ApplicationStatus.saved)
    resp = client.post(
        f"/applications/{app.id}/revert",
        json={"target": "resume", "to": "original"},
    )
    assert resp.status_code == 409


def test_revert_route_rejected_app_returns_409(client: TestClient, session: Session, user: User):
    app = _make_app(session, user.id, status=ApplicationStatus.rejected)
    resp = client.post(
        f"/applications/{app.id}/revert",
        json={"target": "resume", "to": "ai_draft"},
    )
    assert resp.status_code == 409


def test_revert_route_missing_app_returns_404(client: TestClient):
    resp = client.post(
        f"/applications/{uuid.uuid4()}/revert",
        json={"target": "resume", "to": "ai_draft"},
    )
    assert resp.status_code == 404


def test_revert_route_other_users_app_returns_404(
    session: Session, user: User, other_user: User, make_client
):
    app = _make_app(session, user.id)
    client_b = make_client(other_user)
    resp = client_b.post(
        f"/applications/{app.id}/revert",
        json={"target": "resume", "to": "ai_draft"},
    )
    assert resp.status_code == 404


def test_revert_route_resume_original_happy_path(client: TestClient, session: Session, user: User):
    """resume→original: HTTP 200 with tailored_resume_text == uploaded Resume.text_content."""
    app = _make_app(
        session,
        user.id,
        tailored_resume_text=_MANUAL_RESUME,
        ai_tailored_resume_text=_AI_TAILORED_RESUME,
    )
    resp = client.post(
        f"/applications/{app.id}/revert",
        json={"target": "resume", "to": "original"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tailored_resume_text"] == _ORIGINAL_RESUME
    # AI snapshot must be preserved in the response.
    assert body["ai_tailored_resume_text"] == _AI_TAILORED_RESUME


def test_revert_route_resume_ai_draft_happy_path(client: TestClient, session: Session, user: User):
    """resume→ai_draft: HTTP 200 with tailored_resume_text restored to AI snapshot."""
    app = _make_app(
        session,
        user.id,
        tailored_resume_text=_MANUAL_RESUME,
        ai_tailored_resume_text=_AI_TAILORED_RESUME,
    )
    resp = client.post(
        f"/applications/{app.id}/revert",
        json={"target": "resume", "to": "ai_draft"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tailored_resume_text"] == _AI_TAILORED_RESUME
    assert body["ai_tailored_resume_text"] == _AI_TAILORED_RESUME


def test_revert_route_cover_letter_ai_draft_happy_path(
    client: TestClient, session: Session, user: User
):
    """cover_letter→ai_draft: HTTP 200 with cover_letter_text restored to AI snapshot."""
    app = _make_app(
        session,
        user.id,
        cover_letter_text=_MANUAL_COVER_LETTER,
        ai_cover_letter_text=_AI_COVER_LETTER,
    )
    resp = client.post(
        f"/applications/{app.id}/revert",
        json={"target": "cover_letter", "to": "ai_draft"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cover_letter_text"] == _AI_COVER_LETTER
    assert body["ai_cover_letter_text"] == _AI_COVER_LETTER
