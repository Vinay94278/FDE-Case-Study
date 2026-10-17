"""Converts between the ask DTOs (API layer) and the query/answer models (service layer)."""
from typing import List, Optional

from app.core.constants import (
    ANSWERED_ENVELOPE_MESSAGE,
    NOT_COVERED_ENVELOPE_MESSAGE,
    PARTIAL_ENVELOPE_MESSAGE,
    UNAVAILABLE_ENVELOPE_MESSAGE,
)
from app.dto.ask_dto import AskRequestDTO, AskResponseDTO, CitationDTO, RelatedDocumentDTO
from app.models.answer_models import Answer, AnswerMode, AnswerStatus
from app.models.query_models import ConversationTurn, Query


class AskMapper:
    @staticmethod
    def to_query_model(request_dto: AskRequestDTO, max_history_turns: int) -> Query:
        """RequestDTO -> Query model. Only the most recent turns are kept."""
        if max_history_turns <= 0:
            recent_turn_dtos = []
        else:
            recent_turn_dtos = request_dto.conversation_history[-max_history_turns:]

        conversation_history: List[ConversationTurn] = []
        for turn_dto in recent_turn_dtos:
            conversation_history.append(ConversationTurn(question=turn_dto.question, answer=turn_dto.answer))

        return Query(
            original_question=request_dto.question,
            conversation_history=conversation_history,
            include_debug=request_dto.include_debug,
            standalone_question=request_dto.question,
            search_text=request_dto.question,
        )

    @staticmethod
    def to_response_dto(query: Query, answer: Answer) -> AskResponseDTO:
        """Answer model -> ResponseDTO."""
        citation_dtos = []
        for sentence in answer.cited_sentences:
            citation_dtos.append(CitationDTO(
                sentence_id=sentence.sentence_id,
                doc_id=sentence.doc_id,
                title=sentence.title,
                text=sentence.text,
            ))

        related_document_dtos = []
        for related_document in answer.related_documents:
            related_document_dtos.append(RelatedDocumentDTO(
                doc_id=related_document.doc_id,
                title=related_document.title,
            ))

        standalone_question: Optional[str] = None
        if query.was_rewritten:
            standalone_question = query.standalone_question

        debug_details = None
        if query.include_debug:
            debug_details = dict(answer.debug_details)
            debug_details["search_text"] = query.search_text
            debug_details["followup_rewrite"] = query.rewrite_note

        return AskResponseDTO(
            question=query.original_question,
            standalone_question=standalone_question,
            answer_status=answer.status.value,
            answer_type=answer.answer_type.value,
            answer=answer.text,
            missing_information=answer.missing_information,
            citations=citation_dtos,
            related_documents=related_document_dtos,
            mode=answer.mode.value,
            decision_reason=answer.decision_reason,
            latency_ms=answer.latency_ms,
            debug=debug_details,
        )

    @staticmethod
    def build_envelope_message(response_dto: AskResponseDTO) -> str:
        """Short message for the response envelope, matching the answer outcome."""
        if response_dto.mode == AnswerMode.LLM_UNAVAILABLE.value:
            return UNAVAILABLE_ENVELOPE_MESSAGE
        if response_dto.answer_status == AnswerStatus.ANSWERED.value:
            return ANSWERED_ENVELOPE_MESSAGE
        if response_dto.answer_status == AnswerStatus.PARTIAL.value:
            return PARTIAL_ENVELOPE_MESSAGE
        return NOT_COVERED_ENVELOPE_MESSAGE
