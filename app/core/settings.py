"""Application settings.

Values are read in this order (highest priority first):
    1. Arguments passed to Settings(...) directly (used by tests).
    2. Real environment variables (used by Docker, Railway, CI).
    3. The local .env file (used for local development).
    4. The defaults written below.

This is the standard "12-factor" order: a deployment platform must be able to
override a value without editing files inside the image.
"""
import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT_DIRECTORY = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """All runtime configuration for the service, validated at startup."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT_DIRECTORY / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    # ------------------------------------------------------------------ application
    app_name: str = "Solstice Docs Q&A"
    app_version: str = "2.0.0"
    app_env: str = "local"
    expose_technical_messages: bool = True

    # ------------------------------------------------------------------ logging
    log_level: str = "INFO"
    log_format: str = "text"

    # ------------------------------------------------------------------ pluggable components
    document_source: str = "json"
    query_log_store: str = "jsonl"

    # ------------------------------------------------------------------ data paths
    docs_path: Path = PROJECT_ROOT_DIRECTORY / "data" / "docs.json"
    glossary_path: Path = PROJECT_ROOT_DIRECTORY / "data" / "glossary.json"
    query_log_path: Path = Field(
        default=PROJECT_ROOT_DIRECTORY / "logs" / "queries.jsonl",
        validation_alias=AliasChoices("QUERY_LOG_PATH", "LOG_PATH"),
    )

    # ------------------------------------------------------------------ LLM
    llm_provider: str = "groq"
    llm_base_url: str = ""
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "GROQ_API_KEY"),
    )
    llm_model: str = "openai/gpt-oss-120b"
    llm_timeout_seconds: float = 20.0
    llm_max_tokens: int = 1500
    llm_retry_attempts: int = 1
    llm_retry_backoff_seconds: float = 0.5
    azure_api_version: str = "2024-10-21"

    # ------------------------------------------------------------------ retrieval
    chunk_max_chars: int = 400
    chunk_overlap_sentences: int = 1
    top_k: int = 4
    embeddings_enabled: bool = True
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ------------------------------------------------------------------ relevance gate thresholds
    min_term_coverage_llm: float = 0.2
    min_term_coverage_extractive: float = 0.6
    min_cosine: float = 0.35

    # ------------------------------------------------------------------ follow-up questions
    followup_max_turns: int = 3
    followup_max_answer_chars: int = 300

    def is_llm_enabled(self) -> bool:
        """True when an LLM provider is configured and an API key is present."""
        if self.llm_provider.strip().lower() == "none":
            return False
        if self.llm_api_key.strip() == "":
            return False
        return True


def describe_api_key_source() -> str:
    """Explain where the LLM key came from, without revealing it.

    An exported shell variable silently overrides .env. Logging the source at
    startup makes a stale exported key easy to spot when authentication fails.
    """
    for variable_name in ("LLM_API_KEY", "GROQ_API_KEY"):
        if os.environ.get(variable_name):
            return "environment variable " + variable_name
    return ".env file or default"


def mask_secret(secret_value: str) -> str:
    """Show only the last four characters of a secret."""
    if len(secret_value) <= 4:
        return "****"
    return "****" + secret_value[-4:]
