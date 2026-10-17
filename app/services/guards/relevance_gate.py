"""Layer 1: relevance pre-filter.

Cheap check run before any LLM call: is any retrieved passage even loosely about
the question? If not, refuse immediately. This saves LLM cost and latency on
obviously out-of-scope questions ("What's the weather?").

It is deliberately NOT the main refusal mechanism: keyword overlap cannot tell
"related" from "answers the question". Layers 2 and 3 handle that.
"""
from typing import List, Optional

from app.models.guard_models import GateDecision
from app.models.query_models import RetrievalHit


class RelevanceGate:
    def __init__(self, min_cosine_similarity: float):
        self.min_cosine_similarity = min_cosine_similarity

    def evaluate(self, hits: List[RetrievalHit], min_term_coverage: float, allow_cosine_pass: bool) -> GateDecision:
        if len(hits) == 0:
            return GateDecision(passed=False, explanation="no passage shares any term with the question")

        best_term_coverage = self._find_best_term_coverage(hits)
        best_cosine_similarity = self._find_best_cosine_similarity(hits)

        if best_term_coverage >= min_term_coverage:
            return GateDecision(
                passed=True,
                explanation="term coverage " + str(best_term_coverage) + " >= " + str(min_term_coverage),
            )

        cosine_is_high_enough = (
            best_cosine_similarity is not None
            and best_cosine_similarity >= self.min_cosine_similarity
        )
        if allow_cosine_pass and cosine_is_high_enough:
            return GateDecision(
                passed=True,
                explanation="cosine " + str(best_cosine_similarity) + " >= " + str(self.min_cosine_similarity),
            )

        return GateDecision(
            passed=False,
            explanation=(
                "term coverage " + str(best_term_coverage) + " < " + str(min_term_coverage)
                + ", cosine " + str(best_cosine_similarity)
            ),
        )

    @staticmethod
    def _find_best_term_coverage(hits: List[RetrievalHit]) -> float:
        best_term_coverage = 0.0
        for hit in hits:
            if hit.term_coverage > best_term_coverage:
                best_term_coverage = hit.term_coverage
        return best_term_coverage

    @staticmethod
    def _find_best_cosine_similarity(hits: List[RetrievalHit]) -> Optional[float]:
        best_cosine_similarity: Optional[float] = None
        for hit in hits:
            if hit.cosine_similarity is None:
                continue
            if best_cosine_similarity is None or hit.cosine_similarity > best_cosine_similarity:
                best_cosine_similarity = hit.cosine_similarity
        return best_cosine_similarity
