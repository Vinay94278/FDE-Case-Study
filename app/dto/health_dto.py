"""DTOs for GET /api/v1/health."""
from typing import Optional

from pydantic import BaseModel


class HealthResponseDTO(BaseModel):
    service_status: str
    version: str
    environment: str
    answer_mode: str
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    embeddings_status: str
    document_source: str
    document_count: int
    chunk_count: int
    sentence_count: int
