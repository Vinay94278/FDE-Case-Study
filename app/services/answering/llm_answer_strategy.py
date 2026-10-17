"""LLM answering strategy: three layers of defence against made-up answers.

    Layer 1  RelevanceGate       cheap pre-filter, skips the LLM for obvious misses
    Layer 2  LLM judgement       answered / partial / not_covered, with sentence citations
    Layer 3  GroundingVerifier   code checks the citations and numbers are real

Fail-safe rule: if the LLM is unreachable after retries, the service refuses with
"I can't verify an answer right now". It never falls back to guessing.
"""
import asyncio
import logging
import re
from typing import Any, Dict, List

from app.core.constants import LLM_UNAVAILABLE_MESSAGE, NOT_COVERED_MESSAGE
from app.core.exceptions import LlmAuthenticationException, LlmException
from app.core.settings import Settings
from app.llm.base_llm_client import BaseLlmClient
from app.llm.prompt_loader import ANSWER_PROMPT_NAME
from app.models.answer_models import Answer, AnswerMode, AnswerStatus, AnswerType
from app.models.corpus_models import Sentence
from app.models.query_models import Query, RetrievalHit
from app.retrieval.hybrid_retriever import HybridRetriever
from app.services.answering.answer_strategy import (
    AnswerStrategy,
    build_refusal_answer,
    build_retrieval_debug,
)
from app.services.guards.grounding_verifier import GroundingVerifier
from app.services.guards.relevance_gate import RelevanceGate

logger = logging.getLogger(__name__)

CITATION_MARKER_PATTERN = re.compile(r"\s*[\[(]?\bD-\d+\.S\d+\b[\])]?")
ANSWERED_STATUS_TEXT = AnswerStatus.ANSWERED.value
PARTIAL_STATUS_TEXT = AnswerStatus.PARTIAL.value
NOT_COVERED_STATUS_TEXT = AnswerStatus.NOT_COVERED.value


class LlmAnswerStrategy(AnswerStrategy):
    def __init__(self, retriever: HybridRetriever, relevance_gate: RelevanceGate,
                 grounding_verifier: GroundingVerifier, llm_client: BaseLlmClient,
                 settings: Settings, system_prompt: str):
        self.retriever = retriever
        self.relevance_gate = relevance_gate
        self.grounding_verifier = grounding_verifier
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.top_k = settings.top_k
        self.min_term_coverage = settings.min_term_coverage_llm
        self.retry_attempts = settings.llm_retry_attempts
        self.retry_backoff_seconds = settings.llm_retry_backoff_seconds

    def get_mode(self) -> AnswerMode:
        return AnswerMode.LLM

    async def generate_answer(self, query: Query) -> Answer:
        # Search is CPU-bound (embeddings), so it runs in a worker thread.
        retrieval_result = await asyncio.to_thread(self.retriever.search, query.search_text, self.top_k)
        hits = retrieval_result.hits
        debug_details = build_retrieval_debug(retrieval_result)

        # ---- Layer 1: relevance pre-filter
        gate_decision = self.relevance_gate.evaluate(hits, self.min_term_coverage, allow_cosine_pass=True)
        debug_details["relevance_gate"] = gate_decision.explanation
        if not gate_decision.passed:
            logger.info("Layer 1 refused the question: %s", gate_decision.explanation)
            return build_refusal_answer(AnswerMode.LLM, "relevance_gate_failed", hits, NOT_COVERED_MESSAGE, debug_details)

        context_sentences = self._collect_context_sentences(hits)
        context_sentences_by_id: Dict[str, Sentence] = {}
        for sentence in context_sentences:
            context_sentences_by_id[sentence.sentence_id] = sentence
        user_prompt = self._build_user_prompt(query.standalone_question, context_sentences)
        debug_details["prompt_version"] = ANSWER_PROMPT_NAME

        # ---- Layer 2: LLM judgement (with retry and a fail-safe refusal)
        try:
            llm_reply = await self._call_llm_with_retry(user_prompt)
        except LlmException as error:
            logger.error("LLM unavailable (%s); returning a safe refusal", error.error_code)
            debug_details["llm_error"] = error.technical_message
            return build_refusal_answer(
                AnswerMode.LLM_UNAVAILABLE,
                "llm_unavailable:" + error.error_code,
                hits,
                LLM_UNAVAILABLE_MESSAGE,
                debug_details,
            )
        debug_details["llm_reply"] = llm_reply

        # ---- Layer 3: grounding verification
        return self._build_answer_from_reply(llm_reply, context_sentences_by_id, hits, debug_details)

    # ------------------------------------------------------------------ LLM call

    async def _call_llm_with_retry(self, user_prompt: str) -> Dict[str, Any]:
        total_attempts = 1 + self.retry_attempts
        last_error = None
        for attempt_number in range(1, total_attempts + 1):
            try:
                return await self.llm_client.complete_json(self.system_prompt, user_prompt)
            except LlmAuthenticationException:
                # A wrong key will not fix itself; retrying only adds latency.
                raise
            except LlmException as error:
                last_error = error
                logger.warning(
                    "LLM attempt %d of %d failed: %s",
                    attempt_number,
                    total_attempts,
                    error.error_code,
                )
                if attempt_number < total_attempts:
                    await asyncio.sleep(self.retry_backoff_seconds * attempt_number)
        raise last_error

    # ------------------------------------------------------------------ prompt building

    @staticmethod
    def _collect_context_sentences(hits: List[RetrievalHit]) -> List[Sentence]:
        """Unique sentences from the retrieved chunks, grouped by article in relevance order."""
        article_order: List[str] = []
        sentences_by_id: Dict[str, Sentence] = {}
        for hit in hits:
            if hit.chunk.doc_id not in article_order:
                article_order.append(hit.chunk.doc_id)
            for sentence in hit.chunk.sentences:
                sentences_by_id[sentence.sentence_id] = sentence

        def read_sort_key(sentence: Sentence):
            article_rank = article_order.index(sentence.doc_id)
            return (article_rank, sentence.position)

        return sorted(sentences_by_id.values(), key=read_sort_key)

    @staticmethod
    def _build_user_prompt(question_text: str, context_sentences: List[Sentence]) -> str:
        context_lines = []
        for sentence in context_sentences:
            context_lines.append("[" + sentence.sentence_id + "] (" + sentence.title + ") " + sentence.text)
        return (
            "Documentation sentences:\n" + "\n".join(context_lines) + "\n\n"
            + "<question>\n" + question_text + "\n</question>\n\n"
            + "Return the JSON object now."
        )

    # ------------------------------------------------------------------ reply handling

    def _build_answer_from_reply(self, llm_reply: Dict[str, Any], context_sentences_by_id: Dict[str, Sentence],
                                 hits: List[RetrievalHit], debug_details: Dict[str, Any]) -> Answer:
        status_text = self._read_text_field(llm_reply, "status").lower()
        raw_answer_text = self._read_text_field(llm_reply, "answer")
        answer_text = CITATION_MARKER_PATTERN.sub("", raw_answer_text).strip()
        missing_text = self._read_text_field(llm_reply, "missing")
        cited_sentence_ids = self._normalize_citation_ids(llm_reply.get("citations"))

        if status_text == NOT_COVERED_STATUS_TEXT:
            logger.info("Layer 2: the LLM judged the question not covered")
            return build_refusal_answer(AnswerMode.LLM, "llm_not_covered", hits, NOT_COVERED_MESSAGE, debug_details)

        if status_text != ANSWERED_STATUS_TEXT and status_text != PARTIAL_STATUS_TEXT:
            logger.warning("Layer 2: the LLM returned an unknown status '%s'", status_text)
            reported_status = status_text
            if reported_status == "":
                reported_status = "missing"
            return build_refusal_answer(
                AnswerMode.LLM,
                "invalid_llm_status:" + reported_status,
                hits,
                NOT_COVERED_MESSAGE,
                debug_details,
            )

        verification = self.grounding_verifier.verify(answer_text, cited_sentence_ids, context_sentences_by_id)
        if not verification.passed:
            logger.warning("Layer 3 rejected the LLM draft: %s", verification.failure_reason)
            debug_details["grounding_check"] = "failed: " + str(verification.failure_reason)
            return build_refusal_answer(
                AnswerMode.LLM,
                "grounding_check_failed:" + str(verification.failure_reason),
                hits,
                NOT_COVERED_MESSAGE,
                debug_details,
            )
        debug_details["grounding_check"] = "passed"

        cited_sentences = []
        for sentence_id in cited_sentence_ids:
            cited_sentences.append(context_sentences_by_id[sentence_id])

        answer_status = AnswerStatus.ANSWERED
        missing_information = None
        if status_text == PARTIAL_STATUS_TEXT:
            answer_status = AnswerStatus.PARTIAL
            if missing_text != "":
                missing_information = missing_text

        return Answer(
            status=answer_status,
            answer_type=AnswerType.GENERATED_ANSWER,
            mode=AnswerMode.LLM,
            text=answer_text,
            decision_reason="llm_grounded_answer",
            cited_sentences=cited_sentences,
            missing_information=missing_information,
            debug_details=debug_details,
        )

    @staticmethod
    def _read_text_field(llm_reply: Dict[str, Any], field_name: str) -> str:
        """Read a field as trimmed text; missing or null values become an empty string."""
        field_value = llm_reply.get(field_name)
        if field_value is None:
            return ""
        return str(field_value).strip()

    @staticmethod
    def _normalize_citation_ids(raw_citations: Any) -> List[str]:
        """Accept a list of IDs, strip brackets and spaces, drop duplicates, keep order."""
        normalized_ids: List[str] = []
        if not isinstance(raw_citations, list):
            return normalized_ids
        for raw_citation in raw_citations:
            if not isinstance(raw_citation, (str, int)):
                continue
            cleaned_id = str(raw_citation).strip().strip("[]()")
            if cleaned_id != "" and cleaned_id not in normalized_ids:
                normalized_ids.append(cleaned_id)
        return normalized_ids
