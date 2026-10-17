"""Central logging setup.

- Every log line carries the request ID, so all lines for one question can be found together.
- LOG_FORMAT=text is easy to read locally; LOG_FORMAT=json suits log platforms
  (Azure Monitor, Datadog, Railway log search).
- Question text is never logged at INFO level. Services log decisions and timings,
  and the redacted question goes to the query log store instead.
"""
import json
import logging
import sys
from datetime import datetime, timezone

from app.core.request_context import get_current_request_id

TEXT_LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s - %(message)s"


class RequestIdFilter(logging.Filter):
    """Adds the current request ID to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_current_request_id()
        return True


class JsonLogFormatter(logging.Formatter):
    """Formats each log record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def configure_logging(log_level: str, log_format: str) -> None:
    """Configure the root logger once at startup. Safe to call more than once."""
    root_logger = logging.getLogger()
    for existing_handler in list(root_logger.handlers):
        root_logger.removeHandler(existing_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.addFilter(RequestIdFilter())
    if log_format.strip().lower() == "json":
        console_handler.setFormatter(JsonLogFormatter())
    else:
        console_handler.setFormatter(logging.Formatter(TEXT_LOG_FORMAT))

    root_logger.addHandler(console_handler)
    root_logger.setLevel(log_level.strip().upper())

    # Uvicorn's own access log is replaced by our request middleware log line.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # Third-party HTTP clients are noisy at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
