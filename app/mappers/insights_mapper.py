"""DocumentationGap models -> gap report DTO."""
from typing import List

from app.dto.insights_dto import DocumentationGapDTO, DocumentationGapReportDTO
from app.models.log_models import DocumentationGap


class InsightsMapper:
    @staticmethod
    def to_gap_report_dto(documentation_gaps: List[DocumentationGap], total_unanswered: int) -> DocumentationGapReportDTO:
        gap_dtos = []
        for documentation_gap in documentation_gaps:
            gap_dtos.append(DocumentationGapDTO(
                question=documentation_gap.question,
                times_asked=documentation_gap.times_asked,
            ))
        return DocumentationGapReportDTO(total_unanswered_questions=total_unanswered, gaps=gap_dtos)
