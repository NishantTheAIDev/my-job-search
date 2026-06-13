"""Tests for revise_application and edit_application_content gating.

Critical invariants:
1. Both functions raise InvalidStateError when status != pending.
2. The HTTP routes return 409 for non-pending applications.
3. submission_service.submit() is never called during revise or edit.
4. Happy-path revise updates tailored_resume_text, resume_data_yaml, resume_diff_json.
5. Happy-path edit updates cover_letter_text, cover_letter_data_yaml.
"""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.models.application import Application, ApplicationStatus
from backend.models.job_posting import JobPosting, RemoteStatus
from backend.models.resume import Resume
from backend.services.application_service import (
    InvalidStateError,
    edit_application_content,
    revise_application,
)

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_RESUME_YAML = yaml.dump(
    {
        "cv": {
            "name": "Jane Smith",
            "sections": {
                "Experience": [
                    {
                        "company": "Acme",
                        "position": "Engineer",
                        "start_date": "2020",
                        "end_date": "2023",
                        "highlights": ["Built APIs"],
                    }
                ]
            },
        },
        "design": {"theme": "engineeringresumes"},
    }
)

_COVER_LETTER_YAML = yaml.dump(
    {
        "cv": {
            "name": "Jane Smith",
            "sections": {"Cover Letter": ["Paragraph one.", "Paragraph two."]},
        },
        "design": {"theme": "engineeringresumes"},
    }
)


def _make_posting(session: Session) -> JobPosting:
    posting = JobPosting(
        source="test",
        source_job_id=str(uuid.uuid4()),
        title="Software Engineer",
        company="Acme Corp",
        url="https://example.com/job/1",
        description="A test job",
        remote_status=RemoteStatus.remote,
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)
    return posting


def _make_resume(session: Session) -> Resume:
    resume = Resume(
        filename="test.txt",
        file_path="/tmp/test.txt",
        text_content="Jane Smith, Software Engineer",
        is_active=True,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def _make_app(
    session: Session,
    status: ApplicationStatus = ApplicationStatus.pending,
) -> Application:
    posting = _make_posting(session)
    resume = _make_resume(session)
    app = Application(
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=status,
        tailored_resume_text="Original resume text.",
        cover_letter_text="Original cover letter.",
        resume_data_yaml=_RESUME_YAML,
        cover_letter_data_yaml=_COVER_LETTER_YAML,
        match_score=70,
        match_rationale="decent match",
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


# ---------------------------------------------------------------------------
# LLM mock helpers
# ---------------------------------------------------------------------------

_REVISED_CV = {
    "name": "Jane Smith",
    "sections": {
        "Experience": [
            {
                "company": "Acme",
                "position": "Senior Engineer",
                "start_date": "2020",
                "end_date": "2023",
                "highlights": ["Built REST APIs serving 10M req/day", "Led team of 4"],
            }
        ]
    },
}

_REVISE_CV_RESPONSE = json.dumps(
    {"cv": _REVISED_CV, "review_notes": "Added lead metric to highlight."}
)

_REVISED_PARAGRAPHS = [
    "Updated opening paragraph.",
    "Strong body paragraph with specifics.",
    "Confident closing.",
]

_REVISE_CL_RESPONSE = json.dumps(
    {
        "cover_letter": {"paragraphs": _REVISED_PARAGRAPHS},
        "review_notes": "Sharpened tone.",
    }
)

# Responses for edit_application_content (structure prompts)
_EDIT_CV_RESPONSE = _REVISE_CV_RESPONSE  # same shape
_EDIT_CL_RESPONSE = _REVISE_CL_RESPONSE  # same shape


def _patch_llm(response_text: str):
    return patch(
        "backend.llm.client.get_client",
        return_value=AsyncMock(
            messages=AsyncMock(
                create=AsyncMock(
                    return_value=AsyncMock(content=[AsyncMock(text=response_text)])
                )
            )
        ),
    )


# ---------------------------------------------------------------------------
# revise_application — gate: non-pending statuses must raise InvalidStateError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_status",
    [
        ApplicationStatus.submitted,
        ApplicationStatus.rejected,
        ApplicationStatus.failed,
        ApplicationStatus.preparing,
        ApplicationStatus.prep_failed,
    ],
)
async def test_revise_application_raises_for_non_pending(session: Session, bad_status):
    app = _make_app(session, status=bad_status)
    with pytest.raises(InvalidStateError):
        await revise_application(app.id, "resume", "Make it shorter.", session)


@pytest.mark.asyncio
async def test_revise_application_not_found_raises_application_error(session: Session):
    from backend.services.application_service import ApplicationError

    with pytest.raises(ApplicationError):
        await revise_application(uuid.uuid4(), "resume", "any", session)


# ---------------------------------------------------------------------------
# revise_application — gate: submission_service.submit() is never called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_resume_does_not_call_submit(session: Session):
    app = _make_app(session)
    with _patch_llm(_REVISE_CV_RESPONSE), patch(
        "backend.services.submission_service.submit"
    ) as mock_submit:
        await revise_application(app.id, "resume", "Make bullets stronger.", session)
    mock_submit.assert_not_called()


@pytest.mark.asyncio
async def test_revise_cover_letter_does_not_call_submit(session: Session):
    app = _make_app(session)
    with _patch_llm(_REVISE_CL_RESPONSE), patch(
        "backend.services.submission_service.submit"
    ) as mock_submit:
        await revise_application(app.id, "cover_letter", "Shorter please.", session)
    mock_submit.assert_not_called()


# ---------------------------------------------------------------------------
# revise_application — happy path: resume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_resume_updates_tailored_text(session: Session):
    app = _make_app(session)
    original_text = app.tailored_resume_text
    with _patch_llm(_REVISE_CV_RESPONSE):
        updated = await revise_application(app.id, "resume", "Add more impact.", session)
    assert updated.tailored_resume_text != original_text
    assert updated.tailored_resume_text  # not empty


@pytest.mark.asyncio
async def test_revise_resume_updates_resume_data_yaml(session: Session):
    app = _make_app(session)
    with _patch_llm(_REVISE_CV_RESPONSE):
        updated = await revise_application(app.id, "resume", "Restructure.", session)
    assert updated.resume_data_yaml
    doc = yaml.safe_load(updated.resume_data_yaml)
    assert "cv" in doc
    assert "design" in doc


@pytest.mark.asyncio
async def test_revise_resume_updates_diff_json(session: Session):
    app = _make_app(session)
    with _patch_llm(_REVISE_CV_RESPONSE):
        updated = await revise_application(app.id, "resume", "Rephrase bullets.", session)
    hunks = json.loads(updated.resume_diff_json)
    assert isinstance(hunks, list)
    # Regression guard: the diff must be computed against the PREVIOUS text, not
    # the newly-assigned text — otherwise it self-diffs and shows no changes.
    assert any(h["type"] in ("added", "removed") for h in hunks)


@pytest.mark.asyncio
async def test_revise_resume_status_remains_pending(session: Session):
    app = _make_app(session)
    with _patch_llm(_REVISE_CV_RESPONSE):
        updated = await revise_application(app.id, "resume", "Shorten.", session)
    assert updated.status == ApplicationStatus.pending


# ---------------------------------------------------------------------------
# revise_application — happy path: cover_letter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_cover_letter_updates_text(session: Session):
    app = _make_app(session)
    original = app.cover_letter_text
    with _patch_llm(_REVISE_CL_RESPONSE):
        updated = await revise_application(app.id, "cover_letter", "Be more concise.", session)
    assert updated.cover_letter_text != original
    assert updated.cover_letter_text == "\n\n".join(_REVISED_PARAGRAPHS)


@pytest.mark.asyncio
async def test_revise_cover_letter_updates_yaml(session: Session):
    app = _make_app(session)
    with _patch_llm(_REVISE_CL_RESPONSE):
        updated = await revise_application(app.id, "cover_letter", "Stronger close.", session)
    assert updated.cover_letter_data_yaml
    doc = yaml.safe_load(updated.cover_letter_data_yaml)
    sections = doc["cv"]["sections"]
    all_paras = [p for paras in sections.values() for p in paras]
    assert _REVISED_PARAGRAPHS[0] in all_paras


@pytest.mark.asyncio
async def test_revise_cover_letter_status_remains_pending(session: Session):
    app = _make_app(session)
    with _patch_llm(_REVISE_CL_RESPONSE):
        updated = await revise_application(app.id, "cover_letter", "Tweak tone.", session)
    assert updated.status == ApplicationStatus.pending


# ---------------------------------------------------------------------------
# revise_application — invalid target
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_unknown_target_raises_application_error(session: Session):
    from backend.services.application_service import ApplicationError

    app = _make_app(session)
    with _patch_llm("{}"), pytest.raises(ApplicationError, match="Unknown target"):
        await revise_application(app.id, "bio", "Change something.", session)


# ---------------------------------------------------------------------------
# edit_application_content — gate: non-pending statuses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_status",
    [
        ApplicationStatus.submitted,
        ApplicationStatus.rejected,
        ApplicationStatus.failed,
    ],
)
async def test_edit_raises_for_non_pending(session: Session, bad_status):
    app = _make_app(session, status=bad_status)
    with pytest.raises(InvalidStateError):
        await edit_application_content(app.id, "resume", "Some text.", session)


@pytest.mark.asyncio
async def test_edit_not_found_raises_application_error(session: Session):
    from backend.services.application_service import ApplicationError

    with pytest.raises(ApplicationError):
        await edit_application_content(uuid.uuid4(), "resume", "text", session)


# ---------------------------------------------------------------------------
# edit_application_content — gate: submit never called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_resume_does_not_call_submit(session: Session):
    app = _make_app(session)
    with _patch_llm(_EDIT_CV_RESPONSE), patch(
        "backend.services.submission_service.submit"
    ) as mock_submit:
        await edit_application_content(app.id, "resume", "Jane Smith\n\nEngineer at Acme", session)
    mock_submit.assert_not_called()


@pytest.mark.asyncio
async def test_edit_cover_letter_does_not_call_submit(session: Session):
    app = _make_app(session)
    with _patch_llm(_EDIT_CL_RESPONSE), patch(
        "backend.services.submission_service.submit"
    ) as mock_submit:
        await edit_application_content(app.id, "cover_letter", "Dear Hiring Manager...", session)
    mock_submit.assert_not_called()


# ---------------------------------------------------------------------------
# edit_application_content — happy path: resume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_resume_updates_text_and_yaml(session: Session):
    app = _make_app(session)
    with _patch_llm(_EDIT_CV_RESPONSE):
        updated = await edit_application_content(
            app.id, "resume", "Jane Smith\n\nEngineer at Acme.", session
        )
    assert updated.tailored_resume_text
    assert updated.resume_data_yaml
    doc = yaml.safe_load(updated.resume_data_yaml)
    assert doc["cv"]["name"] == "Jane Smith"


@pytest.mark.asyncio
async def test_edit_resume_updates_diff_json(session: Session):
    app = _make_app(session)
    with _patch_llm(_EDIT_CV_RESPONSE):
        updated = await edit_application_content(app.id, "resume", "New text.", session)
    assert updated.resume_diff_json
    json.loads(updated.resume_diff_json)  # must be valid JSON


@pytest.mark.asyncio
async def test_edit_resume_status_remains_pending(session: Session):
    app = _make_app(session)
    with _patch_llm(_EDIT_CV_RESPONSE):
        updated = await edit_application_content(app.id, "resume", "New text.", session)
    assert updated.status == ApplicationStatus.pending


# ---------------------------------------------------------------------------
# edit_application_content — happy path: cover_letter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_cover_letter_updates_text(session: Session):
    app = _make_app(session)
    with _patch_llm(_EDIT_CL_RESPONSE):
        updated = await edit_application_content(
            app.id, "cover_letter", "New cover letter text.", session
        )
    assert updated.cover_letter_text == "\n\n".join(_REVISED_PARAGRAPHS)


@pytest.mark.asyncio
async def test_edit_cover_letter_updates_yaml(session: Session):
    app = _make_app(session)
    with _patch_llm(_EDIT_CL_RESPONSE):
        updated = await edit_application_content(
            app.id, "cover_letter", "New cover letter text.", session
        )
    assert updated.cover_letter_data_yaml
    doc = yaml.safe_load(updated.cover_letter_data_yaml)
    assert "cv" in doc


# ---------------------------------------------------------------------------
# HTTP route-level tests: 409 for non-pending (revise and edit)
# ---------------------------------------------------------------------------


def test_revise_route_returns_409_for_submitted_app(client: TestClient, session: Session):
    app = _make_app(session, status=ApplicationStatus.submitted)
    response = client.post(
        f"/applications/{app.id}/revise",
        json={"target": "resume", "instructions": "Make it shorter."},
    )
    assert response.status_code == 409


def test_revise_route_returns_404_for_missing_app(client: TestClient):
    response = client.post(
        f"/applications/{uuid.uuid4()}/revise",
        json={"target": "resume", "instructions": "Make it shorter."},
    )
    assert response.status_code == 404


def test_edit_content_route_returns_409_for_submitted_app(client: TestClient, session: Session):
    app = _make_app(session, status=ApplicationStatus.submitted)
    response = client.put(
        f"/applications/{app.id}/content",
        json={"target": "resume", "text": "Some resume text."},
    )
    assert response.status_code == 409


def test_edit_content_route_returns_404_for_missing_app(client: TestClient):
    response = client.put(
        f"/applications/{uuid.uuid4()}/content",
        json={"target": "resume", "text": "Some resume text."},
    )
    assert response.status_code == 404


def test_revise_route_returns_409_for_rejected_app(client: TestClient, session: Session):
    app = _make_app(session, status=ApplicationStatus.rejected)
    response = client.post(
        f"/applications/{app.id}/revise",
        json={"target": "cover_letter", "instructions": "Be friendlier."},
    )
    assert response.status_code == 409


def test_edit_content_route_returns_409_for_rejected_app(client: TestClient, session: Session):
    app = _make_app(session, status=ApplicationStatus.rejected)
    response = client.put(
        f"/applications/{app.id}/content",
        json={"target": "cover_letter", "text": "New cover letter."},
    )
    assert response.status_code == 409
