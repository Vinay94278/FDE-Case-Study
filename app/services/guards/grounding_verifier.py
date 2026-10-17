"""Layer 3: grounding verification, in plain code (no LLM involved).

Checks an LLM draft before it is shown:
    - the answer is not empty
    - it cites at least one sentence
    - every cited sentence was actually given to the LLM
    - every number in the answer appears in the cited sentences ("24 hours" when the
      docs say "15 minutes" is rejected)

Deterministic, cheap and auditable: the same draft always gets the same verdict.
"""
from typing import Dict, List, Set

from app.models.corpus_models import Sentence
from app.models.guard_models import VerificationResult
from app.retrieval.text_processing import extract_numbers


class GroundingVerifier:
    def verify(self, answer_text: str, cited_sentence_ids: List[str],
               context_sentences_by_id: Dict[str, Sentence]) -> VerificationResult:
        if answer_text.strip() == "":
            return VerificationResult(passed=False, failure_reason="empty_answer")

        if len(cited_sentence_ids) == 0:
            return VerificationResult(passed=False, failure_reason="no_citations")

        unknown_sentence_ids = []
        for sentence_id in cited_sentence_ids:
            if sentence_id not in context_sentences_by_id:
                unknown_sentence_ids.append(sentence_id)
        if len(unknown_sentence_ids) > 0:
            return VerificationResult(
                passed=False,
                failure_reason="citation_not_in_context:" + ",".join(unknown_sentence_ids[:3]),
            )

        cited_text_parts = []
        for sentence_id in cited_sentence_ids:
            cited_text_parts.append(context_sentences_by_id[sentence_id].text)
        cited_text = " ".join(cited_text_parts)

        numbers_in_answer: Set[str] = extract_numbers(answer_text)
        numbers_in_citations: Set[str] = extract_numbers(cited_text)
        unsupported_numbers = sorted(numbers_in_answer - numbers_in_citations)
        if len(unsupported_numbers) > 0:
            return VerificationResult(
                passed=False,
                failure_reason="numbers_not_in_cited_text:" + ",".join(unsupported_numbers),
            )

        return VerificationResult(passed=True)
