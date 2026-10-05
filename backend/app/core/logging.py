"""Logging and request correlation.

One JSON object per line in production so a log shipper can index it; a plain
line in development so it is readable in a terminal. Every record carries the
current request id (from the middleware in `app.core.request_id`) when there
is one. Standard library only.

Patient details must never be logged at INFO: log ids and timings, not text.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings

# Set by the request-id middleware for the duration of a request (and the
# background tasks that run after its response).
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_STANDARD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime"}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """`{"time", "level", "logger", "message", "request_id", ...extras}`."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        # Anything passed via `logger.info(..., extra={...})`
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key != "request_id":
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class DevFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__(
            "%(asctime)s %(levelname)-7s %(name)s [%(request_id)s] %(message)s"
        )

    def format(self, record: logging.LogRecord) -> str:
        if getattr(record, "request_id", None) is None:
            record.request_id = "-"
        return super().format(record)


def configure_logging(settings: Settings) -> None:
    """Idempotent: replaces the root handlers so uvicorn's defaults don't double-log."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        DevFormatter() if settings.FASTAPI_ENV == "development" else JsonFormatter()
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.LOG_LEVEL)
    # Uvicorn's own access log duplicates our request log line.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv = logging.getLogger(name)
        uv.handlers[:] = []
        uv.propagate = True
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
