"""The contract every LLM provider client implements.

The rest of the application depends only on this interface, never on a vendor SDK.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseLlmClient(ABC):
    @abstractmethod
    def get_display_name(self) -> str:
        """Provider and model, for example "groq:openai/gpt-oss-120b"."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Provider only, for example "groq"."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Model only."""

    @abstractmethod
    async def complete_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Send one chat request and return the reply parsed as a JSON object.

        Raises an LlmException subclass on any failure (timeout, rate limit,
        authentication, provider error, or a reply that is not a JSON object).
        """

    async def close(self) -> None:
        """Release network resources. Called once at shutdown."""
        return None
