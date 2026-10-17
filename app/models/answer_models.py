"""Domain models for an answer produced by an answering strategy."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.models.corpus_models import Sentence


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    PARTIAL = "partial"
    NOT_COVERED = "not_covered"


class AnswerType(str, Enum):
    GENERATED_ANSWER = "generated_answer"
    VERBATIM_PASSAGE = "verbatim_passage"
    REFUSAL = "refusal"


class AnswerMode(str, Enum):
    LLM = "llm"
    EXTRACTIVE = "extractive"
    LLM_UNAVAILABLE = "llm_unavailable"


@dataclass(frozen=True)
class RelatedDocument:
    doc_id: str
    title: str


@dataclass
class Answer:
    status: AnswerStatus
    answer_type: AnswerType
    mode: AnswerMode
    text: str
    decision_reason: str
    cited_sentences: List[Sentence] = field(default_factory=list)
    related_documents: List[RelatedDocument] = field(default_factory=list)
    missing_information: Optional[str] = None
    latency_ms: int = 0
    debug_details: Dict[str, Any] = field(default_factory=dict)
