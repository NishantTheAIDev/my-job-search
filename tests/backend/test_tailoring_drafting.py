"""Tests for tailoring_service.tailor_resume and drafting_service.draft_cover_letter.

call_claude is mocked so no real LLM calls occur.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.services import drafting_service, tailoring_service

SAMPLE_RESUME = (
    "Jane Smith\n"
    "Software Engineer\n\n"
    "EXPERIENCE\n"
    "Software Engineer at Acme (2020–2023)\n"
    "- Built REST APIs\n\n"
    "EDUCATION\n"
    "BS Computer Science — MIT (2016–2020)"
)

SAMPLE_JD = {
    "title": "Senior Software Engineer",
    "must_have": ["Python", "FastAPI"],
    "nice_to_have": ["Docker"],
    "keywords": ["Python", "FastAPI", "distributed systems"],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOOD_CV = {
    "name": "Jane Smith",
    "headline": "Senior Software Engineer",
    "sections": {
        "Experience": [
            {
                "company": "Acme",
                "position": "Software Engineer",
                "start_date": "2020",
                "end_date": "2023",
                "highlights": ["Built REST APIs serving 10M requests/day"],
            }
        ],
        "Education": [
            {
                "institution": "MIT",
                "degree": "BS",
                "area": "Computer Science",
                "start_date": "2016",
                "end_date": "2020",
            }
        ],
    },
}

_GOOD_TAILOR_RESPONSE = json.dumps(
    {
        "cv": _GOOD_CV,
        "change_summary": "Emphasised API work and quantified request volume.",
        "gaps": ["Docker experience not mentioned"],
    }
)

_GOOD_DRAFT_RESPONSE = json.dumps(
    {
        "cover_letter": {
            "paragraphs": [
                "Opening: I am excited to apply for the Senior Software Engineer role.",
                "Body: At Acme I built REST APIs serving 10M requests/day.",
                "Closing: I look forward to discussing this opportunity.",
            ]
        },
        "review_notes": "Verify request-volume figure before sending.",
    }
)


def _mock_call_claude(response_text: str):
    """Return a context-manager patch that stubs call_claude with *response_text*."""
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
# tailor_resume — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tailor_resume_returns_five_tuple():
    with _mock_call_claude(_GOOD_TAILOR_RESPONSE):
        result = await tailoring_service.tailor_resume(SAMPLE_RESUME, SAMPLE_JD)
    assert len(result) == 5, "tailor_resume must return (text, summary, diff, gaps, cv_dict)"


@pytest.mark.asyncio
async def test_tailor_resume_cv_dict_populated():
    with _mock_call_claude(_GOOD_TAILOR_RESPONSE):
        _, _, _, _, cv_dict = await tailoring_service.tailor_resume(SAMPLE_RESUME, SAMPLE_JD)
    assert isinstance(cv_dict, dict)
    assert cv_dict.get("name") == "Jane Smith"
    assert "sections" in cv_dict


@pytest.mark.asyncio
async def test_tailor_resume_text_derived_from_cv():
    """tailored_text must be the cv_to_text output of the returned cv, not the raw LLM string."""
    with _mock_call_claude(_GOOD_TAILOR_RESPONSE):
        tailored_text, _, _, _, cv_dict = await tailoring_service.tailor_resume(
            SAMPLE_RESUME, SAMPLE_JD
        )
    from backend.services.rendercv_service import cv_to_text

    assert tailored_text == cv_to_text(cv_dict)


@pytest.mark.asyncio
async def test_tailor_resume_change_summary_non_empty():
    with _mock_call_claude(_GOOD_TAILOR_RESPONSE):
        _, summary, _, _, _ = await tailoring_service.tailor_resume(SAMPLE_RESUME, SAMPLE_JD)
    assert summary == "Emphasised API work and quantified request volume."


@pytest.mark.asyncio
async def test_tailor_resume_gaps_parsed():
    with _mock_call_claude(_GOOD_TAILOR_RESPONSE):
        _, _, _, gaps, _ = await tailoring_service.tailor_resume(SAMPLE_RESUME, SAMPLE_JD)
    assert isinstance(gaps, list)
    assert any("Docker" in g for g in gaps)


@pytest.mark.asyncio
async def test_tailor_resume_diff_json_valid():
    with _mock_call_claude(_GOOD_TAILOR_RESPONSE):
        _, _, diff_json, _, _ = await tailoring_service.tailor_resume(SAMPLE_RESUME, SAMPLE_JD)
    hunks = json.loads(diff_json)
    assert isinstance(hunks, list)
    # Every hunk must have type, text, and line keys
    for hunk in hunks:
        assert "type" in hunk
        assert hunk["type"] in ("unchanged", "added", "removed")
        assert "text" in hunk
        assert "line" in hunk


# ---------------------------------------------------------------------------
# tailor_resume — bad JSON fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tailor_resume_bad_json_falls_back_to_original():
    with _mock_call_claude("not valid json at all"):
        tailored_text, summary, diff_json, gaps, cv_dict = await tailoring_service.tailor_resume(
            SAMPLE_RESUME, SAMPLE_JD
        )
    # Fallback: return original text unchanged
    assert tailored_text == SAMPLE_RESUME
    assert summary == ""
    assert gaps == []
    assert cv_dict == {}


@pytest.mark.asyncio
async def test_tailor_resume_missing_cv_key_falls_back():
    bad_response = json.dumps({"change_summary": "oops", "gaps": []})  # missing "cv" key
    with _mock_call_claude(bad_response):
        tailored_text, _, _, _, cv_dict = await tailoring_service.tailor_resume(
            SAMPLE_RESUME, SAMPLE_JD
        )
    assert tailored_text == SAMPLE_RESUME
    assert cv_dict == {}


@pytest.mark.asyncio
async def test_tailor_resume_bad_json_diff_is_noop():
    """Even on fallback the diff_json must be valid JSON (a no-op diff)."""
    with _mock_call_claude("invalid"):
        _, _, diff_json, _, _ = await tailoring_service.tailor_resume(SAMPLE_RESUME, SAMPLE_JD)
    hunks = json.loads(diff_json)
    # A no-op diff between identical texts has only "unchanged" hunks
    types = {h["type"] for h in hunks}
    assert types <= {"unchanged"}


# ---------------------------------------------------------------------------
# draft_cover_letter — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_cover_letter_returns_three_tuple():
    with _mock_call_claude(_GOOD_DRAFT_RESPONSE):
        result = await drafting_service.draft_cover_letter(
            SAMPLE_RESUME, SAMPLE_JD, "Senior Software Engineer", "Acme"
        )
    assert len(result) == 3


@pytest.mark.asyncio
async def test_draft_cover_letter_text_joins_paragraphs():
    with _mock_call_claude(_GOOD_DRAFT_RESPONSE):
        cover_letter_text, _, paragraphs = await drafting_service.draft_cover_letter(
            SAMPLE_RESUME, SAMPLE_JD, "Senior Software Engineer", "Acme"
        )
    assert cover_letter_text == "\n\n".join(paragraphs)


@pytest.mark.asyncio
async def test_draft_cover_letter_paragraphs_non_empty():
    with _mock_call_claude(_GOOD_DRAFT_RESPONSE):
        _, _, paragraphs = await drafting_service.draft_cover_letter(
            SAMPLE_RESUME, SAMPLE_JD, "Senior Software Engineer", "Acme"
        )
    assert isinstance(paragraphs, list)
    assert len(paragraphs) == 3
    assert all(isinstance(p, str) and p for p in paragraphs)


@pytest.mark.asyncio
async def test_draft_cover_letter_review_notes_returned():
    with _mock_call_claude(_GOOD_DRAFT_RESPONSE):
        _, review_notes, _ = await drafting_service.draft_cover_letter(
            SAMPLE_RESUME, SAMPLE_JD, "Senior Software Engineer", "Acme"
        )
    assert "Verify request-volume" in review_notes


@pytest.mark.asyncio
async def test_draft_cover_letter_none_company_accepted():
    """company=None should not raise; the service substitutes a default."""
    with _mock_call_claude(_GOOD_DRAFT_RESPONSE):
        text, _, paragraphs = await drafting_service.draft_cover_letter(
            SAMPLE_RESUME, SAMPLE_JD, "Senior Software Engineer", None
        )
    assert text  # some content returned


# ---------------------------------------------------------------------------
# draft_cover_letter — bad JSON fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_cover_letter_bad_json_returns_empty():
    with _mock_call_claude("this is not json"):
        cover_letter_text, review_notes, paragraphs = await drafting_service.draft_cover_letter(
            SAMPLE_RESUME, SAMPLE_JD, "Role", "Company"
        )
    assert cover_letter_text == ""
    assert paragraphs == []
    assert review_notes  # should include a failure note, not be silently empty


@pytest.mark.asyncio
async def test_draft_cover_letter_missing_cover_letter_key_returns_empty():
    bad = json.dumps({"review_notes": "oops"})  # missing "cover_letter" key
    with _mock_call_claude(bad):
        cover_letter_text, _, paragraphs = await drafting_service.draft_cover_letter(
            SAMPLE_RESUME, SAMPLE_JD, "Role", "Company"
        )
    assert cover_letter_text == ""
    assert paragraphs == []


@pytest.mark.asyncio
async def test_draft_cover_letter_backward_compat_plain_string():
    """LLM returns cover_letter as a plain string (backward compat path)."""
    response = json.dumps(
        {"cover_letter": "A single string cover letter.", "review_notes": ""}
    )
    with _mock_call_claude(response):
        text, _, paragraphs = await drafting_service.draft_cover_letter(
            SAMPLE_RESUME, SAMPLE_JD, "Role", "Company"
        )
    assert text == "A single string cover letter."
    assert paragraphs == ["A single string cover letter."]
