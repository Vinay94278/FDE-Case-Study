"""LLM provider layer.

Groq, Azure OpenAI, OpenAI, vLLM, Ollama and many gateways speak the same
OpenAI-style chat API, so one small client covers them. Switching provider is a
config change (LLM_PROVIDER / LLM_BASE_URL / LLM_MODEL), not a code change.

The rest of the app only depends on `complete_json(system, user) -> dict`.
"""
import json
import logging
import re

from .config import Settings

log = logging.getLogger(__name__)


class LLMError(Exception):
    """Any provider failure: network, timeout, auth, rate limit, bad JSON."""


def parse_json_object(content: str) -> dict:
    text = (content or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError("LLM did not return a JSON object")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("LLM JSON is not an object")
    return data


class OpenAICompatibleLLM:
    def __init__(self, client, model: str, max_tokens: int, name: str):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.name = name

    def complete_json(self, system: str, user: str) -> dict:
        import openai

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        kwargs = dict(model=self.model, messages=messages, temperature=0, max_tokens=self.max_tokens)
        try:
            try:
                resp = self.client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
            except openai.BadRequestError:
                # Some models/providers reject JSON mode; the prompt still asks for JSON.
                resp = self.client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc
        return parse_json_object(content)


class GroqLLM:
    def __init__(self, client, model: str, max_tokens: int, name: str):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.name = name

    def complete_json(self, system: str, user: str) -> dict:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=0,
            max_completion_tokens=self.max_tokens,
            top_p=1,
            stream=False,
            stop=None,
        )
        try:
            resp = self.client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
        except Exception as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc
        return parse_json_object(content)


def build_llm(settings: Settings):
    """Return an LLM client, or None for extractive-only mode."""
    provider = settings.llm_provider
    if provider == "none":
        return None
    if not settings.llm_api_key:
        log.warning("LLM_PROVIDER=%s but no API key set; running in extractive mode.", provider)
        return None
    try:
        import openai
    except ImportError:
        log.warning("openai package not installed; running in extractive mode.")
        return None

    if provider == "azure":
        client = openai.AzureOpenAI(
            azure_endpoint=settings.llm_base_url,
            api_key=settings.llm_api_key,
            api_version=settings.azure_api_version,
            timeout=settings.llm_timeout_s,
            max_retries=1,
        )
        return OpenAICompatibleLLM(client, settings.llm_model, settings.llm_max_tokens, f"{provider}:{settings.llm_model}")

    if provider == "groq":
        try:
            from groq import Groq
        except ImportError as exc:
            raise ImportError("groq package is required for LLM_PROVIDER=groq") from exc
        client = Groq(api_key=settings.llm_api_key, timeout=settings.llm_timeout_s, max_retries=1)
        return GroqLLM(client, settings.llm_model, settings.llm_max_tokens, f"{provider}:{settings.llm_model}")

    if provider == "openai_compatible":
        client = openai.OpenAI(
            base_url=settings.llm_base_url or None,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_s,
            max_retries=1,
        )
        return OpenAICompatibleLLM(client, settings.llm_model, settings.llm_max_tokens, f"{provider}:{settings.llm_model}")

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
