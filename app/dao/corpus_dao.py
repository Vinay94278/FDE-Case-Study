"""Corpus DAO: stores the processed corpus (sentences and chunks) and serves lookups.

InMemoryCorpusDAO is right for a handful of articles: building it takes milliseconds.
At scale this interface is where a PostgresCorpusDAO (pgvector + full-text search)
would plug in, without changing the services that use it.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from app.models.corpus_models import Chunk, Document, Sentence

logger = logging.getLogger(__name__)


class CorpusDAO(ABC):
    @abstractmethod
    def replace_corpus(self, documents: List[Document], sentences: List[Sentence], chunks: List[Chunk]) -> None:
        """Replace the whole corpus with a newly built one."""

    @abstractmethod
    def find_sentence_by_id(self, sentence_id: str) -> Optional[Sentence]:
        """Return the sentence, or None if the ID is unknown."""

    @abstractmethod
    def find_all_chunks(self) -> List[Chunk]:
        """Return every chunk in a stable order."""

    @abstractmethod
    def find_all_sentences(self) -> List[Sentence]:
        """Return every sentence in a stable order."""

    @abstractmethod
    def count_documents(self) -> int:
        """Number of articles in the corpus."""


class InMemoryCorpusDAO(CorpusDAO):
    def __init__(self):
        self._documents: List[Document] = []
        self._sentences_in_order: List[Sentence] = []
        self._sentences_by_id: Dict[str, Sentence] = {}
        self._chunks_in_order: List[Chunk] = []

    def replace_corpus(self, documents: List[Document], sentences: List[Sentence], chunks: List[Chunk]) -> None:
        sentences_by_id = {}
        for sentence in sentences:
            sentences_by_id[sentence.sentence_id] = sentence

        self._documents = list(documents)
        self._sentences_in_order = list(sentences)
        self._sentences_by_id = sentences_by_id
        self._chunks_in_order = list(chunks)
        logger.info(
            "Corpus stored in memory: %d documents, %d sentences, %d chunks",
            len(documents),
            len(sentences),
            len(chunks),
        )

    def find_sentence_by_id(self, sentence_id: str) -> Optional[Sentence]:
        return self._sentences_by_id.get(sentence_id)

    def find_all_chunks(self) -> List[Chunk]:
        return list(self._chunks_in_order)

    def find_all_sentences(self) -> List[Sentence]:
        return list(self._sentences_in_order)

    def count_documents(self) -> int:
        return len(self._documents)
