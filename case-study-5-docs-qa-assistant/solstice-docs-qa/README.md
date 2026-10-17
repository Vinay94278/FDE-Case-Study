# Solstice Docs Q&A Assistant

Admins type a plain-English question and get an answer drawn only from the Solstice documentation, with the exact source sentence shown. If the docs don't cover the question, it says "I don't have an answer for that in the documentation" instead of guessing.

Design and trade-offs: see `SOLUTION_DESIGN.md`.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # add your Groq API key
uvicorn app.api:app --reload
```

Open http://localhost:8000 for the UI, or http://localhost:8000/docs for the API.

No API key? Set `LLM_PROVIDER=none`. The app runs in extractive mode (returns the best-matching doc sentences verbatim). Everything, including tests and the eval, works offline.

Optional semantic search: `pip install -r requirements-embeddings.txt` (large, needs access to huggingface.co). Without it, retrieval is keyword-only (BM25). `/api/health` reports which mode is active.

## Run the tests and the evaluation

```bash
pytest                                   # 18 tests, no network or key needed
python -m eval.run_eval --baseline       # starter kit, for comparison
python -m eval.run_eval --mode extractive
python -m eval.run_eval                  # LLM mode (uses .env)
```

Each eval run writes a results table to `eval/results_<mode>.md`. The eval set (`data/eval_questions.json`) has the 5 provided questions plus 20 more: every article, paraphrases, a multi-article question, partial-coverage questions, near-miss out-of-scope questions and a prompt-injection attempt.

## How it works

1. Docs are split into sentences (each gets an ID like `D-01.S6`) and packed into overlapping chunks of about 400 characters. No text is dropped.
2. Hybrid retrieval: BM25 keyword scores plus optional embeddings, combined with Reciprocal Rank Fusion.
3. Gate 1: if no retrieved passage shares meaningful terms with the question (or is semantically close), refuse without calling the LLM.
4. The LLM writes a short answer from the numbered sentences only, returning JSON: status (`answered` / `partial` / `not_covered`), answer and cited sentence IDs.
5. Gate 2, in code: citations must exist in the retrieved context, and every number in the answer must appear in the cited sentences. Otherwise the answer is replaced with "I don't have an answer".
6. If the LLM is down or misbehaves, the app falls back to extractive mode instead of failing.
7. Every question is logged (emails and long numbers redacted). `GET /api/gaps` lists unanswered questions, most frequent first: a to-do list for the docs team.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/ask` | `{"question": "..."}` returns status, answer, citations, related docs. Add `?debug=true` for retrieval and gate details. |
| GET | `/api/health` | Mode, LLM, embeddings status, index size |
| POST | `/api/feedback` | Thumbs up/down on an answer |
| GET | `/api/gaps` | Unanswered questions by frequency |

## Switching LLM provider

Config only, no code change. Groq is used for the demo; production would use the client's own cloud.

| Provider | Settings |
|---|---|
| Groq | `LLM_PROVIDER=groq`, `LLM_MODEL=openai/gpt-oss-120b` |
| Azure OpenAI | `LLM_PROVIDER=azure`, `LLM_BASE_URL=<endpoint>`, `LLM_MODEL=<deployment>` |
| Any OpenAI-compatible endpoint | `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL=...` |
| No LLM | `LLM_PROVIDER=none` |

## Project layout

```
app/
  api.py         FastAPI endpoints
  qa.py          pipeline: retrieval, gates, LLM, fallback
  ingest.py      sentence-aware chunking
  retrieval.py   BM25 + optional embeddings + RRF
  llm.py         provider-agnostic LLM client
  textproc.py    tokenizing, stopwords, stemming
  querylog.py    JSONL query log, gap report, redaction
  static/index.html   the UI
baseline/        starter kit code, kept unchanged for the before/after comparison
data/            docs, provided questions, expanded eval set
eval/run_eval.py evaluation runner
tests/           unit and API tests
```

## Known limitations

- Single-turn only; no follow-up questions in context.
- English only.
- Answers come from docs, not account data: "when is my renewal?" gets the general rule, not the user's date.
- Extractive fallback can't recognise partial coverage (for example "Is SSO on Growth?"), so it is stricter and refuses more often.
- Gate 2's number check catches invented figures and citations, not every possible wording error. The LLM's own `not_covered` judgement is the first line of defence.
- The index is rebuilt at startup; there is no live re-indexing when docs change.
- No authentication or rate limiting on the API yet.
- Query logs are a local file; production needs a real store and a retention policy.

## What I'd do next

See "Future work" in `SOLUTION_DESIGN.md`.
