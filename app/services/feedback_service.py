"""Records thumbs up / thumbs down on answers."""
import logging

from app.core.request_context import get_current_request_id
from app.dao.query_log_dao import QueryLogDAO
from app.dto.feedback_dto import FeedbackRequestDTO, FeedbackResponseDTO
from app.mappers.feedback_mapper import FeedbackMapper

logger = logging.getLogger(__name__)


class FeedbackService:
    def __init__(self, query_log_dao: QueryLogDAO):
        self.query_log_dao = query_log_dao

    async def record_feedback(self, request_dto: FeedbackRequestDTO) -> FeedbackResponseDTO:
        feedback_record = FeedbackMapper.to_feedback_record(request_dto, get_current_request_id())
        # Unlike the query log, a failed save is reported: saving is this endpoint's whole job.
        await self.query_log_dao.save_feedback_record(feedback_record)
        logger.info("Feedback recorded: helpful=%s status=%s", request_dto.helpful, request_dto.answer_status)
        return FeedbackMapper.to_feedback_response_dto(feedback_record)
