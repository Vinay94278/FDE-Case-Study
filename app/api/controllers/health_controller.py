"""GET /api/v1/health: liveness plus a summary of the active configuration."""
from fastapi import APIRouter, Depends

from app.api.dependencies import get_health_service
from app.core.constants import API_VERSION_PREFIX
from app.core.response_builder import build_success_response
from app.dto.api_response_dto import ApiResponseDTO
from app.dto.health_dto import HealthResponseDTO
from app.services.health_service import HealthService

router = APIRouter(prefix=API_VERSION_PREFIX, tags=["Health"])


@router.get("/health", response_model=ApiResponseDTO[HealthResponseDTO], summary="Service health")
async def get_health(health_service: HealthService = Depends(get_health_service)) -> ApiResponseDTO[HealthResponseDTO]:
    health_dto = await health_service.get_health()
    return build_success_response(data=health_dto, message="Service is healthy.")
