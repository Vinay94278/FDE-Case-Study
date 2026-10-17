"""DTOs for POST /api/v1/ask."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import (
    MAX_HISTORY_ANSWER_LENGTH,
    MAX_HISTORY_TURNS_ACCEPTED,
    MAX_QUESTION_LENGTH,
    MIN_QUESTION_LENGTH,
)


def _collapse_whitespace(text: str) -> str:
    """Turn any run of spaces, tabs or newlines into a single space."""
    words = text.split()
    return " ".join(words)


class ConversationTurnDTO(BaseModel):
    """One earlier question and the answer that was shown for it."""

    question: str = Field(max_length=MAX_QUESTION_LENGTH)
    answer: str = Field(default="", max_length=MAX_HISTORY_ANSWER_LENGTH)


class AskRequestDTO(BaseModel):
    question: str = Field(
        min_length=MIN_QUESTION_LENGTH,
        max_length=MAX_QUESTION_LENGTH,
        description="The admin's question in plain English",
    )
    conversation_history: List[ConversationTurnDTO] = Field(
        default_factory=list,
        max_length=MAX_HISTORY_TURNS_ACCEPTED,
        description="Earlier turns, oldest first. Used only to understand follow-up questions.",
    )
    include_debug: bool = Field(
        default=False,
        description="Return retrieval scores and gate decisions for troubleshooting",
    )

    @field_validator("question")
    @classmethod
    def clean_question(cls, question_text: str) -> str:
        cleaned_question = _collapse_whitespace(question_text)
        if len(cleaned_question) < MIN_QUESTION_LENGTH:
            raise ValueError("Question must have at least " + str(MIN_QUESTION_LENGTH) + " characters")
        return cleaned_question


class CitationDTO(BaseModel):
    sentence_id: str
    doc_id: str
    title: str
    text: str


class RelatedDocumentDTO(BaseModel):
    doc_id: str
    title: str


class AskResponseDTO(BaseModel):
    question: str
    standalone_question: Optional[str] = Field(
        default=None,
        description="Set when a follow-up was rewritten into a standalone question",
    )
    answer_status: str = Field(description='"answered", "partial" or "not_covered"')
    answer_type: str = Field(description='"generated_answer", "verbatim_passage" or "refusal"')
    answer: str
    missing_information: Optional[str] = None
    citations: List[CitationDTO] = Field(default_factory=list)
    related_documents: List[RelatedDocumentDTO] = Field(default_factory=list)
    mode: str = Field(description='"llm", "extractive" or "llm_unavailable"')
    decision_reason: str
    latency_ms: int
    debug: Optional[Dict[str, Any]] = None
