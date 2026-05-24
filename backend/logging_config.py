"""Centralized logging configuration for the job-search backend.

Call configure_logging() once at startup. All modules then use the standard
    logger = logging.getLogger(__name__)
pattern and inherit this configuration automatically.

Request ID propagation uses a ContextVar so every log line emitted during a
request (including in background-called services) carries the same req_id.
Background tasks show "-" as the request ID since they run outside a request.
"""
import logging
import logging.config
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class _ContextFilter(logging.Filter):
    """Injects the current request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()  # type: ignore[attr-defined]
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with a consistent format and sensible library levels.

    Safe to call multiple times (idempotent via disable_existing_loggers=False).
    """
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "context": {"()": _ContextFilter},
            },
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s | %(levelname)-8s | %(request_id)s"
                        " | %(name)s | %(message)s"
                    ),
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["context"],
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": level.upper(),
                "handlers": ["console"],
            },
            "loggers": {
                # Silence chatty third-party libraries
                "httpx": {"level": "WARNING", "propagate": True},
                "httpcore": {"level": "WARNING", "propagate": True},
                "anthropic": {"level": "WARNING", "propagate": True},
                "uvicorn.access": {"level": "WARNING", "propagate": True},
                "multipart": {"level": "WARNING", "propagate": True},
            },
        }
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status code, and duration.

    Also sets a short request ID in the ContextVar so all log lines within
    the request lifecycle carry the same ID. The ID is echoed back in the
    X-Request-ID response header for correlation with client-side logs.
    """

    _logger = logging.getLogger("backend.access")

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = uuid.uuid4().hex[:8]
        token = request_id_var.set(req_id)
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self._logger.info(
                "%s %s → %d (%.0f ms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self._logger.exception(
                "%s %s → ERROR (%.0f ms)", request.method, request.url.path, elapsed_ms
            )
            raise
        finally:
            request_id_var.reset(token)
