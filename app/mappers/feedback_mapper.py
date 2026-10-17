"""Feedback DTOs <-> FeedbackRecord model."""
import uuid
from typing import Optional

from app.dto.feedback_dto import FeedbackRequestDTO, FeedbackResponseDTO
from app.models.log_models import FeedbackRecord
from app.utils.redaction import redact_personal_data
from app.utils.time_utils import utc_now_iso

FEEDBACK_RECORD_TYPE = "feedback"


class FeedbackMapper:
    @staticmethod
    def to_feedback_record(request_dto: FeedbackRequestDTO, request_id: str) -> FeedbackRecord:
        redacted_comment: Optional[str] = None
        if request_dto.comment is not None:
            redacted_comment = redact_personal_data(request_dto.comment)

        return FeedbackRecord(
            record_type=FEEDBACK_RECORD_TYPE,
            feedback_id=uuid.uuid4().hex,
            timestamp=utc_now_iso(),
            request_id=request_id,
            question=redact_personal_data(request_dto.question),
            answer_status=request_dto.answer_status,
            helpful=request_dto.helpful,
            comment=redacted_comment,
        )

    @staticmethod
    def to_feedback_response_dto(record: FeedbackRecord) -> FeedbackResponseDTO:
        return FeedbackResponseDTO(feedback_id=record.feedback_id, recorded_at=record.timestamp)
