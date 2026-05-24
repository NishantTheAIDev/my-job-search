"""Draft a cover letter from a tailored resume and parsed JD."""
import json
import logging

from backend.llm import client as llm
from backend.llm.prompts import drafter as drafter_prompts

logger = logging.getLogger(__name__)


async def draft_cover_letter(
    tailored_resume_text: str,
    parsed_jd: dict,
    role_title: str,
    company: str | None,
) -> tuple[str, str]:
    """Return (cover_letter_text, review_notes)."""
    parsed_jd_json = json.dumps(parsed_jd, indent=2)
    user = drafter_prompts.build_user_prompt(
        tailored_resume_text, parsed_jd_json, role_title, company
    )
    raw = await llm.call_claude(
        system=drafter_prompts.SYSTEM,
        user=user,
        max_tokens=2048,
    )
    try:
        data = json.loads(raw)
        return str(data["cover_letter"]), str(data.get("review_notes", ""))
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("drafter: failed to parse LLM response: %s", exc)
        return "", "Cover letter generation failed"
