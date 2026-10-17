"""Follow-up questions: rewrite "And for Enterprise?" into a standalone question.

Design rules:
    - The server is stateless. The UI sends the last few turns with each request,
      so no session store is needed and any instance can answer any request.
    - Earlier answers are only used to understand the question. They are never a
      source of facts: the answer still comes only from the docs, through the same gates.
    - History is capped (turns and characters) to bound cost and prompt-injection surface.
    - If there is no LLM, or the rewrite fails, the question is used as typed.
"""
import json
import logging
from dataclasses import dataclass
from typing import List, Optional

from app.core.constants import MAX_QUESTION_LENGTH
from app.core.exceptions import LlmException
from app.llm.base_llm_client import BaseLlmClient
from app.models.query_models import ConversationTurn, Query

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RewriteResult:
    standalone_question: str
    was_rewritten: bool
    note: str


class FollowUpRewriter:
    def __init__(self, llm_client: Optional[BaseLlmClient], system_prompt: str, max_answer_chars: int):
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.max_answer_chars = max_answer_chars

    async def resolve_standalone_question(self, query: Query) -> RewriteResult:
        original_question = query.original_question

        if len(query.conversation_history) == 0:
            return RewriteResult(original_question, False, "no_history")

        if self.llm_client is None:
            return RewriteResult(original_question, False, "no_llm_question_used_as_typed")

        user_prompt = self._build_user_prompt(query.conversation_history, original_question)
        try:
            llm_reply = await self.llm_client.complete_json(self.system_prompt, user_prompt)
        except LlmException as error:
            logger.warning("Follow-up rewrite failed (%s); using the question as typed", error.error_code)
            return RewriteResult(original_question, False, "rewrite_failed")

        candidate_question = llm_reply.get("standalone_question")
        if not isinstance(candidate_question, str):
            return RewriteResult(original_question, False, "rewrite_invalid")

        cleaned_question = " ".join(candidate_question.split())
        if len(cleaned_question) < 3 or len(cleaned_question) > MAX_QUESTION_LENGTH:
            return RewriteResult(original_question, False, "rewrite_invalid")

        was_rewritten = cleaned_question.lower() != original_question.lower()
        logger.info("Follow-up resolved (rewritten=%s)", was_rewritten)
        return RewriteResult(cleaned_question, was_rewritten, "rewritten")

    def _build_user_prompt(self, conversation_history: List[ConversationTurn], latest_question: str) -> str:
        turns_for_prompt = []
        for turn in conversation_history:
            shortened_answer = turn.answer[:self.max_answer_chars]
            turns_for_prompt.append({"question": turn.question, "answer": shortened_answer})
        return (
            "<conversation>\n" + json.dumps(turns_for_prompt, indent=2) + "\n</conversation>\n\n"
            + "<latest_message>\n" + latest_question + "\n</latest_message>\n\n"
            + "Return the JSON object now."
        )
