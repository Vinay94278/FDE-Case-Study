# Extractive Mode: What Failed, What Changed, and What to Try Next

## What extractive mode does

Extractive mode does not write a new answer. It searches the documentation and returns selected source sentences with citations. This avoids generated facts, but it can still select the wrong passage or mistake related text for a complete answer.

## The eight v1 evaluation failures

Extractive v1 scored **17/25** on its original evaluation set. These are the eight failed questions and the reason each failed:

| Question | v1 failure |
|---|---|
| **E-03: “How do I add a new user to my team?”** | The docs say to “invite” a team member. The wording mismatch caused a false refusal. |
| **E-05: “How long are CSV exports kept?”** | The answer, 7 days, was in the docs, but retrieval missed it and refused. |
| **E-10: “What error do I get if I go over the API rate limit?”** | The docs state HTTP 429, but v1 did not retrieve that sentence and refused. |
| **E-11: “How do I invite a teammate, and what are the rules for a new password?”** | It handled only one part and missed the required team-invitation source. |
| **E-12: “Is SSO available on the Growth plan?”** | It answered from related SSO text even though the docs only mention Enterprise. |
| **E-13: “Can I get a refund on a monthly plan?”** | It treated related billing text as an answer, but the docs do not cover this refund question. |
| **E-14: “Can I export a report as a PDF?”** | It answered from related export text, although the docs cover CSV and do not say PDF is supported. |
| **E-15: “What is the API rate limit on the Starter plan?”** | It used related rate-limit text for other plans; the docs do not specify a Starter limit. |

The first three were **false refusals**: an answer existed, but retrieval did not find it. E-11 was an **incomplete multi-part response**. E-12 to E-15 were **unsupported answers**: related text was treated as if it answered the exact question.

## What changed from v1 to v2

Extractive v2 scored **25/25 on the development set**. The changes targeted the failures above:

1. **Sentence-aware chunking with overlap:** keeps complete sentences, includes article endings, and gives sentences stable citation IDs. This prevents useful facts from being cut off or lost.
2. **Hybrid retrieval:** BM25 keyword search is combined with optional embeddings using Reciprocal Rank Fusion. BM25 weights informative, rarer words more heavily; embeddings can help when wording differs.
3. **Maintained glossary:** maps common admin phrases to doc phrases, for example “add a user” to “invite,” “kept” to “retained,” and “go over” to “exceed.”
4. **Multi-part question splitting:** searches for each part separately, then combines the selected sentences and citations.
5. **Sentence ranking:** ranks candidate sentences by rare-word overlap and, when available, sentence-embedding similarity; returns up to two source sentences.
6. **Relevance gate:** extractive answers require at least 0.6 term coverage. Embedding similarity alone cannot pass this gate.
7. **Entity coverage check:** uses glossary entities such as plans, file formats, and integrations. If the question names an entity absent from the anchor evidence, the result can be marked partial instead of answered.

The detailed implementation is in [extractive_answer_strategy.py](app/services/answering/extractive_answer_strategy.py), [hybrid_retriever.py](app/retrieval/hybrid_retriever.py), [sentence_chunker.py](app/ingestion/sentence_chunker.py), and [glossary.json](data/glossary.json).

### Why v2 still failed on held-out questions

V2 scored **9/13 on the held-out test set**, not 25/25. The four failures show limits that the development examples did not expose:

| Question | What happened | Why |
|---|---|---|
| **T-01: “What is the minimum password length?”** | False refusal | The doc says “at least 8 characters”; the system did not connect that wording to “minimum length.” |
| **T-05: “Which protocol does SSO use?”** | False refusal | The doc says “SAML 2.0”; keyword matching did not understand that this is the requested protocol. |
| **T-09: “Is there a limit on how many team members I can invite?”** | Unsupported answer | The invitation article explains how to invite someone but gives no maximum. |
| **T-10: “Can admins change a team member's role later?”** | Unsupported answer | The article says a role is selected during invitation; it does not say whether it can be changed later. |

The first two need better vocabulary/meaning matching. The latter two need a stronger check that the evidence entails the requested fact, not just that it is about the same subject. The entity check cannot catch every missing relationship or detail.

These scores should be read with the split in mind: the original v1 set and the v2 dev/test evaluation are not a clean, independent experiment proving that code changes alone caused every score difference. The v2 held-out result is the better indicator of behavior on new questions. See [v1 extractive results](eval/v1_results/results_extractive.md) and [v2 extractive results](eval/results_extractive.md).

## Three strong alternatives

No approach has a universal accuracy percentage. Quality depends on the corpus, question set, and definition of a correct answer. Compare alternatives on representative held-out questions, measuring answerable-question recall, unsupported-answer rate, citation accuracy, and refusal rate.

### 1. Hybrid search + reranking + answerability check — recommended for a growing corpus

Retrieve candidates with keyword and vector search, rerank them against the question with a cross-encoder, then return only cited text that passes a tested support/answerability check. This improves candidate ordering while preserving source-based answers. It requires model inference for reranking/checking, though it does not require a generative chat answer.

### 2. Extractive QA span model — useful when paraphrases are the main issue

Give a question-answering model the question and retrieved passage. It predicts the exact start and end of an answer span, such as “SAML 2.0.” Return that span with its source, or refuse if confidence is below a calibrated threshold. This is not a free-form chat answer, but it is still a machine-learning model and can select an unsupported span.

### 3. Curated FAQs with extractive fallback — strongest control for frequent questions

Write and review approved answers for common questions, match incoming questions to them, and send unmatched questions to extractive search or refusal. Approved answers are predictable, but FAQ coverage and upkeep are manual.

Production search systems and libraries provide building blocks for these designs, but their product documentation does not promise an accuracy score for this Solstice corpus. A local evaluation is required before choosing one.

## If generative LLMs are not allowed

“No generative LLM” still allows several approaches:

- **Search-engine retrieval:** use an inverted index such as OpenSearch/Elasticsearch for BM25 and, if permitted, a vector index for semantic candidate retrieval. Return source sentences rather than generated prose.
- **Extractive QA model:** use a task-specific span predictor, with strict confidence calibration and citations. Confirm that policy permits this model; it is still ML.
- **Cross-encoder reranker or answerability classifier:** score whether a candidate passage answers the question. These are also ML models, not generative LLMs.
- **Rules, glossary, and structured facts:** maintain synonyms, entity aliases, and explicit facts such as plan limits. Use deterministic matching and refuse when the fact is missing. This uses no ML, but requires domain-specific maintenance and cannot understand every paraphrase.
- **Curated FAQs:** provide reviewed answers for known frequent questions and refuse or use cited search for unmatched questions. This also uses no ML if matching is deterministic.

If **all ML models** are prohibited, use search plus deterministic rules, structured facts, and/or curated FAQs. Do not present similarity as proof of an answer: when rules cannot establish that the requested fact exists, return a refusal.

## Main difficulties and ways to manage them

| Difficulty | Why it happens | Mitigation without a generative LLM |
|---|---|---|
| Unfamiliar wording | Exact terms differ from documentation (“protocol” vs. “SAML”). | Maintain aliases/glossary; add real user paraphrases to evaluation; optionally use approved embeddings or a non-generative reranker. |
| Related but incomplete evidence | A passage can discuss the topic without stating the requested limit, permission, or relationship. | Require evidence for the asked attribute; use structured facts or a calibrated answerability check; otherwise refuse. |
| Threshold trade-offs | A strict threshold misses valid paraphrases; a loose one accepts weak matches. | Tune on a dev set, freeze a separate test set, and track both false refusals and unsupported answers. |
| Multi-part questions | One part may retrieve well while another is missed. | Split questions carefully, answer and score each part independently, and return partial/refusal if any required part is unsupported. |
| Entity and terminology maintenance | New plans, integrations, aliases, and product terms appear over time. | Keep glossary and fact data outside code, assign an owner, review changes with docs/product updates, and test them automatically. |
| Larger, changing corpus | In-memory indexes and full rebuilds cost more as documents grow and change. | Use a persistent search index, incremental updates, stable source IDs, and monitoring for indexing failures. |
| Measuring quality | A high development score can reflect tuning to familiar examples. | Use representative held-out questions; separately report answerable recall, unsupported-answer rate, citation accuracy, and refusal rate. |

For this project, the practical next step is not to claim a new accuracy number. Add the T-01/T-05 vocabulary cases and T-09/T-10 unsupported-detail cases to regression tests, then compare candidate changes on a fresh held-out set before deploying them.

## References

- [Sentence Transformers: Retrieve & Re-Rank](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html)
- [Elastic: Reciprocal Rank Fusion](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion)
- [Microsoft: Semantic ranking in Azure AI Search](https://learn.microsoft.com/en-us/azure/search/semantic-search-overview)
- [SQuAD 2.0: answerable and unanswerable reading-comprehension questions](https://rajpurkar.github.io/SQuAD-explorer/)
