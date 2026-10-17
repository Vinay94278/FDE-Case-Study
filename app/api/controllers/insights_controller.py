"""GET /api/v1/insights/documentation-gaps: what the docs should cover next."""
from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_insights_service
from app.core.constants import API_VERSION_PREFIX
from app.core.response_builder import build_success_response
from app.dto.api_response_dto import ApiResponseDTO
from app.dto.insights_dto import DocumentationGapReportDTO
from app.services.insights_service import InsightsService

router = APIRouter(prefix=API_VERSION_PREFIX + "/insights", tags=["Insights"])


@router.get(
    "/documentation-gaps",
    response_model=ApiResponseDTO[DocumentationGapReportDTO],
    summary="Unanswered questions, most frequent first",
)
async def get_documentation_gaps(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of questions to return"),
    insights_service: InsightsService = Depends(get_insights_service),
) -> ApiResponseDTO[DocumentationGapReportDTO]:
    report_dto = await insights_service.get_documentation_gaps(limit)
    return build_success_response(data=report_dto, message="Documentation gap report.")
