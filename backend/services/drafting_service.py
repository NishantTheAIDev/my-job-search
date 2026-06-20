"""Draft a cover letter from a tailored resume and parsed JD."""

import json
import logging

from backend.llm import client as llm
from backend.llm.parsing import extract_json
from backend.llm.prompts import drafter as drafter_prompts

logger = logging.getLogger(__name__)


async def draft_cover_letter(
    tailored_resume_text: str,
    parsed_jd: dict,
    role_title: str,
    company: str | None,
) -> tuple[str, str, list[str]]:
    """Return (cover_letter_text, review_notes, paragraphs).

    ``cover_letter_text`` is paragraphs joined by double newlines (for DOCX/
    plain-text export).  ``paragraphs`` is the raw list used to build the
    rendercv cover-letter YAML.
    """
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
        data = extract_json(raw)
        cl_block = data["cover_letter"]
        if isinstance(cl_block, dict):
            paragraphs = [str(p) for p in cl_block.get("paragraphs", [])]
        else:
            # Backward compat: LLM returned a plain string
            paragraphs = [str(cl_block)]
        cover_letter_text = "\n\n".join(paragraphs)
        review_notes = str(data.get("review_notes", ""))
        return cover_letter_text, review_notes, paragraphs
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("drafter: failed to parse LLM response: %s", exc)
        return "", "Cover letter generation failed", []
