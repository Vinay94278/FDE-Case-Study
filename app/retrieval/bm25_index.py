"""BM25 keyword index.

BM25 scores a chunk higher when it contains the question's words, gives rare words
("csv", "429") more weight than common ones ("plan"), and does not punish long
chunks the way the starter kit's Jaccard score does.
"""
import math
from collections import Counter
from typing import Dict, List

TERM_FREQUENCY_SATURATION = 1.5   # k1: how fast repeated words stop adding score
LENGTH_NORMALIZATION = 0.75       # b: how much long chunks are scaled down


class Bm25Index:
    def __init__(self, terms_per_chunk: List[List[str]]):
        self.chunk_count = len(terms_per_chunk)
        self.term_counts_per_chunk: List[Counter] = []
        self.chunk_lengths: List[int] = []
        self.document_frequency: Dict[str, int] = Counter()

        for chunk_terms in terms_per_chunk:
            self.term_counts_per_chunk.append(Counter(chunk_terms))
            self.chunk_lengths.append(len(chunk_terms))
            for unique_term in set(chunk_terms):
                self.document_frequency[unique_term] += 1

        if self.chunk_count > 0:
            self.average_chunk_length = sum(self.chunk_lengths) / self.chunk_count
        else:
            self.average_chunk_length = 0.0

    def inverse_document_frequency(self, term: str) -> float:
        """High for rare terms, low for terms found in many chunks, 0-ish for unknown-everywhere terms."""
        chunks_containing_term = self.document_frequency.get(term, 0)
        numerator = self.chunk_count - chunks_containing_term + 0.5
        denominator = chunks_containing_term + 0.5
        return math.log(1 + numerator / denominator)

    def score_all_chunks(self, query_terms: List[str]) -> List[float]:
        unique_query_terms = set(query_terms)
        average_length = self.average_chunk_length
        if average_length == 0:
            average_length = 1.0

        chunk_scores = []
        for chunk_index in range(self.chunk_count):
            term_counts = self.term_counts_per_chunk[chunk_index]
            chunk_length = self.chunk_lengths[chunk_index]
            chunk_score = 0.0
            for query_term in unique_query_terms:
                term_frequency = term_counts.get(query_term, 0)
                if term_frequency == 0:
                    continue
                length_factor = 1 - LENGTH_NORMALIZATION + LENGTH_NORMALIZATION * chunk_length / average_length
                normalized_frequency = (
                    term_frequency * (TERM_FREQUENCY_SATURATION + 1)
                    / (term_frequency + TERM_FREQUENCY_SATURATION * length_factor)
                )
                chunk_score = chunk_score + self.inverse_document_frequency(query_term) * normalized_frequency
            chunk_scores.append(chunk_score)
        return chunk_scores
