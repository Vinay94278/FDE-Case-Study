"""POST /api/v1/ask: answer a question from the documentation."""
import logging

from fastapi import APIRouter, Depends

from app.api.dependencies import get_question_answering_service
from app.core.constants import API_VERSION_PREFIX
from app.core.response_builder import build_success_response
from app.dto.api_response_dto import ApiResponseDTO
from app.dto.ask_dto import AskRequestDTO, AskResponseDTO
from app.mappers.ask_mapper import AskMapper
from app.services.question_answering_service import QuestionAnsweringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix=API_VERSION_PREFIX, tags=["Questions"])


@router.post(
    "/ask",
    response_model=ApiResponseDTO[AskResponseDTO],
    summary="Answer a question using only the documentation",
)
async def ask_question(
    request_dto: AskRequestDTO,
    question_answering_service: QuestionAnsweringService = Depends(get_question_answering_service),
) -> ApiResponseDTO[AskResponseDTO]:
    logger.info(
        "Ask request received: %d characters, %d history turns",
        len(request_dto.question),
        len(request_dto.conversation_history),
    )
    response_dto = await question_answering_service.answer_question(request_dto)
    envelope_message = AskMapper.build_envelope_message(response_dto)
    return build_success_response(data=response_dto, message=envelope_message)
