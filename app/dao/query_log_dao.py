"""Query log DAO: stores asked questions, outcomes and feedback.

Uses:
    - Documentation gap report: unanswered questions, most frequent first.
    - Quality monitoring: refusal rate, feedback, latency.

File writes are blocking, so they run in a worker thread (asyncio.to_thread) and
never block the event loop. A lock keeps concurrent writes from interleaving.
"""
import asyncio
import json
import logging
import threading
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Iterator, List

from app.core.component_registry import ComponentRegistry
from app.core.exceptions import StorageException
from app.core.settings import Settings
from app.models.log_models import DocumentationGap, FeedbackRecord, QueryLogRecord

logger = logging.getLogger(__name__)

QUERY_LOG_STORE_REGISTRY = ComponentRegistry("query log store")

QUERY_RECORD_TYPE = "query"
FEEDBACK_RECORD_TYPE = "feedback"
NOT_COVERED_STATUS = "not_covered"


class QueryLogDAO(ABC):
    @abstractmethod
    async def save_query_record(self, record: QueryLogRecord) -> None:
        """Persist one answered question."""

    @abstractmethod
    async def save_feedback_record(self, record: FeedbackRecord) -> None:
        """Persist one thumbs up / thumbs down."""

    @abstractmethod
    async def find_documentation_gaps(self, result_limit: int) -> List[DocumentationGap]:
        """Unanswered questions grouped by text, most frequent first."""

    @abstractmethod
    async def count_unanswered_questions(self) -> int:
        """Total number of unanswered questions logged."""


class JsonlQueryLogDAO(QueryLogDAO):
    """Appends one JSON object per line to a local file."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._write_lock = threading.Lock()
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise StorageException(
                technical_message="Cannot create log directory " + str(self.file_path.parent) + ": " + str(error)
            ) from error

    async def save_query_record(self, record: QueryLogRecord) -> None:
        await asyncio.to_thread(self._append_line, asdict(record))

    async def save_feedback_record(self, record: FeedbackRecord) -> None:
        await asyncio.to_thread(self._append_line, asdict(record))

    async def find_documentation_gaps(self, result_limit: int) -> List[DocumentationGap]:
        return await asyncio.to_thread(self._read_documentation_gaps, result_limit)

    async def count_unanswered_questions(self) -> int:
        return await asyncio.to_thread(self._count_unanswered)

    # ------------------------------------------------------------------ blocking helpers (run in a thread)

    def _append_line(self, record_fields: dict) -> None:
        serialized_record = json.dumps(record_fields)
        try:
            with self._write_lock:
                with open(self.file_path, "a", encoding="utf-8") as log_file:
                    log_file.write(serialized_record + "\n")
        except OSError as error:
            raise StorageException(
                technical_message="Cannot write to " + str(self.file_path) + ": " + str(error)
            ) from error

    def _iterate_records(self) -> Iterator[dict]:
        if not self.file_path.exists():
            return
        try:
            with open(self.file_path, encoding="utf-8") as log_file:
                for line_text in log_file:
                    stripped_line = line_text.strip()
                    if stripped_line == "":
                        continue
                    try:
                        yield json.loads(stripped_line)
                    except json.JSONDecodeError:
                        logger.warning("Skipping a corrupt line in %s", self.file_path.name)
        except OSError as error:
            raise StorageException(
                technical_message="Cannot read " + str(self.file_path) + ": " + str(error)
            ) from error

    def _collect_unanswered_question_counts(self) -> Counter:
        question_counts: Counter = Counter()
        for record_fields in self._iterate_records():
            is_query_record = record_fields.get("record_type") == QUERY_RECORD_TYPE
            is_unanswered = record_fields.get("answer_status") == NOT_COVERED_STATUS
            if is_query_record and is_unanswered:
                normalized_question = str(record_fields.get("question", "")).strip().lower()
                question_counts[normalized_question] += 1
        return question_counts

    def _read_documentation_gaps(self, result_limit: int) -> List[DocumentationGap]:
        question_counts = self._collect_unanswered_question_counts()
        documentation_gaps = []
        for question_text, times_asked in question_counts.most_common(result_limit):
            documentation_gaps.append(DocumentationGap(question=question_text, times_asked=times_asked))
        return documentation_gaps

    def _count_unanswered(self) -> int:
        question_counts = self._collect_unanswered_question_counts()
        return sum(question_counts.values())


class NullQueryLogDAO(QueryLogDAO):
    """Stores nothing. Used by the eval runner so test questions don't pollute the gap report."""

    async def save_query_record(self, record: QueryLogRecord) -> None:
        return None

    async def save_feedback_record(self, record: FeedbackRecord) -> None:
        return None

    async def find_documentation_gaps(self, result_limit: int) -> List[DocumentationGap]:
        return []

    async def count_unanswered_questions(self) -> int:
        return 0


@QUERY_LOG_STORE_REGISTRY.register("jsonl")
def build_jsonl_query_log(settings: Settings) -> QueryLogDAO:
    return JsonlQueryLogDAO(settings.query_log_path)


@QUERY_LOG_STORE_REGISTRY.register("none")
def build_null_query_log(settings: Settings) -> QueryLogDAO:
    return NullQueryLogDAO()
