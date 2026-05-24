"""Tailor a resume to a job description and compute a diff."""
import difflib
import json
import logging

from backend.llm import client as llm
from backend.llm.prompts import tailor as tailor_prompts

logger = logging.getLogger(__name__)


def _compute_diff_json(original: str, tailored: str) -> str:
    """Compute a unified diff between original and tailored resume as JSON."""
    orig_lines = original.splitlines(keepends=True)
    tail_lines = tailored.splitlines(keepends=True)
    hunks: list[dict] = []
    line_num = 0
    matcher = difflib.SequenceMatcher(None, orig_lines, tail_lines)
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            for line in orig_lines[i1:i2]:
                hunks.append({"type": "unchanged", "text": line.rstrip("\n"), "line": line_num})
                line_num += 1
        elif opcode in ("replace", "delete"):
            for line in orig_lines[i1:i2]:
                hunks.append({"type": "removed", "text": line.rstrip("\n"), "line": line_num})
                line_num += 1
        if opcode in ("replace", "insert"):
            for line in tail_lines[j1:j2]:
                hunks.append({"type": "added", "text": line.rstrip("\n"), "line": line_num})
                line_num += 1
    return json.dumps(hunks)


async def tailor_resume(
    resume_text: str, parsed_jd: dict
) -> tuple[str, str, str, list[str]]:
    """Return (tailored_resume_text, change_summary, diff_json, gaps)."""
    parsed_jd_json = json.dumps(parsed_jd, indent=2)
    user = tailor_prompts.build_user_prompt(resume_text, parsed_jd_json)
    raw = await llm.call_claude(
        system=tailor_prompts.SYSTEM,
        user=user,
        max_tokens=4096,
        cache_system=True,
    )
    try:
        data = json.loads(raw)
        tailored = str(data["tailored_resume"])
        summary = str(data.get("change_summary", ""))
        gaps = list(data.get("gaps", []))
        diff_json = _compute_diff_json(resume_text, tailored)
        return tailored, summary, diff_json, gaps
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("tailor: failed to parse LLM response: %s", exc)
        diff_json = _compute_diff_json(resume_text, resume_text)
        return resume_text, "", diff_json, []
