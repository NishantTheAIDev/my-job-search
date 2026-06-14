"""Shared HTTP retry policy for insights clients.

Retry only on transient failures — transport errors (timeouts, connection resets)
and 5xx responses. A 4xx (e.g. GDELT's 429 "1 request / 5s" rate limit) is NOT
retried: backing off a second or two would just hit the limit again, so we fail
fast and let the caller degrade gracefully.
"""

import httpx
from tenacity import retry_if_exception


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


retry_transient = retry_if_exception(_is_transient)


def safe_err(exc: Exception) -> str:
    """Describe an exception for logs without leaking the request URL (carries app_key)."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__
