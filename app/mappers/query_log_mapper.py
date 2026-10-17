"""Query + Answer models -> QueryLogRecord model (what the log store persists).

Question text is redacted here, so personal data never reaches storage.
"""
from typing import List, Optional

from app.models.answer_models import Answer
from app.models.log_models import QueryLogRecord
from app.models.query_models import Query
from app.utils.redaction import redact_personal_data
from app.utils.time_utils import utc_now_iso

QUERY_RECORD_TYPE = "query"


class QueryLogMapper:
    @staticmethod
    def to_query_log_record(query: Query, answer: Answer, request_id: str) -> QueryLogRecord:
        cited_doc_ids: List[str] = []
        for sentence in answer.cited_sentences:
            if sentence.doc_id not in cited_doc_ids:
                cited_doc_ids.append(sentence.doc_id)

        redacted_standalone_question: Optional[str] = None
        if query.was_rewritten:
            redacted_standalone_question = redact_personal_data(query.standalone_question)

        return QueryLogRecord(
            record_type=QUERY_RECORD_TYPE,
            timestamp=utc_now_iso(),
            request_id=request_id,
            question=redact_personal_data(query.original_question),
            standalone_question=redacted_standalone_question,
            answer_status=answer.status.value,
            mode=answer.mode.value,
            decision_reason=answer.decision_reason,
            latency_ms=answer.latency_ms,
            cited_doc_ids=sorted(cited_doc_ids),
        )
