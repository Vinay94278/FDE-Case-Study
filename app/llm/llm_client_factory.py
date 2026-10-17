"""Builds the configured LLM client. Switching provider is a config change only.

    LLM_PROVIDER=groq               Groq (demo)
    LLM_PROVIDER=azure              Azure OpenAI in the client's own tenant (production)
    LLM_PROVIDER=openai_compatible  Any OpenAI-style endpoint (OpenAI, vLLM, Ollama, gateways)
    LLM_PROVIDER=none               No LLM: extractive mode
"""
import logging
from typing import Optional

from app.core.component_registry import ComponentRegistry
from app.core.exceptions import ConfigurationException
from app.core.settings import Settings, describe_api_key_source, mask_secret
from app.llm.base_llm_client import BaseLlmClient

logger = logging.getLogger(__name__)

LLM_CLIENT_REGISTRY = ComponentRegistry("LLM provider")


@LLM_CLIENT_REGISTRY.register("groq")
def build_groq_client(settings: Settings) -> BaseLlmClient:
    try:
        from app.llm.groq_llm_client import GroqLlmClient
    except ImportError as error:
        raise ConfigurationException(technical_message="Install the 'groq' package to use LLM_PROVIDER=groq") from error
    return GroqLlmClient(
        api_key=settings.llm_api_key,
        model_name=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_tokens,
    )


@LLM_CLIENT_REGISTRY.register("openai_compatible")
def build_openai_compatible_client(settings: Settings) -> BaseLlmClient:
    import openai

    from app.llm.openai_compatible_llm_client import OpenAiCompatibleLlmClient

    base_url: Optional[str] = None
    if settings.llm_base_url.strip() != "":
        base_url = settings.llm_base_url
    sdk_client = openai.AsyncOpenAI(
        base_url=base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
    )
    return OpenAiCompatibleLlmClient("openai_compatible", sdk_client, settings.llm_model, settings.llm_max_tokens)


@LLM_CLIENT_REGISTRY.register("azure")
def build_azure_openai_client(settings: Settings) -> BaseLlmClient:
    import openai

    from app.llm.openai_compatible_llm_client import OpenAiCompatibleLlmClient

    if settings.llm_base_url.strip() == "":
        raise ConfigurationException(technical_message="LLM_BASE_URL must be the Azure OpenAI endpoint for LLM_PROVIDER=azure")
    sdk_client = openai.AsyncAzureOpenAI(
        azure_endpoint=settings.llm_base_url,
        api_key=settings.llm_api_key,
        api_version=settings.azure_api_version,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
    )
    return OpenAiCompatibleLlmClient("azure", sdk_client, settings.llm_model, settings.llm_max_tokens)


def create_llm_client(settings: Settings) -> Optional[BaseLlmClient]:
    """Return the configured client, or None when the service should run in extractive mode."""
    provider_name = settings.llm_provider.strip().lower()
    if provider_name == "none":
        logger.info("LLM_PROVIDER=none: running in extractive mode")
        return None
    if settings.llm_api_key.strip() == "":
        logger.warning("LLM_PROVIDER=%s but no API key is set: running in extractive mode", provider_name)
        return None

    logger.info(
        "LLM key %s loaded from %s",
        mask_secret(settings.llm_api_key),
        describe_api_key_source(),
    )
    return LLM_CLIENT_REGISTRY.create(provider_name, settings)
