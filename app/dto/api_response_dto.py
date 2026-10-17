"""The single response envelope used by every endpoint, success or error.

The frontend handles every call the same way:
    if body.status == "success": use body.data
    else: show body.message (and log body.technical_message / body.error_code)

`data` is generic: it holds the endpoint-specific DTO (AskResponseDTO,
HealthResponseDTO, ...) or, for validation errors, the list of field errors.
"""
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

DataType = TypeVar("DataType")


class ApiResponseDTO(BaseModel, Generic[DataType]):
    status: str = Field(description='"success" or "error"')
    status_code: int = Field(description="HTTP status code, repeated for convenience")
    message: str = Field(description="Short, user-facing message")
    technical_message: Optional[str] = Field(
        default=None,
        description="Developer-facing detail. Hidden in production.",
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Stable machine-readable error code, only set on errors",
    )
    data: Optional[DataType] = Field(default=None, description="Endpoint-specific payload")
    request_id: str = Field(description="Correlation ID, also sent as the X-Request-ID header")
    timestamp: str = Field(description="UTC time the response was created, ISO 8601")


class FieldErrorDTO(BaseModel):
    """One problem found while validating a request body or query parameter."""

    field: str
    issue: str
