"""End-to-end service behaviour with a scripted fake LLM, and in extractive mode."""
from app.core.exceptions import LlmAuthenticationException, LlmTimeoutException
from tests.helpers import FakeLlmClient, ask_question, build_container, build_test_settings

LLM_SETTINGS = build_test_settings(llm_retry_backoff_seconds=0.0)
VALIDITY_QUESTION = "How long is a password reset link valid?"


def build_llm_container(scripted_replies):
    fake_llm_client = FakeLlmClient(scripted_replies)
    return build_container(LLM_SETTINGS, fake_llm_client), fake_llm_client


# ---------------------------------------------------------------- LLM strategy: the three layers

def test_layer1_refuses_out_of_scope_without_calling_llm():
    container, fake_llm_client = build_llm_container([])
    response = ask_question(container, "Does Solstice have a mobile app?")
    assert response.answer_status == "not_covered"
    assert fake_llm_client.call_count == 0


def test_grounded_llm_answer_is_returned_with_citation():
    container, _ = build_llm_container([
        {"status": "answered", "answer": "Reset links expire after 15 minutes.", "citations": ["D-01.S6"]},
    ])
    response = ask_question(container, VALIDITY_QUESTION)
    assert response.answer_status == "answered"
    assert response.answer_type == "generated_answer"
    assert response.citations[0].sentence_id == "D-01.S6"


def test_layer3_rejects_invented_number():
    container, _ = build_llm_container([
        {"status": "answered", "answer": "Reset links expire after 24 hours.", "citations": ["D-01.S6"]},
    ])
    response = ask_question(container, VALIDITY_QUESTION)
    assert response.answer_status == "not_covered"
    assert response.decision_reason.startswith("grounding_check_failed:numbers_not_in_cited_text")


def test_layer3_rejects_invented_citation():
    container, _ = build_llm_container([
        {"status": "answered", "answer": "Yes, via the API.", "citations": ["D-99.S1"]},
    ])
    response = ask_question(container, "Can I use the Solstice API to sync data with Salesforce?")
    assert response.answer_status == "not_covered"
    assert "citation_not_in_context" in response.decision_reason


def test_layer2_not_covered_lists_related_documents():
    container, _ = build_llm_container([{"status": "not_covered", "answer": "", "citations": []}])
    response = ask_question(container, "Can I use the Solstice API to sync data with Salesforce?")
    assert response.answer_status == "not_covered"
    related_doc_ids = []
    for related_document in response.related_documents:
        related_doc_ids.append(related_document.doc_id)
    assert "D-06" in related_doc_ids


def test_partial_answer_reports_missing_information():
    container, _ = build_llm_container([{
        "status": "partial",
        "answer": "SSO is available on Enterprise plans.",
        "citations": ["D-05.S1"],
        "missing": "whether the Growth plan supports SSO",
    }])
    response = ask_question(container, "Is SSO available on the Growth plan?")
    assert response.answer_status == "partial"
    assert "Growth" in response.missing_information


def test_unknown_llm_status_is_refused():
    container, _ = build_llm_container([{"status": "maybe", "answer": "Perhaps.", "citations": ["D-01.S6"]}])
    response = ask_question(container, VALIDITY_QUESTION)
    assert response.answer_status == "not_covered"
    assert response.decision_reason == "invalid_llm_status:maybe"


def test_llm_failure_after_retry_is_a_safe_refusal_not_a_guess():
    container, fake_llm_client = build_llm_container([LlmTimeoutException(), LlmTimeoutException()])
    response = ask_question(container, "Is SSO available on the Growth plan?")
    assert response.mode == "llm_unavailable"
    assert response.answer_status == "not_covered"
    assert fake_llm_client.call_count == 2


def test_llm_retry_recovers_after_one_failure():
    container, fake_llm_client = build_llm_container([
        LlmTimeoutException(),
        {"status": "answered", "answer": "Reset links expire after 15 minutes.", "citations": ["D-01.S6"]},
    ])
    response = ask_question(container, VALIDITY_QUESTION)
    assert response.answer_status == "answered"
    assert fake_llm_client.call_count == 2


def test_authentication_error_is_not_retried():
    container, fake_llm_client = build_llm_container([LlmAuthenticationException()])
    response = ask_question(container, VALIDITY_QUESTION)
    assert response.mode == "llm_unavailable"
    assert fake_llm_client.call_count == 1


# ---------------------------------------------------------------- follow-up questions

def test_followup_is_rewritten_before_search():
    container, fake_llm_client = build_llm_container([
        {"standalone_question": "What is the API rate limit for the Enterprise plan?"},
        {"status": "answered", "answer": "Enterprise plans are limited to 300 requests per minute.",
         "citations": ["D-06.S5"]},
    ])
    history = [{"question": "What are the API rate limits for the Growth plan?", "answer": "60 requests per minute."}]
    response = ask_question(container, "And for Enterprise?", history)
    assert response.standalone_question == "What is the API rate limit for the Enterprise plan?"
    assert response.answer_status == "answered"
    assert "Enterprise plan" in fake_llm_client.received_user_prompts[1]


def test_followup_rewrite_failure_uses_question_as_typed():
    container, _ = build_llm_container([
        LlmTimeoutException(),
        {"status": "answered", "answer": "Reset links expire after 15 minutes.", "citations": ["D-01.S6"]},
    ])
    history = [{"question": "How do I reset my password?", "answer": "Use Forgot password."}]
    response = ask_question(container, VALIDITY_QUESTION, history)
    assert response.standalone_question is None
    assert response.answer_status == "answered"


# ---------------------------------------------------------------- extractive strategy (no LLM)

EXTRACTIVE_CONTAINER = build_container(build_test_settings())


def test_extractive_answers_with_verbatim_passage():
    response = ask_question(EXTRACTIVE_CONTAINER, "What's the maximum number of rows I can export to CSV?")
    assert response.mode == "extractive"
    assert response.answer_type == "verbatim_passage"
    assert "10,000" in response.answer


def test_extractive_marks_missing_plan_as_partial():
    response = ask_question(EXTRACTIVE_CONTAINER, "Is SSO available on the Growth plan?")
    assert response.answer_status == "partial"
    assert "growth" in response.missing_information


def test_extractive_uses_glossary_synonyms():
    response = ask_question(EXTRACTIVE_CONTAINER, "How do I add a new user to my team?")
    assert response.answer_status == "answered"
    assert "Invite Member" in response.answer


def test_extractive_answers_each_part_of_a_two_part_question():
    response = ask_question(
        EXTRACTIVE_CONTAINER,
        "How do I invite a teammate, and what are the rules for a new password?",
    )
    cited_doc_ids = set()
    for citation in response.citations:
        cited_doc_ids.add(citation.doc_id)
    assert cited_doc_ids == {"D-01", "D-02"}


def test_extractive_refuses_out_of_scope():
    response = ask_question(EXTRACTIVE_CONTAINER, "Can I connect Solstice to Salesforce?")
    assert response.answer_status == "not_covered"
    assert response.answer_type == "refusal"


def test_eval_rate_limiter_waits_before_21st_call(monkeypatch):
    from collections import deque

    from eval.run_eval import wait_for_llm_rate_limit

    sleep_calls = []
    current_time = [100.0]

    def fake_sleep(seconds):
        sleep_calls.append(seconds)
        current_time[0] += seconds

    monkeypatch.setattr("eval.run_eval.time.monotonic", lambda: current_time[0])
    monkeypatch.setattr("eval.run_eval.time.sleep", fake_sleep)

    recent_calls = deque([41.0 + (i * 3) for i in range(20)])
    wait_for_llm_rate_limit(recent_calls, max_calls_per_minute=10, window_seconds=60.0)

    assert sleep_calls
    assert len(recent_calls) == 20
    assert recent_calls[-1] >= 100.0


def test_followup_without_llm_uses_question_as_typed():
    history = [{"question": "How do I reset my password?", "answer": "Use Forgot password."}]
    response = ask_question(EXTRACTIVE_CONTAINER, "How long is a password reset link valid?", history)
    assert response.standalone_question is None
    assert response.debug["followup_rewrite"] == "no_llm_question_used_as_typed"
