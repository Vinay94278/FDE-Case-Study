"""Groq provider client, using the official async Groq SDK."""
import logging
from typing import Any, Dict

from app.core.exceptions import (
    LlmAuthenticationException,
    LlmException,
    LlmRateLimitException,
    LlmTimeoutException,
)
from app.llm.base_llm_client import BaseLlmClient
from app.llm.json_response_parser import parse_json_object

logger = logging.getLogger(__name__)

PROVIDER_NAME = "groq"


class GroqLlmClient(BaseLlmClient):
    def __init__(self, api_key: str, model_name: str, timeout_seconds: float, max_output_tokens: int):
        from groq import AsyncGroq

        self.model_name = model_name
        self.max_output_tokens = max_output_tokens
        # Retries are handled by the answering strategy, so the SDK does not retry on its own.
        self.sdk_client = AsyncGroq(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    def get_display_name(self) -> str:
        return PROVIDER_NAME + ":" + self.model_name

    def get_provider_name(self) -> str:
        return PROVIDER_NAME

    def get_model_name(self) -> str:
        return self.model_name

    async def complete_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        import groq

        request_arguments = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_completion_tokens": self.max_output_tokens,
        }

        try:
            try:
                completion = await self.sdk_client.chat.completions.create(
                    response_format={"type": "json_object"},
                    **request_arguments,
                )
            except groq.BadRequestError as json_mode_error:
                # JSON mode is rejected by some models, or fails when the model's output
                # is not valid JSON. The prompt still asks for JSON, so retry without it.
                logger.warning("Groq rejected JSON mode, retrying without it: %s", json_mode_error)
                completion = await self.sdk_client.chat.completions.create(**request_arguments)
        except groq.APITimeoutError as error:
            raise LlmTimeoutException(technical_message="Groq timeout: " + str(error)) from error
        except groq.RateLimitError as error:
            raise LlmRateLimitException(technical_message="Groq rate limit: " + str(error)) from error
        except groq.AuthenticationError as error:
            raise LlmAuthenticationException(technical_message="Groq authentication failed: " + str(error)) from error
        except groq.APIError as error:
            raise LlmException(technical_message="Groq API error: " + type(error).__name__ + ": " + str(error)) from error

        reply_text = completion.choices[0].message.content
        return parse_json_object(reply_text)

    async def close(self) -> None:
        await self.sdk_client.close()
