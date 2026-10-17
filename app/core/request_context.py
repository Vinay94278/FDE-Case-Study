"""Per-request context.

A ContextVar keeps the current request ID available to any code running for that
request (services, DAOs, log formatting) without passing it through every call.
"""
from contextvars import ContextVar

NO_REQUEST_ID = "-"

request_id_context: ContextVar[str] = ContextVar("request_id", default=NO_REQUEST_ID)


def get_current_request_id() -> str:
    """Return the request ID of the request being handled, or "-" outside a request."""
    return request_id_context.get()
