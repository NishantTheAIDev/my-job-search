"""Score a resume against a parsed job description."""

import json
import logging

from backend.llm import client as llm
from backend.llm.prompts import scorer as scorer_prompts

logger = logging.getLogger(__name__)


async def score_resume(resume_text: str, parsed_jd: dict) -> tuple[int, str, list[str]]:
    """Return (score, rationale, gaps)."""
    parsed_jd_json = json.dumps(parsed_jd, indent=2)
    user = scorer_prompts.build_user_prompt(resume_text, parsed_jd_json)
    raw = await llm.call_claude(
        system=scorer_prompts.SYSTEM,
        user=user,
        max_tokens=512,
        cache_system=True,
    )
    try:
        data = json.loads(raw)
        return int(data["score"]), str(data["rationale"]), list(data.get("gaps", []))
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("scorer: failed to parse LLM response: %s (response len=%d)", exc, len(raw))
        return 0, "Scoring failed", []
