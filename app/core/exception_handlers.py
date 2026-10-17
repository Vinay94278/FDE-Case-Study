"""Centralized exception handling: every error leaves the API in the same envelope.

    AppException             our own errors, each with an error code and HTTP status
    RequestValidationError   bad request body or query parameters (422, with field list)
    StarletteHTTPException   unknown route (404), wrong method (405), etc.
    Exception                anything unexpected (500); details are logged, never leaked
                             unless EXPOSE_TECHNICAL_MESSAGES=true
"""
import logging
from typing import List

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.constants import REQUEST_ID_HEADER
from app.core.exceptions import AppException
from app.core.request_context import NO_REQUEST_ID, get_current_request_id
from app.core.response_builder import build_error_response
from app.dto.api_response_dto import FieldErrorDTO

logger = logging.getLogger(__name__)

HTTP_ERROR_MESSAGES = {
    404: ("NOT_FOUND", "The requested endpoint does not exist."),
    405: ("METHOD_NOT_ALLOWED", "This HTTP method is not allowed for this endpoint."),
}


def _read_request_id(request: Request) -> str:
    """The middleware stores the ID on request.state; fall back to the context variable."""
    stored_request_id = getattr(request.state, "request_id", None)
    if stored_request_id:
        return stored_request_id
    return get_current_request_id()


def _should_expose_technical_messages(request: Request) -> bool:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        return False
    return settings.expose_technical_messages


def _build_json_response(request: Request, status_code: int, message: str, error_code: str,
                         technical_message, data=None) -> JSONResponse:
    request_id = _read_request_id(request)
    visible_technical_message = None
    if _should_expose_technical_messages(request):
        visible_technical_message = technical_message

    error_response = build_error_response(
        status_code=status_code,
        message=message,
        error_code=error_code,
        request_id=request_id,
        technical_message=visible_technical_message,
        data=data,
    )
    response_headers = {}
    if request_id != NO_REQUEST_ID:
        response_headers[REQUEST_ID_HEADER] = request_id
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(mode="json"),
        headers=response_headers,
    )


async def handle_app_exception(request: Request, error: AppException) -> JSONResponse:
    if error.http_status >= 500:
        logger.error("%s: %s (%s)", error.error_code, error.message, error.technical_message)
    else:
        logger.warning("%s: %s (%s)", error.error_code, error.message, error.technical_message)
    return _build_json_response(request, error.http_status, error.message, error.error_code, error.technical_message)


async def handle_request_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    field_errors: List[dict] = []
    technical_parts: List[str] = []
    for validation_issue in error.errors():
        location_parts = []
        for location_part in validation_issue.get("loc", []):
            if location_part == "body":
                continue
            location_parts.append(str(location_part))
        field_path = ".".join(location_parts)
        if field_path == "":
            field_path = "body"
        issue_text = str(validation_issue.get("msg", "invalid value"))
        field_errors.append(FieldErrorDTO(field=field_path, issue=issue_text).model_dump())
        technical_parts.append(field_path + ": " + issue_text)

    logger.warning("Request validation failed: %s", "; ".join(technical_parts))
    return _build_json_response(
        request,
        422,
        "Some fields in the request are not valid.",
        "VALIDATION_FAILED",
        "; ".join(technical_parts),
        data=field_errors,
    )


async def handle_http_exception(request: Request, error: StarletteHTTPException) -> JSONResponse:
    error_code = "HTTP_ERROR"
    message = str(error.detail)
    if error.status_code in HTTP_ERROR_MESSAGES:
        error_code, message = HTTP_ERROR_MESSAGES[error.status_code]
    logger.warning("HTTP %d on %s %s", error.status_code, request.method, request.url.path)
    return _build_json_response(request, error.status_code, message, error_code, str(error.detail))


async def handle_unexpected_exception(request: Request, error: Exception) -> JSONResponse:
    logger.exception("Unexpected error on %s %s", request.method, request.url.path)
    return _build_json_response(
        request,
        500,
        "An unexpected error occurred. Please try again.",
        "INTERNAL_ERROR",
        type(error).__name__ + ": " + str(error),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, handle_app_exception)
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_exception)
