"""Centralized Anthropic SDK client with retry and prompt caching."""

import logging
import time

import anthropic
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import settings

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        # The key is loaded from .env via pydantic-settings (backend/config.py);
        # it is NOT exported to os.environ, so pass it explicitly.
        _client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value()
        )
    return _client


def _log_retry(state: RetryCallState) -> None:
    exc = state.outcome.exception() if state.outcome else None
    logger.warning(
        "llm: retrying call (attempt %d) after %s: %s",
        state.attempt_number,
        type(exc).__name__ if exc else "unknown",
        exc,
    )


@retry(
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIStatusError)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
    before_sleep=_log_retry,
)
async def call_claude(
    system: str,
    user: str,
    max_tokens: int,
    cache_system: bool = False,
) -> str:
    """Call Claude and return the text content of the first response block.

    Args:
        system: System prompt (never interpolated with external content).
        user: User turn content (external content wrapped in XML tags here).
        max_tokens: Maximum tokens for the response.
        cache_system: If True, apply prompt caching to the system prompt.
    """
    client = get_client()

    system_content: list[dict] | str
    if cache_system:
        system_content = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        system_content = system

    t0 = time.perf_counter()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system_content,
        messages=[{"role": "user", "content": user}],
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    usage = response.usage
    logger.info(
        "llm: model=%s in=%d out=%d cache_read=%d cache_write=%d elapsed=%.0fms",
        MODEL,
        usage.input_tokens,
        usage.output_tokens,
        getattr(usage, "cache_read_input_tokens", 0) or 0,
        getattr(usage, "cache_creation_input_tokens", 0) or 0,
        elapsed_ms,
    )

    return response.content[0].text
