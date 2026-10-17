"""Builds the ApiResponseDTO envelope for both success and error responses."""
from typing import Any, Optional

from app.core.constants import RESPONSE_STATUS_ERROR, RESPONSE_STATUS_SUCCESS
from app.core.request_context import get_current_request_id
from app.dto.api_response_dto import ApiResponseDTO
from app.utils.time_utils import utc_now_iso


def build_success_response(data: Any, message: str, status_code: int = 200) -> ApiResponseDTO:
    return ApiResponseDTO(
        status=RESPONSE_STATUS_SUCCESS,
        status_code=status_code,
        message=message,
        technical_message=None,
        error_code=None,
        data=data,
        request_id=get_current_request_id(),
        timestamp=utc_now_iso(),
    )


def build_error_response(status_code: int, message: str, error_code: str, request_id: str,
                         technical_message: Optional[str] = None, data: Any = None) -> ApiResponseDTO:
    return ApiResponseDTO(
        status=RESPONSE_STATUS_ERROR,
        status_code=status_code,
        message=message,
        technical_message=technical_message,
        error_code=error_code,
        data=data,
        request_id=request_id,
        timestamp=utc_now_iso(),
    )
