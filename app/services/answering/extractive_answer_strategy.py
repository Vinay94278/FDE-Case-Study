"""Extractive answering strategy: no LLM, the answer is the best doc sentences, verbatim.

Nothing is generated, so no fact can be invented. The risks are choosing the wrong
sentence or treating a partly covered question as fully answered. v2 reduces both:

    1. Glossary synonyms (applied before this strategy): "add a user" -> "invite".
    2. Multi-part questions are split and each part answered separately.
    3. Sentences are ranked by informative word overlap (rare words count more),
       plus embedding similarity when embeddings are installed.
    4. Entity check: if the question names a plan, format or integration that the
       chosen passage never mentions, the result is "partial", not "answered".
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.constants import MAX_EXTRACTIVE_SENTENCES, NOT_COVERED_MESSAGE
from app.core.settings import Settings
from app.models.answer_models import Answer, AnswerMode, AnswerStatus, AnswerType, RelatedDocument
from app.models.corpus_models import Chunk, Sentence
from app.models.query_models import Query, RetrievalHit
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.text_processing import extract_unique_search_terms
from app.services.answering.answer_strategy import (
    AnswerStrategy,
    build_refusal_answer,
    build_related_documents,
    build_retrieval_debug,
)
from app.services.guards.entity_coverage_checker import EntityCoverageChecker
from app.services.guards.relevance_gate import RelevanceGate
from app.utils.question_splitter import split_question_into_parts

logger = logging.getLogger(__name__)

# How much embedding similarity adds to a sentence's word-overlap score.
SIMILARITY_WEIGHT = 1.0


@dataclass
class ScoredSentence:
    sentence: Sentence
    word_overlap_score: float
    similarity_score: float

    def get_total_score(self) -> float:
        return self.word_overlap_score + SIMILARITY_WEIGHT * self.similarity_score


@dataclass
class PartResult:
    """The outcome for one part of a (possibly multi-part) question."""

    question_part: str
    status: AnswerStatus
    chosen_sentences: List[Sentence] = field(default_factory=list)
    missing_entities: List[str] = field(default_factory=list)
    hits: List[RetrievalHit] = field(default_factory=list)
    debug_details: Dict[str, Any] = field(default_factory=dict)


class ExtractiveAnswerStrategy(AnswerStrategy):
    def __init__(self, retriever: HybridRetriever, relevance_gate: RelevanceGate,
                 entity_checker: EntityCoverageChecker, settings: Settings):
        self.retriever = retriever
        self.relevance_gate = relevance_gate
        self.entity_checker = entity_checker
        self.top_k = settings.top_k
        self.min_term_coverage = settings.min_term_coverage_extractive

    def get_mode(self) -> AnswerMode:
        return AnswerMode.EXTRACTIVE

    async def generate_answer(self, query: Query) -> Answer:
        question_parts = split_question_into_parts(query.search_text)
        part_results: List[PartResult] = []
        for question_part in question_parts:
            part_result = await self._answer_question_part(question_part)
            part_results.append(part_result)
        return self._combine_part_results(part_results)

    # ------------------------------------------------------------------ one question part

    async def _answer_question_part(self, question_part: str) -> PartResult:
        retrieval_result = await asyncio.to_thread(self.retriever.search, question_part, self.top_k)
        hits = retrieval_result.hits
        debug_details = build_retrieval_debug(retrieval_result)

        # Layer 1 is the main guard here, so it is stricter and ignores embedding similarity.
        gate_decision = self.relevance_gate.evaluate(hits, self.min_term_coverage, allow_cosine_pass=False)
        debug_details["relevance_gate"] = gate_decision.explanation
        if not gate_decision.passed:
            return PartResult(
                question_part=question_part,
                status=AnswerStatus.NOT_COVERED,
                hits=hits,
                debug_details=debug_details,
            )

        best_hit = self._find_first_hit_above_threshold(hits)
        ranked_sentences = await asyncio.to_thread(
            self._rank_chunk_sentences,
            question_part,
            best_hit.chunk,
        )
        chosen_sentences = self._choose_sentences(ranked_sentences, best_hit.chunk)

        anchor_sentence = ranked_sentences[0].sentence
        evidence_text = anchor_sentence.text + " " + anchor_sentence.title
        missing_entities = self.entity_checker.find_missing_entities(question_part, evidence_text)
        debug_details["anchor_sentence"] = anchor_sentence.sentence_id
        debug_details["missing_entities"] = missing_entities

        part_status = AnswerStatus.ANSWERED
        if len(missing_entities) > 0:
            part_status = AnswerStatus.PARTIAL

        return PartResult(
            question_part=question_part,
            status=part_status,
            chosen_sentences=chosen_sentences,
            missing_entities=missing_entities,
            hits=hits,
            debug_details=debug_details,
        )

    def _find_first_hit_above_threshold(self, hits: List[RetrievalHit]) -> RetrievalHit:
        for hit in hits:
            if hit.term_coverage >= self.min_term_coverage:
                return hit
        return hits[0]

    def _rank_chunk_sentences(self, question_part: str, chunk: Chunk) -> List[ScoredSentence]:
        """Score each sentence: sum of rare-word weights it shares with the question,
        plus embedding similarity when available."""
        question_terms = set(extract_unique_search_terms(question_part))
        similarity_by_id = self.retriever.compute_sentence_similarities(question_part, chunk.get_sentence_ids())

        scored_sentences = []
        for sentence in chunk.sentences:
            word_overlap_score = 0.0
            for sentence_term in extract_unique_search_terms(sentence.text):
                if sentence_term in question_terms:
                    word_overlap_score = word_overlap_score + self.retriever.get_term_weight(sentence_term)

            similarity_score = 0.0
            if sentence.sentence_id in similarity_by_id:
                similarity_score = similarity_by_id[sentence.sentence_id]

            scored_sentences.append(ScoredSentence(sentence, word_overlap_score, similarity_score))

        def read_ranking_key(scored_sentence: ScoredSentence):
            return (-scored_sentence.get_total_score(), scored_sentence.sentence.position)

        return sorted(scored_sentences, key=read_ranking_key)

    @staticmethod
    def _choose_sentences(ranked_sentences: List[ScoredSentence], chunk: Chunk) -> List[Sentence]:
        """Top sentences that share at least one word with the question, in reading order."""
        chosen_sentences: List[Sentence] = []
        for scored_sentence in ranked_sentences:
            if scored_sentence.word_overlap_score <= 0:
                continue
            chosen_sentences.append(scored_sentence.sentence)
            if len(chosen_sentences) >= MAX_EXTRACTIVE_SENTENCES:
                break

        if len(chosen_sentences) == 0:
            chosen_sentences = list(chunk.sentences[:MAX_EXTRACTIVE_SENTENCES])

        def read_position(sentence: Sentence) -> int:
            return sentence.position

        chosen_sentences.sort(key=read_position)
        return chosen_sentences

    # ------------------------------------------------------------------ combine parts

    def _combine_part_results(self, part_results: List[PartResult]) -> Answer:
        debug_details: Dict[str, Any] = {"question_parts": []}
        all_hits: List[RetrievalHit] = []
        cited_sentences: List[Sentence] = []
        cited_sentence_ids = set()
        missing_descriptions: List[str] = []
        answered_part_count = 0
        covered_part_count = 0

        for part_result in part_results:
            part_debug = dict(part_result.debug_details)
            part_debug["question_part"] = part_result.question_part
            part_debug["status"] = part_result.status.value
            debug_details["question_parts"].append(part_debug)
            all_hits.extend(part_result.hits)

            if part_result.status == AnswerStatus.NOT_COVERED:
                missing_descriptions.append('"' + part_result.question_part + '"')
                continue

            covered_part_count = covered_part_count + 1
            if part_result.status == AnswerStatus.ANSWERED:
                answered_part_count = answered_part_count + 1
            for missing_entity in part_result.missing_entities:
                missing_descriptions.append(missing_entity)
            for sentence in part_result.chosen_sentences:
                if sentence.sentence_id not in cited_sentence_ids:
                    cited_sentence_ids.add(sentence.sentence_id)
                    cited_sentences.append(sentence)

        if covered_part_count == 0:
            return build_refusal_answer(
                AnswerMode.EXTRACTIVE,
                "relevance_gate_failed",
                all_hits,
                NOT_COVERED_MESSAGE,
                debug_details,
            )

        answer_text_parts = []
        for sentence in cited_sentences:
            answer_text_parts.append(sentence.text)

        answer_status = AnswerStatus.ANSWERED
        decision_reason = "extractive_best_sentences"
        missing_information: Optional[str] = None
        if answered_part_count < len(part_results):
            answer_status = AnswerStatus.PARTIAL
            decision_reason = "extractive_partial_coverage"
            missing_information = "The documentation does not mention: " + ", ".join(missing_descriptions)

        return Answer(
            status=answer_status,
            answer_type=AnswerType.VERBATIM_PASSAGE,
            mode=AnswerMode.EXTRACTIVE,
            text=" ".join(answer_text_parts),
            decision_reason=decision_reason,
            cited_sentences=cited_sentences,
            related_documents=self._related_documents_if_partial(answer_status, all_hits),
            missing_information=missing_information,
            debug_details=debug_details,
        )

    @staticmethod
    def _related_documents_if_partial(answer_status: AnswerStatus, hits: List[RetrievalHit]) -> List[RelatedDocument]:
        if answer_status == AnswerStatus.PARTIAL:
            return build_related_documents(hits)
        return []
