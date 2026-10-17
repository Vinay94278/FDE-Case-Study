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
