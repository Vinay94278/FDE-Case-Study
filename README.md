# Solstice Docs Q&A Assistant

Admins ask a plain-English question and get an answer drawn only from the Solstice documentation, with the exact source sentence shown. If the docs don't cover it, the assistant says so instead of guessing.

Design, assumptions and trade-offs: [SOLUTION_DESIGN.md](SOLUTION_DESIGN.md). Version history: [change.md](change.md).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # add your Groq key
uvicorn app.main:app --reload
```

- UI: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs

No API key? Set `LLM_PROVIDER=none` for extractive mode. Tests and evaluation run fully offline.

Optional semantic search: `pip install -r requirements-embeddings.txt` (large; needs access to huggingface.co). `/api/v1/health` shows whether embeddings are on.

Python 3.9+ is supported (tested on 3.9 and 3.12).

## Docker

```bash
docker compose up --build            # uses your .env, serves on http://localhost:8000
```

The image runs as a non-root user, logs in JSON, hides technical error details, and has a healthcheck. It reads `$PORT`, so it deploys to Railway (or similar) from this repo: set `LLM_PROVIDER`, `LLM_API_KEY` and `LLM_MODEL` as service variables.

## Tests and evaluation

```bash
pytest                                          # 52 tests, no network or key needed
python -m eval.run_eval --baseline              # starter kit, for comparison
python -m eval.run_eval --mode extractive       # no-LLM mode
python -m eval.run_eval --runs 3                # LLM mode (from .env), 3 runs for stability
python -m eval.run_eval --split test            # held-out questions only
```

Each run writes `eval/results_<mode>.md` with a mode column per question. v1 results are kept in `eval/v1_results/`.

### Results snapshot

v1 used a single 25-question evaluation set (no dev/test split): extractive scored 17/25 and LLM scored 24/25. For v2, the 25-question dev set was used during development and tuning, and 13 entirely new questions formed a held-out test set. Extractive scored 25/25 on dev and 9/13 on test (four test misses). LLM scored 25/25 on dev and 13/13 on test, plus 4/4 LLM-only follow-ups, in each of 3 runs (42/42 overall per run). The third run's latency was 584 ms p50 / 1215 ms max. Full details: [SOLUTION_DESIGN.md](SOLUTION_DESIGN.md), [ARCHITECTURE.md](ARCHITECTURE.md), and the [evaluation results](eval/).

## API

Every endpoint returns the same envelope, success or error:

```json
{
  "status": "success | error",
  "status_code": 200,
  "message": "Answer found in the documentation.",
  "technical_message": null,
  "error_code": null,
  "data": { "...endpoint-specific DTO..." },
  "request_id": "a1b2c3d4e5f6a7b8",
  "timestamp": "2025-01-01T10:00:00+00:00"
}
```

| Method | Path | `data` |
|---|---|---|
| POST | `/api/v1/ask` | `AskResponseDTO`: answer_status, answer_type, answer, citations, related_documents, missing_information, standalone_question, mode, decision_reason |
| POST | `/api/v1/feedback` | `FeedbackResponseDTO` |
| GET | `/api/v1/insights/documentation-gaps` | Unanswered questions by frequency |
| GET | `/api/v1/health` | Mode, LLM, embeddings, index size |

Errors: `VALIDATION_FAILED` (422, `data` lists the fields), `NOT_FOUND`, `METHOD_NOT_ALLOWED`, `SERVICE_UNAVAILABLE`, `INTERNAL_ERROR`, and the codes in `app/core/exceptions.py`. Send `X-Request-ID` to correlate with logs.

## Project structure

Request flow: `RequestDTO -> Controller -> Service -> Mapper (DTO to model) -> DAO -> Model -> Mapper (model to DTO) -> Service -> ResponseDTO -> Controller`.

```
app/
  main.py                    app factory: logging, middleware, exception handlers, routes
  core/                      settings, logging, request ID middleware, exceptions,
                             centralized exception handlers, response envelope builder,
                             component registry, application container (wiring)
  api/controllers/           ask, feedback, insights, health, ui
  api/dependencies.py        hands each controller its service
  dto/                       request/response DTOs, generic ApiResponseDTO[T]
  models/                    domain models (corpus, query, answer, guard results, log records)
  mappers/                   DTO <-> model conversion
  dao/                       document source, corpus store, query log store (pluggable)
  ingestion/                 sentence splitting, chunking, corpus builder
  retrieval/                 BM25, embeddings, hybrid retriever, glossary/query expander
  llm/                       provider interface, Groq and OpenAI-compatible/Azure clients,
                             factory registry, JSON parser, versioned prompts
  services/                  question answering, follow-up rewriter, feedback, insights, health
  services/answering/        LLM and extractive strategies
  services/guards/           relevance gate, grounding verifier, entity coverage checker
  utils/                     question splitter, redaction, time helpers
  static/index.html          the UI
baseline/                    starter kit code, unchanged, for the before/after comparison
data/                        docs, glossary, eval questions
eval/run_eval.py             evaluation runner
tests/unit, tests/integration
```

## Plugging in a new component

Each pluggable part has a registry. Write the class, register a builder, set the config value:

| Part | Registry | Setting | Built-in |
|---|---|---|---|
| LLM provider | `LLM_CLIENT_REGISTRY` | `LLM_PROVIDER` | `groq`, `azure`, `openai_compatible` (`none` = extractive) |
| Document source | `DOCUMENT_SOURCE_REGISTRY` | `DOCUMENT_SOURCE` | `json` |
| Query log store | `QUERY_LOG_STORE_REGISTRY` | `QUERY_LOG_STORE` | `jsonl`, `none` |

## Configuration

Settings come from (highest first): real environment variables, `.env`, defaults. At startup the log shows where the LLM key came from (masked), which makes a stale exported key easy to spot. See `.env.example` for every option.

## Known limitations

- English only. Follow-ups need an LLM; without one each question is answered on its own.
- Extractive mode scored 25/25 on the v2 dev set but 9/13 on the held-out test set; v1 extractive scored 17/25 on its single unsplit set.
- Grounding verification checks citations and numbers, not every possible wording error.
- The corpus is rebuilt in memory at startup; no live re-indexing yet.
- No authentication or rate limiting on the API yet.
- The query log is a local JSONL file; production needs a database and a retention policy.
