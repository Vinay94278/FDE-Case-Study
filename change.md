# Change Summary

This document captures the small, compatibility-focused changes made to keep the project working while preserving the original code structure and implementation style.

## 1) Python compatibility fix

### What changed

- Replaced the newer union syntax `str | None` with `Optional[...]` in the affected model and QA code.
- Kept the original project structure and conventions intact rather than rewriting the app architecture.

### Why

The runtime was failing at import time because the project used Python 3.10-style annotation syntax where the execution environment was not accepting it as expected. This caused the app to crash before it could start.

### Files updated

- `app/models.py`
- `app/qa.py`
- `app/retrieval.py`
- `app/config.py`

---

## 2) Environment variable handling and .env precedence

### What changed

- Ensured the app loads the local `.env` file first and treats it as the source of truth.
- Added explicit `.env` precedence over exported shell variables.
- Kept the existing settings pattern based on `load_settings()` and the same config object shape.

### Why

The app was occasionally reading stale exported environment variables instead of the project’s secret file, which caused confusing Groq authentication failures. This change makes the app behave predictably and keeps secrets in the project-local config model as intended.

### Files updated

- `app/config.py`

---

## 3) Groq client alignment with the official demo pattern

### What changed

- Added a Groq-specific LLM path that uses the `groq` SDK directly.
- Kept the earlier OpenAI-compatible provider support for other providers such as Azure or generic OpenAI-compatible endpoints.
- Preserved the existing application-level interface (`complete_json`) so the rest of the app logic does not change.

### Why

The project was reaching Groq through a generic OpenAI-compatible client, while the Groq demo pattern uses the official `Groq` SDK and request format. This mismatch could lead to request/auth issues. The update aligns the app with the provider’s expected usage while keeping the original design intact.

### Files updated

- `app/llm.py`

---

## 4) Minimal, style-preserving implementation approach

Each change was kept intentionally small and close to the original code style:

- no large refactor
- no rewrite of the API contract
- no change to the QA pipeline behavior beyond compatibility and auth correctness
- no major redesign of the settings model

The goal was to preserve the original architecture while fixing compatibility and authentication issues.

---

## Verification

After the fixes, the project was verified with the project test suite:

- `pytest -q` → `18 passed`

This confirms the app remains stable and the updates did not break the expected behavior.

---

# v2.0.0

## Behaviour fixes

- **Fail-safe LLM handling.** One retry, then a safe refusal ("I can't verify an answer right now") with related articles. The v1 fallback to extractive mode could answer a question it shouldn't (E-12 in the v1 LLM run).
- **Groq JSON mode restored** in the Groq client, with a retry without JSON mode if the model rejects it.
- **Settings precedence** now follows the standard order: real environment variables, then `.env`, then defaults (needed for Docker/Railway and isolated tests). The stale-key problem from v1.1 is handled by logging where the key came from, masked, at startup.

## Extractive mode v2

Glossary synonyms (`data/glossary.json`), multi-part question splitting, rare-word and embedding sentence ranking, entity check for partial coverage, and a "verbatim passage" label in the UI. Dev set 17/25 -> 24/25; held-out test set 9/13.

## New features

- Follow-up questions (stateless, capped history, "Searched for" shown in the UI).
- Evaluation: mode column, `--runs`, dev/test split with 13 held-out questions, 4 follow-up cases.

## Structure and engineering

- Layered architecture: DTOs, controllers, services, mappers, DAOs, domain models.
- One response envelope for every endpoint; centralized exception handling with error codes.
- Pluggable registries for LLM provider, document source and query log store.
- Request IDs on every log line and response; text or JSON logs.
- Async endpoints and LLM clients; blocking work in worker threads.
- Prompts in versioned files.
- Docker image and docker-compose.
- 52 tests (unit + integration), passing on Python 3.9 and 3.12.
