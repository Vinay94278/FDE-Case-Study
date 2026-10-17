"""Builds and holds every component once, at startup (simple dependency injection).

Which implementation is used for each pluggable part comes from settings:
    DOCUMENT_SOURCE   -> DOCUMENT_SOURCE_REGISTRY
    QUERY_LOG_STORE   -> QUERY_LOG_STORE_REGISTRY
    LLM_PROVIDER      -> LLM_CLIENT_REGISTRY (none / no key -> extractive strategy)
"""
import asyncio
import logging
from typing import Optional

from app.core.settings import Settings
from app.dao.corpus_dao import InMemoryCorpusDAO
from app.dao.document_source_dao import DOCUMENT_SOURCE_REGISTRY
from app.dao.query_log_dao import QUERY_LOG_STORE_REGISTRY, QueryLogDAO
from app.ingestion.corpus_builder import CorpusBuilder
from app.llm.base_llm_client import BaseLlmClient
from app.llm.llm_client_factory import create_llm_client
from app.llm.prompt_loader import ANSWER_PROMPT_NAME, FOLLOWUP_REWRITE_PROMPT_NAME, load_prompt
from app.retrieval.embedding_model import EmbeddingModel
from app.retrieval.glossary import QueryExpander, load_glossary
from app.retrieval.hybrid_retriever import HybridRetriever
from app.services.answering.answer_strategy import AnswerStrategy
from app.services.answering.extractive_answer_strategy import ExtractiveAnswerStrategy
from app.services.answering.llm_answer_strategy import LlmAnswerStrategy
from app.services.feedback_service import FeedbackService
from app.services.followup_rewriter import FollowUpRewriter
from app.services.guards.entity_coverage_checker import EntityCoverageChecker
from app.services.guards.grounding_verifier import GroundingVerifier
from app.services.guards.relevance_gate import RelevanceGate
from app.services.health_service import HealthService
from app.services.insights_service import InsightsService
from app.services.question_answering_service import QuestionAnsweringService

logger = logging.getLogger(__name__)


class ApplicationContainer:
    def __init__(self, settings: Settings, llm_client: Optional[BaseLlmClient],
                 question_answering_service: QuestionAnsweringService, feedback_service: FeedbackService,
                 insights_service: InsightsService, health_service: HealthService,
                 query_log_dao: QueryLogDAO):
        self.settings = settings
        self.llm_client = llm_client
        self.question_answering_service = question_answering_service
        self.feedback_service = feedback_service
        self.insights_service = insights_service
        self.health_service = health_service
        self.query_log_dao = query_log_dao

    @classmethod
    async def create(cls, settings: Settings, llm_client_override: Optional[BaseLlmClient] = None) -> "ApplicationContainer":
        """Build everything. Slow, blocking steps (file reads, model loading) run in worker threads."""
        # ---- ingestion: source -> sentences -> chunks -> corpus store
        corpus_dao = InMemoryCorpusDAO()
        document_source = DOCUMENT_SOURCE_REGISTRY.create(settings.document_source, settings)
        corpus_builder = CorpusBuilder(
            document_source,
            corpus_dao,
            settings.chunk_max_chars,
            settings.chunk_overlap_sentences,
        )
        build_summary = await asyncio.to_thread(corpus_builder.build)

        # ---- retrieval
        embedding_model = await asyncio.to_thread(EmbeddingModel, settings.embedding_model, settings.embeddings_enabled)
        retriever = await asyncio.to_thread(HybridRetriever, corpus_dao, embedding_model)
        glossary = await asyncio.to_thread(load_glossary, settings.glossary_path)
        query_expander = QueryExpander(glossary)

        # ---- LLM (optional)
        if llm_client_override is not None:
            llm_client = llm_client_override
        else:
            llm_client = create_llm_client(settings)

        # ---- answering strategy: chosen once, based on whether an LLM is available
        relevance_gate = RelevanceGate(settings.min_cosine)
        answer_strategy: AnswerStrategy
        if llm_client is not None:
            answer_strategy = LlmAnswerStrategy(
                retriever=retriever,
                relevance_gate=relevance_gate,
                grounding_verifier=GroundingVerifier(),
                llm_client=llm_client,
                settings=settings,
                system_prompt=load_prompt(ANSWER_PROMPT_NAME),
            )
        else:
            answer_strategy = ExtractiveAnswerStrategy(
                retriever=retriever,
                relevance_gate=relevance_gate,
                entity_checker=EntityCoverageChecker(glossary),
                settings=settings,
            )

        followup_rewriter = FollowUpRewriter(
            llm_client=llm_client,
            system_prompt=load_prompt(FOLLOWUP_REWRITE_PROMPT_NAME),
            max_answer_chars=settings.followup_max_answer_chars,
        )

        # ---- storage and services
        query_log_dao = QUERY_LOG_STORE_REGISTRY.create(settings.query_log_store, settings)
        question_answering_service = QuestionAnsweringService(
            answer_strategy=answer_strategy,
            followup_rewriter=followup_rewriter,
            query_expander=query_expander,
            query_log_dao=query_log_dao,
            max_history_turns=settings.followup_max_turns,
        )
        health_service = HealthService(
            settings=settings,
            corpus_dao=corpus_dao,
            retriever=retriever,
            llm_client=llm_client,
            answer_mode_name=answer_strategy.get_mode().value,
            document_source_name=document_source.get_source_name(),
            build_summary=build_summary,
        )

        logger.info(
            "Service ready: mode=%s, %d documents, %d chunks, embeddings %s",
            answer_strategy.get_mode().value,
            build_summary.document_count,
            build_summary.chunk_count,
            retriever.get_embeddings_status(),
        )
        return cls(
            settings=settings,
            llm_client=llm_client,
            question_answering_service=question_answering_service,
            feedback_service=FeedbackService(query_log_dao),
            insights_service=InsightsService(query_log_dao),
            health_service=health_service,
            query_log_dao=query_log_dao,
        )

    async def close(self) -> None:
        if self.llm_client is None:
            return
        try:
            await self.llm_client.close()
        except Exception:
            logger.exception("LLM client did not close cleanly")
