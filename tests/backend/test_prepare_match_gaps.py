"""Tests that prepare_application correctly persists match_gaps from the scorer.

These extend the existing prepare-pipeline test suite to cover the gap-persistence
invariant (Application.match_gaps stores JSON-encoded list[str]) and verify that
ApplicationResponse.match_gaps decodes back to that list.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

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
from backend.services.application_service import prepare_application

# ---------------------------------------------------------------------------
# Seed helpers (mirror test_prepare_application.py)
# ---------------------------------------------------------------------------


def _seed(session: Session, user_id, *, source_job_id: str = "gap-p1") -> JobPosting:
    resume = Resume(
        user_id=user_id,
        filename="r.txt",
        file_path="/tmp/r.txt",
        text_content="original resume",
        is_active=True,
    )
    posting = JobPosting(
        user_id=user_id,
        source="test",
        source_job_id=source_job_id,
        title="Software Engineer",
        company="Acme",
        url="https://example.com/job/1",
        description="A test job with several gaps",
        remote_status=RemoteStatus.remote,
    )
    session.add(resume)
    session.add(posting)
    session.commit()
    session.refresh(posting)
    return posting


def _patch_pipeline_with_gaps(monkeypatch, gaps: list[str]) -> None:
    """Patch the full pipeline; scorer returns the supplied gaps list."""

    async def fake_parse_jd(description):
        return {"title": "Software Engineer", "must_have": ["Python"]}

    async def fake_score(resume_text, parsed):
        return (72, "decent match with notable gaps", gaps)

    async def fake_tailor(resume_text, parsed):
        return (
            "tailored resume",
            "added some keywords",
            '[{"type":"added","text":"Python","line":1}]',
            [],
            {},
        )

    async def fake_draft(text, parsed, title, company):
        return (
            "Dear Hiring Manager,\n\nI am excited…",
            "",
            ["Dear Hiring Manager,\n\nI am excited…"],
        )

    monkeypatch.setattr(application_service, "_parse_jd", fake_parse_jd)
    monkeypatch.setattr(scoring_service, "score_resume", fake_score)
    monkeypatch.setattr(tailoring_service, "tailor_resume", fake_tailor)
    monkeypatch.setattr(drafting_service, "draft_cover_letter", fake_draft)


# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_persists_gaps_as_json(session: Session, user: User, monkeypatch):
    """Application.match_gaps must be a JSON-encoded list of the scorer's gaps."""
    gaps = ["Docker", "Kubernetes", "AWS"]
    posting = _seed(session, user.id)
    _patch_pipeline_with_gaps(monkeypatch, gaps)

    app = await prepare_application(posting.id, user.id, session)

    assert app.status == ApplicationStatus.pending
    decoded = json.loads(app.match_gaps)
    assert isinstance(decoded, list)
    assert decoded == gaps


@pytest.mark.asyncio
async def test_prepare_persists_empty_gaps_list(session: Session, user: User, monkeypatch):
    """When the scorer returns no gaps the persisted value must be '[]'."""
    posting = _seed(session, user.id, source_job_id="gap-p2")
    _patch_pipeline_with_gaps(monkeypatch, [])

    app = await prepare_application(posting.id, user.id, session)

    decoded = json.loads(app.match_gaps)
    assert decoded == []


# ---------------------------------------------------------------------------
# API-layer tests — ApplicationResponse.match_gaps decodes correctly
# ---------------------------------------------------------------------------


def _seed_http(client: TestClient, session: Session, user_id) -> JobPosting:
    """Upload a resume via the HTTP API then seed a job posting directly."""
    import io

    content = b"John Doe\nSoftware Engineer\n5 years Python"
    client.post(
        "/resume/upload",
        files={"file": ("resume.txt", io.BytesIO(content), "text/plain")},
    )
    posting = JobPosting(
        user_id=user_id,
        source="test",
        source_job_id="http-gap-p1",
        title="DevOps Engineer",
        company="CloudCo",
        url="https://example.com/job/http-gap",
        description="Needs Docker, K8s, Terraform",
        remote_status=RemoteStatus.remote,
    )
    session.add(posting)
    session.commit()
    session.refresh(posting)
    return posting


def test_application_response_match_gaps_is_list(
    client: TestClient, session: Session, user: User, monkeypatch
):
    """GET /applications/{id} returns match_gaps as a JSON array, not a string."""
    gaps = ["Terraform", "Ansible"]
    posting = _seed_http(client, session, user.id)

    # Directly create a pending Application with known gaps
    resume = session.exec(select(Resume).where(Resume.is_active == True)).first()  # noqa: E712
    app = Application(
        user_id=user.id,
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=ApplicationStatus.pending,
        tailored_resume_text="tailored",
        cover_letter_text="Dear hiring manager",
        match_score=65,
        match_rationale="partial match",
        match_gaps=json.dumps(gaps),
    )
    session.add(app)
    session.commit()
    session.refresh(app)

    response = client.get(f"/applications/{app.id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["match_gaps"], list)
    assert data["match_gaps"] == gaps


def test_application_response_match_gaps_empty_list(
    client: TestClient, session: Session, user: User
):
    """match_gaps == '[]' in DB must deserialise to [] in the API response."""
    posting = _seed_http(client, session, user.id)
    resume = session.exec(select(Resume).where(Resume.is_active == True)).first()  # noqa: E712
    app = Application(
        user_id=user.id,
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=ApplicationStatus.pending,
        tailored_resume_text="tailored",
        cover_letter_text="Dear",
        match_score=90,
        match_rationale="strong match",
        match_gaps="[]",
    )
    session.add(app)
    session.commit()
    session.refresh(app)

    response = client.get(f"/applications/{app.id}")
    assert response.status_code == 200
    assert response.json()["match_gaps"] == []


def test_application_response_match_gaps_malformed_json_defaults_to_empty(
    client: TestClient, session: Session, user: User
):
    """If DB contains malformed JSON in match_gaps, the API must return []."""
    posting = _seed_http(client, session, user.id)
    resume = session.exec(select(Resume).where(Resume.is_active == True)).first()  # noqa: E712
    app = Application(
        user_id=user.id,
        job_posting_id=posting.id,
        resume_id=resume.id,
        status=ApplicationStatus.pending,
        tailored_resume_text="tailored",
        cover_letter_text="Dear",
        match_score=50,
        match_rationale="some match",
        match_gaps="NOT_VALID_JSON",
    )
    session.add(app)
    session.commit()
    session.refresh(app)

    response = client.get(f"/applications/{app.id}")
    assert response.status_code == 200
    assert response.json()["match_gaps"] == []
