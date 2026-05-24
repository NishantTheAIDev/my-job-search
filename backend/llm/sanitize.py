"""Sanitize untrusted job-board text before it enters LLM prompts."""

import re

_MAX_CHARS = 12_000


def sanitize_jd_text(raw: str) -> str:
    """Strip control characters and truncate to prevent context-window abuse."""
    text = raw.replace("\x00", "")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text[:_MAX_CHARS]
