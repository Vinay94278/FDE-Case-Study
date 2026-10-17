"""POST /api/v1/feedback: record whether an answer was helpful."""
from fastapi import APIRouter, Depends

from app.api.dependencies import get_feedback_service
from app.core.constants import API_VERSION_PREFIX
from app.core.response_builder import build_success_response
from app.dto.api_response_dto import ApiResponseDTO
from app.dto.feedback_dto import FeedbackRequestDTO, FeedbackResponseDTO
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix=API_VERSION_PREFIX, tags=["Feedback"])


@router.post(
    "/feedback",
    response_model=ApiResponseDTO[FeedbackResponseDTO],
    status_code=201,
    summary="Record thumbs up or down for an answer",
)
async def record_feedback(
    request_dto: FeedbackRequestDTO,
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> ApiResponseDTO[FeedbackResponseDTO]:
    response_dto = await feedback_service.record_feedback(request_dto)
    return build_success_response(data=response_dto, message="Feedback recorded.", status_code=201)
