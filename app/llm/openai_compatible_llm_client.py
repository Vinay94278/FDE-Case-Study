"""Client for any OpenAI-style chat API: Azure OpenAI, OpenAI, vLLM, Ollama, gateways."""
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


class OpenAiCompatibleLlmClient(BaseLlmClient):
    def __init__(self, provider_name: str, sdk_client: Any, model_name: str, max_output_tokens: int):
        self.provider_name = provider_name
        self.sdk_client = sdk_client
        self.model_name = model_name
        self.max_output_tokens = max_output_tokens

    def get_display_name(self) -> str:
        return self.provider_name + ":" + self.model_name

    def get_provider_name(self) -> str:
        return self.provider_name

    def get_model_name(self) -> str:
        return self.model_name

    async def complete_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        import openai

        request_arguments = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": self.max_output_tokens,
        }

        try:
            try:
                completion = await self.sdk_client.chat.completions.create(
                    response_format={"type": "json_object"},
                    **request_arguments,
                )
            except openai.BadRequestError as json_mode_error:
                logger.warning("Provider rejected JSON mode, retrying without it: %s", json_mode_error)
                completion = await self.sdk_client.chat.completions.create(**request_arguments)
        except openai.APITimeoutError as error:
            raise LlmTimeoutException(technical_message="LLM timeout: " + str(error)) from error
        except openai.RateLimitError as error:
            raise LlmRateLimitException(technical_message="LLM rate limit: " + str(error)) from error
        except openai.AuthenticationError as error:
            raise LlmAuthenticationException(technical_message="LLM authentication failed: " + str(error)) from error
        except openai.APIError as error:
            raise LlmException(technical_message="LLM API error: " + type(error).__name__ + ": " + str(error)) from error

        reply_text = completion.choices[0].message.content
        return parse_json_object(reply_text)

    async def close(self) -> None:
        await self.sdk_client.close()
