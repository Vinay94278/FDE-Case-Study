"""Hybrid search: BM25 keywords + optional embeddings, combined with Reciprocal Rank Fusion.

    - BM25 is exact on product words ("CSV", "SSO", "429") and needs no model.
    - Embeddings catch paraphrases ("add a user" vs "invite a team member").
    - RRF combines the two rankings by position, so their different score scales never
      have to be compared directly.

Where the index lives (in memory, rebuilt at startup):
    self.chunks               chunk models (the metadata)            row i  <->  chunk i
    self.bm25_index           keyword statistics per chunk
    self.chunk_vectors        embedding matrix, shape (chunks, 384)  row i  <->  chunk i
    self.sentence_vectors     embedding matrix, shape (sentences, 384)
"""
import logging
from typing import Dict, List, Optional, Set

from app.core.exceptions import RetrievalException
from app.dao.corpus_dao import CorpusDAO
from app.models.corpus_models import Chunk
from app.models.query_models import RetrievalHit, RetrievalResult
from app.retrieval.bm25_index import Bm25Index
from app.retrieval.embedding_model import EmbeddingModel
from app.retrieval.text_processing import extract_search_terms, extract_unique_search_terms

logger = logging.getLogger(__name__)

RECIPROCAL_RANK_CONSTANT = 60


class HybridRetriever:
    def __init__(self, corpus_dao: CorpusDAO, embedding_model: EmbeddingModel):
        self.embedding_model = embedding_model
        self.chunks: List[Chunk] = corpus_dao.find_all_chunks()
        self.chunk_term_sets: List[Set[str]] = []

        terms_per_chunk = []
        for chunk in self.chunks:
            chunk_terms = extract_search_terms(chunk.get_searchable_text())
            terms_per_chunk.append(chunk_terms)
            self.chunk_term_sets.append(set(chunk_terms))
        self.bm25_index = Bm25Index(terms_per_chunk)

        self.chunk_vectors = None
        self.sentence_vectors = None
        self.sentence_row_by_id: Dict[str, int] = {}
        self._build_embedding_matrices(corpus_dao)

    def _build_embedding_matrices(self, corpus_dao: CorpusDAO) -> None:
        if not self.embedding_model.is_available:
            return

        chunk_texts = []
        for chunk in self.chunks:
            chunk_texts.append(chunk.get_searchable_text())
        self.chunk_vectors = self.embedding_model.encode(chunk_texts)

        sentence_texts = []
        for row_number, sentence in enumerate(corpus_dao.find_all_sentences()):
            self.sentence_row_by_id[sentence.sentence_id] = row_number
            sentence_texts.append(sentence.text)
        self.sentence_vectors = self.embedding_model.encode(sentence_texts)
        logger.info("Embedding index built for %d chunks and %d sentences", len(chunk_texts), len(sentence_texts))

    # ------------------------------------------------------------------ public API

    def get_embeddings_status(self) -> str:
        return self.embedding_model.status_description

    def get_term_weight(self, term: str) -> float:
        """How informative a term is (BM25 inverse document frequency)."""
        return self.bm25_index.inverse_document_frequency(term)

    def search(self, search_text: str, top_k: int) -> RetrievalResult:
        """Return the top_k chunks for the text, each with every score used to judge it."""
        try:
            return self._search(search_text, top_k)
        except Exception as error:
            raise RetrievalException(technical_message=type(error).__name__ + ": " + str(error)) from error

    def compute_sentence_similarities(self, text: str, sentence_ids: List[str]) -> Dict[str, float]:
        """Cosine similarity between the text and each sentence. Empty when embeddings are off."""
        similarities_by_id: Dict[str, float] = {}
        if self.sentence_vectors is None:
            return similarities_by_id

        query_vector = self.embedding_model.encode([text])[0]
        for sentence_id in sentence_ids:
            row_number = self.sentence_row_by_id.get(sentence_id)
            if row_number is None:
                continue
            similarity = float(self.sentence_vectors[row_number] @ query_vector)
            similarities_by_id[sentence_id] = similarity
        return similarities_by_id

    # ------------------------------------------------------------------ internals

    def _search(self, search_text: str, top_k: int) -> RetrievalResult:
        query_terms = extract_unique_search_terms(search_text)
        keyword_scores = self.bm25_index.score_all_chunks(query_terms)
        cosine_scores = self._compute_chunk_cosines(search_text)

        fused_scores = [0.0] * len(self.chunks)
        self._add_rank_contributions(fused_scores, keyword_scores, only_positive_scores=True)
        if cosine_scores is not None:
            self._add_rank_contributions(fused_scores, cosine_scores, only_positive_scores=False)

        ranked_chunk_indexes = self._sort_indexes_by_score_descending(fused_scores)

        hits = []
        for chunk_index in ranked_chunk_indexes:
            if fused_scores[chunk_index] == 0:
                continue
            if len(hits) >= top_k:
                break
            cosine_value: Optional[float] = None
            if cosine_scores is not None:
                cosine_value = round(cosine_scores[chunk_index], 3)
            hit = RetrievalHit(
                chunk=self.chunks[chunk_index],
                fused_score=round(fused_scores[chunk_index], 5),
                keyword_score=round(keyword_scores[chunk_index], 3),
                cosine_similarity=cosine_value,
                term_coverage=self._compute_term_coverage(query_terms, chunk_index),
            )
            hits.append(hit)

        return RetrievalResult(hits=hits, query_terms=query_terms)

    def _compute_chunk_cosines(self, search_text: str) -> Optional[List[float]]:
        if self.chunk_vectors is None:
            return None
        query_vector = self.embedding_model.encode([search_text])[0]
        cosine_scores = []
        for chunk_vector in self.chunk_vectors:
            cosine_scores.append(float(chunk_vector @ query_vector))
        return cosine_scores

    def _add_rank_contributions(self, fused_scores: List[float], scores: List[float], only_positive_scores: bool) -> None:
        """Reciprocal Rank Fusion: add 1 / (60 + rank) for each chunk's rank in this list."""
        candidate_indexes = []
        for chunk_index, score in enumerate(scores):
            if only_positive_scores and score <= 0:
                continue
            candidate_indexes.append(chunk_index)

        ranked_indexes = self._sort_indexes_by_score_descending(scores, candidate_indexes)
        for rank_position, chunk_index in enumerate(ranked_indexes):
            fused_scores[chunk_index] = fused_scores[chunk_index] + 1 / (RECIPROCAL_RANK_CONSTANT + rank_position + 1)

    @staticmethod
    def _sort_indexes_by_score_descending(scores: List[float], candidate_indexes: Optional[List[int]] = None) -> List[int]:
        if candidate_indexes is None:
            candidate_indexes = list(range(len(scores)))

        def read_negative_score(chunk_index: int) -> float:
            return -scores[chunk_index]

        return sorted(candidate_indexes, key=read_negative_score)

    def _compute_term_coverage(self, query_terms: List[str], chunk_index: int) -> float:
        """Share of the question's informative terms that appear in this chunk."""
        if len(query_terms) == 0:
            return 0.0
        matched_term_count = 0
        for query_term in query_terms:
            if query_term in self.chunk_term_sets[chunk_index]:
                matched_term_count = matched_term_count + 1
        return round(matched_term_count / len(query_terms), 3)
