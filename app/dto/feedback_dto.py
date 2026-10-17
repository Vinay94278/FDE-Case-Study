"""DTOs for POST /api/v1/feedback."""
from typing import Optional

from pydantic import BaseModel, Field

from app.core.constants import MAX_QUESTION_LENGTH


class FeedbackRequestDTO(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)
    answer_status: str = Field(pattern="^(answered|partial|not_covered)$")
    helpful: bool
    comment: Optional[str] = Field(default=None, max_length=500)


class FeedbackResponseDTO(BaseModel):
    feedback_id: str
    recorded_at: str
