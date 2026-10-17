"""Answering strategies are pluggable: the service picks one at startup.

    LlmAnswerStrategy         an LLM writes a grounded answer, code verifies it
    ExtractiveAnswerStrategy  no LLM: the best matching doc sentences, verbatim

Both return the same Answer model, so everything after them (mapping, logging,
the API response) is identical.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from app.core.constants import MAX_RELATED_DOCUMENTS
from app.models.answer_models import Answer, AnswerMode, AnswerStatus, AnswerType, RelatedDocument
from app.models.query_models import Query, RetrievalHit, RetrievalResult


class AnswerStrategy(ABC):
    @abstractmethod
    def get_mode(self) -> AnswerMode:
        """The mode reported in responses and /health."""

    @abstractmethod
    async def generate_answer(self, query: Query) -> Answer:
        """Produce an answer, a partial answer, or a refusal. Never raises for a normal question."""


def build_related_documents(hits: List[RetrievalHit]) -> List[RelatedDocument]:
    """Up to two articles that share terms with the question, for refusal messages."""
    related_documents: List[RelatedDocument] = []
    seen_doc_ids = set()
    for hit in hits:
        if hit.term_coverage <= 0:
            continue
        if hit.chunk.doc_id in seen_doc_ids:
            continue
        seen_doc_ids.add(hit.chunk.doc_id)
        related_documents.append(RelatedDocument(doc_id=hit.chunk.doc_id, title=hit.chunk.title))
        if len(related_documents) >= MAX_RELATED_DOCUMENTS:
            break
    return related_documents


def build_refusal_answer(mode: AnswerMode, decision_reason: str, hits: List[RetrievalHit],
                         refusal_message: str, debug_details: Dict[str, Any]) -> Answer:
    return Answer(
        status=AnswerStatus.NOT_COVERED,
        answer_type=AnswerType.REFUSAL,
        mode=mode,
        text=refusal_message,
        decision_reason=decision_reason,
        related_documents=build_related_documents(hits),
        debug_details=debug_details,
    )


def build_retrieval_debug(retrieval_result: RetrievalResult) -> Dict[str, Any]:
    """Scores for every retrieved chunk, shown when include_debug=true."""
    hit_details = []
    for hit in retrieval_result.hits:
        hit_details.append({
            "chunk_id": hit.chunk.chunk_id,
            "fused_score": hit.fused_score,
            "keyword_score": hit.keyword_score,
            "cosine_similarity": hit.cosine_similarity,
            "term_coverage": hit.term_coverage,
        })
    return {
        "query_terms": retrieval_result.query_terms,
        "retrieved_chunks": hit_details,
    }
