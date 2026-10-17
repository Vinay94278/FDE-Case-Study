"""DTOs for GET /api/v1/insights/documentation-gaps."""
from typing import List

from pydantic import BaseModel, Field


class DocumentationGapDTO(BaseModel):
    question: str = Field(description="Redacted, lower-cased question text")
    times_asked: int


class DocumentationGapReportDTO(BaseModel):
    total_unanswered_questions: int
    gaps: List[DocumentationGapDTO]
