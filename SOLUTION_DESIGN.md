# Solution Design: Solstice Docs Q&A Assistant

## 1. The problem, in my words

New Solstice admins ask the same questions (password resets, export limits, billing) that the docs already answer. Elena wants an admin to type a plain-English question and get a real answer from the documentation. Her one hard requirement: if the docs don't cover it, say "I don't have an answer for that" rather than invent one. So this is a precision-first problem: a wrong answer costs more than an honest "I don't know", because admins act on these answers.

## 2. Assumptions (to confirm with Elena)

| Area | Assumption | Why it matters |
|---|---|---|
| Users | Logged-in admins of customer companies, asking in English | Auth and language scope |
| Content | Docs are public product help and the source of truth; today 6 articles, later hundreds, updated weekly | Drives retrieval and re-indexing design |
| Quality bar | Precision over coverage; "partial" is a valid outcome | Thresholds tuned to refuse when unsure |
| Scope | Answers come from docs only, not account data ("when is my renewal?" gets the general rule) | No customer data access needed |
| Volume | Tens to hundreds of questions a day, answer in under ~5 s | Simple single-service deployment is enough |
| Data | Questions may contain personal data; logs are redacted with limited retention | Privacy |
| LLM | In production, the client's own cloud (e.g. Azure OpenAI in their tenant) | Data residency; Groq is only the demo provider |
| Failure | If the LLM is down, refuse safely; never guess | Elena's rule must hold on bad days too |

## 3. Approach

**Retrieval.** Articles are split into sentences, each with a citable ID (`D-01.S6`), packed into overlapping ~400-character chunks. The starter kit's fixed-size chunker dropped the end of every article, which is exactly where the answers to Q-2, Q-3 and Q-4 are; a test documents this. Search is hybrid: BM25 keywords plus optional embeddings, fused with Reciprocal Rank Fusion. A support-maintained glossary maps admin wording to doc wording ("add a user" -> "invite").

**Three layers against made-up answers (LLM mode).**
1. *Relevance gate* (code): if no passage shares meaningful terms with the question, refuse without calling the LLM. Saves cost; catches the obvious misses.
2. *LLM judgement*: the LLM sees numbered sentences and must return JSON: `answered` / `partial` / `not_covered`, the answer, and cited sentence IDs. Meaning-level cases ("Is SSO on Growth?" when the docs only mention Enterprise) are caught here.
3. *Grounding verification* (code): every citation must be a sentence the LLM was actually given, and every number in the answer must appear in the cited sentences. Otherwise the draft is discarded. Deterministic, cheap, auditable.

**Fail-safe.** One retry on LLM failure; if it still fails, the answer is "I can't verify an answer right now", never a guess.

**Extractive mode (no LLM).** Returns the best-matching sentences verbatim, so no fact can be invented. Improvements: multi-part questions are split, sentences ranked by rare-word overlap (plus embeddings when installed), and an entity check marks "partial" when the question names a plan/format/integration the passage never mentions.

**Follow-ups.** The UI sends the last 3 turns; the LLM rewrites "And for Enterprise?" into a standalone question shown to the admin as "Searched for: ...". The server stays stateless; earlier answers are never a source of facts.

**Gap report.** Unanswered questions are logged (redacted) and listed by frequency at `/api/v1/insights/documentation-gaps`: a to-do list for the docs team.

## 4. Results

`data/eval_questions.json`: 25 **dev** questions (the 5 provided plus 20 written while designing), 13 **test** questions written before tuning and never used to tune, and 4 follow-up cases (LLM only).

| Mode | Dev (25) | Test (13) | Answered an unanswerable question |
|---|---|---|---|
| Starter kit | 4 | 6 | 15 of 15 |
| Extractive v2 (no LLM) | 24 | 9 | 2 of 15 |
| LLM v1 (Groq gpt-oss-20b) | 24 | not run | 1 of 10 (the old fallback, now fixed) |

The extractive dev/test gap (24/25 vs 9/13) is the honest cost of tuning on questions we wrote ourselves: its test misses are vocabulary it has never seen ("minimum length", "protocol") and limits the docs are silent about ("how many members can I invite"). That is the strongest argument for LLM mode. LLM v2 numbers: run `python -m eval.run_eval --runs 3`.

## 5. Trade-offs and alternatives considered

| Option | Why not chosen (for now) |
|---|---|
| Plain RAG, refusal by prompt only | Refusal depends on the model obeying; no proof. Our design is this plus two code checks. |
| All docs in the prompt (no retrieval) | Viable for 6 articles today, but cost and latency grow with the docs. Our verification layer would still apply. |
| Agentic / self-correcting RAG | 2-5x cost and latency, harder to test; overkill for FAQ-style questions. |
| Curated FAQ answers | Highest precision, but manual upkeep. Good later as a "verified answers" layer on top. |
| Vector database, LangChain | Unneeded for 12 chunks; plain code keeps the safety logic visible and testable. |

## 6. With more time, data or budget

- Replace self-written eval questions with real ones from Elena's ticket history; keep a held-out set.
- A connector for the real docs site or CMS (the source is pluggable), re-indexing on change.
- Postgres + pgvector behind the existing `CorpusDAO` interface once docs reach the hundreds.
- A cross-encoder reranker and an NLI entailment check to extend Layer 3 beyond numbers.
- Admin SSO, rate limiting, monitoring of refusal rate and thumbs-down rate, CI running tests and the extractive eval.
- Deployment: Docker image on Azure Container Apps or AKS, Azure OpenAI, Key Vault for secrets.

## 7. Scope note

**Core** (what the brief asked): retrieval fix, three-layer guarding, extractive fallback, eval. **Extensions**, built on top and labelled as such: follow-up questions, layered API (DTO / service / DAO), pluggable registries, centralized errors, Docker.
