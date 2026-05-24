"""Tests for the resume scoring service (LLM mocked)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.scoring_service import score_resume

SAMPLE_RESUME = "John Doe\nSoftware Engineer\n5 years Python, FastAPI, PostgreSQL"
SAMPLE_JD = {
    "must_have": ["Python", "FastAPI"],
    "nice_to_have": ["Docker"],
    "keywords": ["Python", "FastAPI"],
}


@pytest.mark.asyncio
async def test_score_resume_returns_valid_score():
    mock_response = json.dumps(
        {"score": 85, "rationale": "Strong Python match", "gaps": ["Docker"]}
    )
    with patch("backend.llm.client.get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = AsyncMock(
            content=[AsyncMock(text=mock_response)]
        )
        mock_get_client.return_value = mock_client
        score, rationale, gaps = await score_resume(SAMPLE_RESUME, SAMPLE_JD)

    assert score == 85
    assert "Python" in rationale
    assert "Docker" in gaps


@pytest.mark.asyncio
async def test_score_resume_handles_malformed_response():
    with patch("backend.llm.client.get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = AsyncMock(
            content=[AsyncMock(text="not valid json")]
        )
        mock_get_client.return_value = mock_client
        score, rationale, gaps = await score_resume(SAMPLE_RESUME, SAMPLE_JD)

    assert score == 0
    assert gaps == []
