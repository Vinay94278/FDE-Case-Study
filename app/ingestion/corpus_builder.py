"""Ingestion pipeline: source -> documents -> sentences -> chunks -> corpus store.

Runs once at startup today. In production it would run on a schedule or a
"docs changed" webhook, and serving would switch to the new corpus only once
the build has finished.
"""
import logging
from dataclasses import dataclass
from typing import List

from app.dao.corpus_dao import CorpusDAO
from app.dao.document_source_dao import DocumentSourceDAO
from app.ingestion.sentence_chunker import build_chunks, build_sentences
from app.models.corpus_models import Chunk, Sentence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CorpusBuildSummary:
    document_count: int
    sentence_count: int
    chunk_count: int


class CorpusBuilder:
    def __init__(self, document_source: DocumentSourceDAO, corpus_dao: CorpusDAO,
                 max_chunk_chars: int, overlap_sentence_count: int):
        self.document_source = document_source
        self.corpus_dao = corpus_dao
        self.max_chunk_chars = max_chunk_chars
        self.overlap_sentence_count = overlap_sentence_count

    def build(self) -> CorpusBuildSummary:
        documents = self.document_source.load_documents()

        all_sentences: List[Sentence] = []
        all_chunks: List[Chunk] = []
        for document in documents:
            document_sentences = build_sentences(document)
            document_chunks = build_chunks(
                document_sentences,
                self.max_chunk_chars,
                self.overlap_sentence_count,
            )
            all_sentences.extend(document_sentences)
            all_chunks.extend(document_chunks)

        self.corpus_dao.replace_corpus(documents, all_sentences, all_chunks)
        return CorpusBuildSummary(
            document_count=len(documents),
            sentence_count=len(all_sentences),
            chunk_count=len(all_chunks),
        )
