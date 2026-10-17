"""Question answering service: orchestrates one question from request to response.

    AskRequestDTO
      -> AskMapper.to_query_model            (DTO -> model)
      -> FollowUpRewriter                    (follow-up -> standalone question)
      -> QueryExpander                       (admin wording -> doc wording, for search)
      -> AnswerStrategy                      (LLM with 3 guard layers, or extractive)
      -> QueryLogDAO                         (redacted record, for the gap report)
      -> AskMapper.to_response_dto           (model -> DTO)
    AskResponseDTO
"""
import logging
import time

from app.core.exceptions import AppException
from app.core.request_context import get_current_request_id
from app.dao.query_log_dao import QueryLogDAO
from app.dto.ask_dto import AskRequestDTO, AskResponseDTO
from app.mappers.ask_mapper import AskMapper
from app.mappers.query_log_mapper import QueryLogMapper
from app.models.answer_models import Answer
from app.models.query_models import Query
from app.retrieval.glossary import QueryExpander
from app.services.answering.answer_strategy import AnswerStrategy
from app.services.followup_rewriter import FollowUpRewriter

logger = logging.getLogger(__name__)


class QuestionAnsweringService:
    def __init__(self, answer_strategy: AnswerStrategy, followup_rewriter: FollowUpRewriter,
                 query_expander: QueryExpander, query_log_dao: QueryLogDAO, max_history_turns: int):
        self.answer_strategy = answer_strategy
        self.followup_rewriter = followup_rewriter
        self.query_expander = query_expander
        self.query_log_dao = query_log_dao
        self.max_history_turns = max_history_turns

    def get_answer_mode_name(self) -> str:
        return self.answer_strategy.get_mode().value

    async def answer_question(self, request_dto: AskRequestDTO) -> AskResponseDTO:
        started_at = time.perf_counter()
        query = AskMapper.to_query_model(request_dto, self.max_history_turns)

        rewrite_result = await self.followup_rewriter.resolve_standalone_question(query)
        query.standalone_question = rewrite_result.standalone_question
        query.was_rewritten = rewrite_result.was_rewritten
        query.rewrite_note = rewrite_result.note
        query.search_text = self.query_expander.expand(query.standalone_question)

        answer = await self.answer_strategy.generate_answer(query)
        answer.latency_ms = int((time.perf_counter() - started_at) * 1000)

        logger.info(
            "Question handled: status=%s mode=%s reason=%s followup=%s latency_ms=%d",
            answer.status.value,
            answer.mode.value,
            answer.decision_reason,
            query.was_rewritten,
            answer.latency_ms,
        )

        await self._save_query_log_safely(query, answer)
        return AskMapper.to_response_dto(query, answer)

    async def _save_query_log_safely(self, query: Query, answer: Answer) -> None:
        """A logging failure must never cost the admin their answer."""
        try:
            log_record = QueryLogMapper.to_query_log_record(query, answer, get_current_request_id())
            await self.query_log_dao.save_query_record(log_record)
        except AppException as error:
            logger.error("Query log not saved (%s): %s", error.error_code, error.technical_message)
        except Exception:
            logger.exception("Query log not saved because of an unexpected error")
