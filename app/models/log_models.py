"""Records written to the query log store."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class QueryLogRecord:
    record_type: str
    timestamp: str
    request_id: str
    question: str
    standalone_question: Optional[str]
    answer_status: str
    mode: str
    decision_reason: str
    latency_ms: int
    cited_doc_ids: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class FeedbackRecord:
    record_type: str
    feedback_id: str
    timestamp: str
    request_id: str
    question: str
    answer_status: str
    helpful: bool
    comment: Optional[str] = None


@dataclass(frozen=True)
class DocumentationGap:
    question: str
    times_asked: int
