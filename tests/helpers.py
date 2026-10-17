"""Shared test helpers. Tests never read the local .env and never call a real LLM."""
import asyncio
from typing import Any, Dict, List, Optional

from app.core.application_container import ApplicationContainer
from app.core.settings import Settings
from app.dto.ask_dto import AskRequestDTO, AskResponseDTO, ConversationTurnDTO
from app.llm.base_llm_client import BaseLlmClient


def build_test_settings(**setting_overrides: Any) -> Settings:
    test_values = {
        "llm_provider": "none",
        "embeddings_enabled": False,
        "query_log_store": "none",
        "log_level": "WARNING",
    }
    test_values.update(setting_overrides)
    return Settings(_env_file=None, **test_values)


class FakeLlmClient(BaseLlmClient):
    """Returns scripted replies in order. An Exception in the script is raised instead."""

    def __init__(self, scripted_replies: List[Any]):
        self.scripted_replies = list(scripted_replies)
        self.call_count = 0
        self.received_user_prompts: List[str] = []

    def get_display_name(self) -> str:
        return "fake:test-model"

    def get_provider_name(self) -> str:
        return "fake"

    def get_model_name(self) -> str:
        return "test-model"

    async def complete_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        self.call_count = self.call_count + 1
        self.received_user_prompts.append(user_prompt)
        if len(self.scripted_replies) == 0:
            raise AssertionError("FakeLlmClient called more times than scripted")
        next_reply = self.scripted_replies.pop(0)
        if isinstance(next_reply, Exception):
            raise next_reply
        return next_reply


def build_container(settings: Settings, llm_client: Optional[BaseLlmClient] = None) -> ApplicationContainer:
    return asyncio.run(ApplicationContainer.create(settings, llm_client))


def ask_question(container: ApplicationContainer, question_text: str,
                 history: Optional[List[Dict[str, str]]] = None) -> AskResponseDTO:
    history_dtos = []
    if history is not None:
        for turn in history:
            history_dtos.append(ConversationTurnDTO(question=turn["question"], answer=turn["answer"]))
    request_dto = AskRequestDTO(question=question_text, conversation_history=history_dtos, include_debug=True)
    return asyncio.run(container.question_answering_service.answer_question(request_dto))
