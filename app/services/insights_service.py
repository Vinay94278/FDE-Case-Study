"""Documentation gap report: the questions admins asked that the docs could not answer."""
from app.dao.query_log_dao import QueryLogDAO
from app.dto.insights_dto import DocumentationGapReportDTO
from app.mappers.insights_mapper import InsightsMapper


class InsightsService:
    def __init__(self, query_log_dao: QueryLogDAO):
        self.query_log_dao = query_log_dao

    async def get_documentation_gaps(self, result_limit: int) -> DocumentationGapReportDTO:
        documentation_gaps = await self.query_log_dao.find_documentation_gaps(result_limit)
        total_unanswered = await self.query_log_dao.count_unanswered_questions()
        return InsightsMapper.to_gap_report_dto(documentation_gaps, total_unanswered)
