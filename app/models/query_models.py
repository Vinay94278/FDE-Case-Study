"""Domain models for an incoming question and its search results."""
from dataclasses import dataclass, field
from typing import List, Optional

from app.models.corpus_models import Chunk


@dataclass(frozen=True)
class ConversationTurn:
    question: str
    answer: str


@dataclass
class Query:
    """A question moving through the pipeline.

    original_question    exactly what the admin typed
    standalone_question  the follow-up rewritten to stand alone (same as original if not a follow-up)
    search_text          standalone question with glossary synonyms applied, used only for search
    """

    original_question: str
    conversation_history: List[ConversationTurn]
    include_debug: bool
    standalone_question: str = ""
    search_text: str = ""
    was_rewritten: bool = False
    rewrite_note: str = ""


@dataclass(frozen=True)
class RetrievalHit:
    """One chunk returned by search, with every score used to judge it."""

    chunk: Chunk
    fused_score: float
    keyword_score: float
    cosine_similarity: Optional[float]
    term_coverage: float


@dataclass
class RetrievalResult:
    hits: List[RetrievalHit] = field(default_factory=list)
    query_terms: List[str] = field(default_factory=list)
