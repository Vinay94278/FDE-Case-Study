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
1. *Relevance gate* (code): in LLM mode, proceed only if term coverage is at least 0.2 or embedding cosine similarity is at least 0.35; in extractive mode, term coverage must be at least 0.6 and cosine cannot pass the gate. Otherwise refuse. This saves cost and catches obvious misses.
2. *LLM judgement*: the LLM sees numbered sentences and must return JSON: `answered` / `partial` / `not_covered`, the answer, and cited sentence IDs. Meaning-level cases ("Is SSO on Growth?" when the docs only mention Enterprise) are caught here.
3. *Grounding verification* (code): every citation must be a sentence the LLM was actually given, and every number in the answer must appear in the cited sentences. Otherwise the draft is discarded. Deterministic, cheap, auditable.

**Why three layers:** The v1 LLM answered "Is SSO available on the Growth plan?" even though the docs mention only Enterprise. Keyword search found related text, but not an answer about Growth; LLM judgement or the extractive entity check must catch that plan mismatch. E-13 showed another miss: extractive mode answered a monthly-plan refund question the docs don't cover. Separately, a failed LLM call fell back to extractive search, so v2 retries once and then refuses rather than returning an unverified result.

**Fail-safe.** One retry on LLM failure; if it still fails, the answer is "I can't verify an answer right now", never a guess.

**Extractive mode (no LLM).** Returns the best-matching sentences verbatim, so no fact can be invented. Improvements: multi-part questions are split, sentences ranked by rare-word overlap (plus embeddings when installed), and an entity check marks "partial" when the question names a plan/format/integration the passage never mentions.

**Follow-ups.** The UI sends the last 3 turns; the LLM rewrites "And for Enterprise?" into a standalone question shown to the admin as "Searched for: ...". The server stays stateless; earlier answers are never a source of facts.

**Gap report.** Unanswered questions are logged (redacted) and listed by frequency at `/api/v1/insights/documentation-gaps`: a to-do list for the docs team.

## 4. Results

The v1 evaluation used one 25-question set and did not have a dev/test split. For v2, the 25-question dev set was retained for development and tuning, and 13 entirely new questions were added as a held-out test set; the test questions were not used for tuning. Four follow-up cases are evaluated in LLM mode only.

| Version / mode | Dev (25) | Held-out test (13) | Follow-ups (4) | Overall result |
|---|---:|---:|---:|---|
| v1 extractive | not split | not measured | not measured | 17/25 on the single v1 set |
| v1 LLM (Groq gpt-oss-20b) | not split | not measured | not measured | 24/25 on the single v1 set |
| v2 extractive (no LLM) | 25/25 | 9/13 | not applicable | 34/38; the four test misses are documented in the eval results |
| v2 LLM (Groq gpt-oss-20b) | 25/25 | 13/13 | 4/4 | 42/42 in each of 3 runs |

The v1 extractive score of 17/25 is from its original unsplit set; v2 scored 25/25 on dev and 9/13 on the newly introduced held-out test, so the v2 test result is the check beyond the development set. The four test misses expose unseen vocabulary ("minimum length", "protocol") and limits the docs do not specify ("how many members can I invite"). The LLM was evaluated against the same 25 dev and 13 held-out questions, plus the four LLM-only follow-ups, and scored 42/42 in each of three runs. The third run's latency was 584 ms p50 / 1215 ms max. See [eval results](eval/results_extractive.md) and [LLM eval results](eval/results_llm_groq_openai_gpt-oss-20b.md).

The five questions supplied with the brief were also run in both modes:

| ID | Question | Extractive result | LLM result |
|---|---|---|---|
| Q-1 | How do I reset my password? | **answered**; D-01.S1, D-01.S3 — If you've forgotten your password, click 'Forgot password?' on the login screen and enter the email address associated with your account. Click the link and choose a new password that's at least 8 characters long, with at least one number. | **answered**; D-01.S1, D-01.S2, D-01.S3 — Click the 'Forgot password?' link on the login screen, enter the email address associated with your account, then check your email for a reset link. Click the link, choose a new password that is at least 8 characters long and contains at least one number, and you’ll be logged out of all other active sessions. |
| Q-2 | How long do I have to use a password reset link before it expires? | **answered**; D-01.S6, D-01.S7 — Note: password reset links expire after 15 minutes. If yours has expired, don't try to reuse the old email -- just go back to the login page and request a brand new reset link. | **answered**; D-01.S6 — Password reset links expire after 15 minutes. |
| Q-3 | What's the maximum number of rows I can export to CSV? | **answered**; D-03.S5, D-03.S6 — Important limit: CSV exports are capped at 10,000 rows. If your report has more rows than that, apply additional filters to narrow it down, or contact support about a bulk data export instead. | **answered**; D-03.S5 — The maximum number of rows you can export to CSV is 10,000. |
| Q-4 | What are the API rate limits for the Growth plan? | **answered**; D-06.S5, D-06.S6 — Rate limits: Growth plans are limited to 60 requests per minute, and Enterprise plans are limited to 300 requests per minute, per API key. Exceeding the limit returns an HTTP 429 response. | **answered**; D-06.S5 — Growth plans are limited to 60 requests per minute, per API key. |
| Q-5 | Can I connect Solstice to Salesforce? | **not_covered**; no cited sentence — I don't have an answer for that in the documentation. | **not_covered**; no cited sentence — I don't have an answer for that in the documentation. |

### Known limitations

- English only. Follow-ups need an LLM; without one, each question is answered on its own.
- Extractive mode scored 25/25 on the v2 dev set but 9/13 on the held-out test set; v1 extractive scored 17/25 on its single unsplit set.
- Grounding verification checks citations and numbers, not every possible wording error.
- The corpus is rebuilt in memory at startup; there is no live re-indexing yet.

## 5. Trade-offs and alternatives considered

| Option | Why not chosen (for now) |
|---|---|
| Plain RAG, refusal by prompt only | Refusal depends on the model obeying; no proof. The current design adds two code checks. |
| All docs in the prompt (no retrieval) | Viable for 6 articles today, but cost and latency grow with the docs. The verification layer would still apply. |
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

*To keep the codebase maintainable at scale rather than leaving a flat prototype script, I specified a strict layered architecture (`DTO -> Controller -> Service -> Strategy/Guards -> DAO`) and used structured LLM prompting to scaffold the boilerplate rapidly—freeing up the 3–4 hour window to focus on retrieval accuracy, failure modes, and the 3-layer verification gates.*
