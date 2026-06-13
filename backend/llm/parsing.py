"""Tolerant JSON extraction for LLM responses.

Models are instructed to return raw JSON, but intermittently wrap it in a
markdown code fence (```json … ```) or add a leading/trailing sentence. A plain
``json.loads`` then fails at char 0. ``extract_json`` strips fences and, as a
fallback, parses the outermost ``{…}`` object, so a stray fence or preamble no
longer drops the whole pipeline to its failure path.
"""

import json
import re

_FENCE_OPEN = re.compile(r"^\s*```[a-zA-Z0-9]*\s*\n?")
_FENCE_CLOSE = re.compile(r"\n?\s*```\s*$")


def extract_json(raw: str) -> dict:
    """Parse a JSON object from an LLM response, tolerating fences/prose.

    Raises ``json.JSONDecodeError`` if no JSON object can be recovered, so
    existing callers can keep handling that exception as a parse failure.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        text = _FENCE_CLOSE.sub("", _FENCE_OPEN.sub("", text)).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fall back to the outermost object if the model added surrounding prose.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise
