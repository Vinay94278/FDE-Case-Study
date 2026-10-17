"""Health and configuration summary for /api/v1/health."""
from typing import Optional

from app.core.settings import Settings
from app.dao.corpus_dao import CorpusDAO
from app.dto.health_dto import HealthResponseDTO
from app.ingestion.corpus_builder import CorpusBuildSummary
from app.llm.base_llm_client import BaseLlmClient
from app.retrieval.hybrid_retriever import HybridRetriever

SERVICE_STATUS_OK = "ok"


class HealthService:
    def __init__(self, settings: Settings, corpus_dao: CorpusDAO, retriever: HybridRetriever,
                 llm_client: Optional[BaseLlmClient], answer_mode_name: str,
                 document_source_name: str, build_summary: CorpusBuildSummary):
        self.settings = settings
        self.corpus_dao = corpus_dao
        self.retriever = retriever
        self.llm_client = llm_client
        self.answer_mode_name = answer_mode_name
        self.document_source_name = document_source_name
        self.build_summary = build_summary

    async def get_health(self) -> HealthResponseDTO:
        llm_provider: Optional[str] = None
        llm_model: Optional[str] = None
        if self.llm_client is not None:
            llm_provider = self.llm_client.get_provider_name()
            llm_model = self.llm_client.get_model_name()

        return HealthResponseDTO(
            service_status=SERVICE_STATUS_OK,
            version=self.settings.app_version,
            environment=self.settings.app_env,
            answer_mode=self.answer_mode_name,
            llm_provider=llm_provider,
            llm_model=llm_model,
            embeddings_status=self.retriever.get_embeddings_status(),
            document_source=self.document_source_name,
            document_count=self.build_summary.document_count,
            chunk_count=self.build_summary.chunk_count,
            sentence_count=self.build_summary.sentence_count,
        )
