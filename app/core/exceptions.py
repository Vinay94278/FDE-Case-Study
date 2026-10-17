"""Application exception hierarchy.

Every exception the application raises on purpose is an AppException. Each one
carries:
    error_code         stable machine-readable code for the frontend
    message            safe, user-facing text
    technical_message  details for developers (hidden when EXPOSE_TECHNICAL_MESSAGES=false)
    http_status        status code returned by the centralized exception handler
"""
from typing import Optional


class AppException(Exception):
    """Base class for all expected application errors."""

    default_error_code = "APPLICATION_ERROR"
    default_message = "Something went wrong while processing the request."
    default_http_status = 500

    def __init__(
        self,
        message: Optional[str] = None,
        technical_message: Optional[str] = None,
        error_code: Optional[str] = None,
        http_status: Optional[int] = None,
    ):
        if message is None:
            message = self.default_message
        if error_code is None:
            error_code = self.default_error_code
        if http_status is None:
            http_status = self.default_http_status

        super().__init__(message)
        self.message = message
        self.technical_message = technical_message
        self.error_code = error_code
        self.http_status = http_status


# ---------------------------------------------------------------------- client errors (4xx)

class RequestValidationException(AppException):
    default_error_code = "INVALID_REQUEST"
    default_message = "The request is not valid."
    default_http_status = 400


class ResourceNotFoundException(AppException):
    default_error_code = "NOT_FOUND"
    default_message = "The requested resource was not found."
    default_http_status = 404


# ---------------------------------------------------------------------- server errors (5xx)

class ConfigurationException(AppException):
    default_error_code = "CONFIGURATION_ERROR"
    default_message = "The service is not configured correctly."
    default_http_status = 500


class DocumentLoadException(AppException):
    default_error_code = "DOCUMENT_LOAD_ERROR"
    default_message = "The documentation could not be loaded."
    default_http_status = 500


class RetrievalException(AppException):
    default_error_code = "RETRIEVAL_ERROR"
    default_message = "The documentation search failed."
    default_http_status = 500


class StorageException(AppException):
    default_error_code = "STORAGE_ERROR"
    default_message = "The data could not be saved."
    default_http_status = 500


class ServiceUnavailableException(AppException):
    default_error_code = "SERVICE_UNAVAILABLE"
    default_message = "The service is not ready yet. Please try again shortly."
    default_http_status = 503


# ---------------------------------------------------------------------- LLM provider errors

class LlmException(AppException):
    """Base class for LLM provider failures. The answering service turns these
    into a safe refusal, so they rarely reach the client directly."""

    default_error_code = "LLM_ERROR"
    default_message = "The language model could not produce a response."
    default_http_status = 502


class LlmTimeoutException(LlmException):
    default_error_code = "LLM_TIMEOUT"
    default_message = "The language model took too long to respond."
    default_http_status = 504


class LlmRateLimitException(LlmException):
    default_error_code = "LLM_RATE_LIMITED"
    default_message = "The language model is busy. Please try again shortly."
    default_http_status = 503


class LlmAuthenticationException(LlmException):
    default_error_code = "LLM_AUTHENTICATION_FAILED"
    default_message = "The language model rejected the service credentials."
    default_http_status = 502


class LlmResponseFormatException(LlmException):
    default_error_code = "LLM_BAD_RESPONSE"
    default_message = "The language model returned a response in an unexpected format."
    default_http_status = 502
