"""Runtime settings, read from environment variables (and a local .env file)."""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values, load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
_DOTENV = dotenv_values(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env", override=True)


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value in (None, "") else float(value)


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in (None, "") else int(value)


def _env(name: str, default: str = "", fallback_name: Optional[str] = None) -> str:
    value = _DOTENV.get(name)
    if value is not None and value.strip() != "":
        return value.strip()
    if fallback_name:
        fallback = _DOTENV.get(fallback_name)
        if fallback is not None and fallback.strip() != "":
            return fallback.strip()
    value = os.getenv(name)
    if value is not None and value.strip() != "":
        return value.strip()
    if fallback_name:
        fallback = os.getenv(fallback_name)
        if fallback is not None and fallback.strip() != "":
            return fallback.strip()
    return default


@dataclass(frozen=True)
class Settings:
    docs_path: Path
    log_path: Path

    # LLM: "groq" | "openai_compatible" | "azure" | "none"
    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_s: float
    llm_max_tokens: int
    azure_api_version: str

    # Retrieval
    chunk_max_chars: int
    chunk_overlap_sentences: int
    top_k: int
    embeddings_enabled: bool
    embedding_model: str

    # Gate 1 (cheap pre-filter before the LLM is called)
    min_term_coverage_llm: float
    min_term_coverage_extractive: float
    min_cosine: float


def load_settings() -> Settings:
    provider = _env("LLM_PROVIDER", "groq").strip().lower()
    default_url = "https://api.groq.com/openai/v1" if provider == "groq" else ""
    return Settings(
        docs_path=Path(_env("DOCS_PATH", str(BASE_DIR / "data" / "docs.json"))),
        log_path=Path(_env("LOG_PATH", str(BASE_DIR / "logs" / "queries.jsonl"))),
        llm_provider=provider,
        llm_base_url=_env("LLM_BASE_URL", default_url),
        llm_api_key=_env("LLM_API_KEY", "", "GROQ_API_KEY"),
        llm_model=_env("LLM_MODEL", "openai/gpt-oss-120b"),
        llm_timeout_s=_float("LLM_TIMEOUT_S", 20.0),
        llm_max_tokens=_int("LLM_MAX_TOKENS", 1500),
        azure_api_version=_env("AZURE_API_VERSION", "2024-10-21"),
        chunk_max_chars=_int("CHUNK_MAX_CHARS", 400),
        chunk_overlap_sentences=_int("CHUNK_OVERLAP_SENTENCES", 1),
        top_k=_int("TOP_K", 4),
        embeddings_enabled=_bool("EMBEDDINGS_ENABLED", True),
        embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        min_term_coverage_llm=_float("MIN_TERM_COVERAGE_LLM", 0.2),
        min_term_coverage_extractive=_float("MIN_TERM_COVERAGE_EXTRACTIVE", 0.6),
        min_cosine=_float("MIN_COSINE", 0.35),
    )
