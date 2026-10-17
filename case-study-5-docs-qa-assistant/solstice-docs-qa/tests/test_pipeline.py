"""Tests that run with no API key and no network.

The LLM is replaced by a scripted fake so we can prove Gate 2 catches
hallucinated citations and numbers, and that the app degrades gracefully
when the LLM fails.
"""
from dataclasses import replace

import pytest

from app.config import load_settings
from app.ingest import build_corpus, load_docs
from app.llm import LLMError, parse_json_object
from app.qa import NOT_COVERED_MSG, QAService
from baseline.docs_qa_utils import chunk_text

SETTINGS = replace(load_settings(), llm_provider="none", embeddings_enabled=False)
DOCS = load_docs(SETTINGS.docs_path)


class FakeLLM:
    name = "fake"

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, 0

    def complete_json(self, system, user):
        self.calls += 1
        if self.error:
            raise self.error
        return self.reply


def service(llm=None):
    return QAService(SETTINGS, llm=llm)


# ---------------------------------------------------------------- chunking

def test_starter_chunker_loses_text():
    """Documents the starter-kit bug this project fixes."""
    by_id = {d["doc_id"]: d["content"] for d in DOCS}
    assert chunk_text(by_id["D-02"]) == []                      # short doc vanishes
    assert "15 minutes" not in "".join(chunk_text(by_id["D-01"]))  # Q-2's answer is cut off


def test_every_sentence_of_every_doc_is_indexed():
    sentences, chunks = build_corpus(DOCS)
    indexed = {s.id for c in chunks for s in c.sentences}
    assert indexed == set(sentences)
    for doc in DOCS:
        rebuilt = " ".join(s.text for s in sentences.values() if s.doc_id == doc["doc_id"])
        assert " ".join(rebuilt.split()) == " ".join(doc["content"].split())


@pytest.mark.parametrize("fact", ["15 minutes", "10,000 rows", "60 requests per minute", "Invite Member", "SAML 2.0"])
def test_key_facts_are_in_some_chunk(fact):
    _, chunks = build_corpus(DOCS)
    assert any(fact in c.text for c in chunks)


# ---------------------------------------------------------------- gate 1

def test_out_of_scope_question_is_refused_without_calling_llm():
    llm = FakeLLM(reply={"status": "answered", "answer": "Yes", "citations": ["D-06.S1"]})
    r = service(llm).ask("Does Solstice have a mobile app?")
    assert r.status == "not_covered" and r.answer == NOT_COVERED_MSG
    assert llm.calls == 0  # no LLM cost for obvious misses


# ---------------------------------------------------------------- gate 2

def test_grounded_llm_answer_passes():
    llm = FakeLLM(reply={"status": "answered", "answer": "Reset links expire after 15 minutes.",
                         "citations": ["D-01.S6"]})
    r = service(llm).ask("How long is a password reset link valid?")
    assert r.status == "answered" and r.mode == "llm"
    assert [c.sentence_id for c in r.citations] == ["D-01.S6"]


def test_invented_number_is_rejected():
    llm = FakeLLM(reply={"status": "answered", "answer": "Reset links expire after 24 hours.",
                         "citations": ["D-01.S6"]})
    r = service(llm).ask("How long is a password reset link valid?")
    assert r.status == "not_covered"
    assert r.reason.startswith("gate2_numbers_not_in_cited_text")


def test_invented_citation_is_rejected():
    llm = FakeLLM(reply={"status": "answered", "answer": "Yes, via the API.", "citations": ["D-99.S1"]})
    r = service(llm).ask("Can I use the Solstice API to sync data with Salesforce?")
    assert r.status == "not_covered" and "citation_not_in_context" in r.reason


def test_answer_without_citations_is_rejected():
    llm = FakeLLM(reply={"status": "answered", "answer": "Yes, it integrates.", "citations": []})
    r = service(llm).ask("Can I use the Solstice API to sync data with Salesforce?")
    assert r.status == "not_covered" and r.reason == "gate2_no_citations"


def test_llm_not_covered_returns_refusal_with_related_docs():
    llm = FakeLLM(reply={"status": "not_covered", "answer": "", "citations": []})
    r = service(llm).ask("Can I use the Solstice API to sync data with Salesforce?")
    assert r.status == "not_covered"
    assert any(d.doc_id == "D-06" for d in r.related_docs)


def test_partial_answer_includes_what_is_missing():
    llm = FakeLLM(reply={"status": "partial", "answer": "SSO is available on Enterprise plans.",
                         "citations": ["D-05.S1"], "missing": "whether the Growth plan supports SSO"})
    r = service(llm).ask("Is SSO available on the Growth plan?")
    assert r.status == "partial" and "Not covered in the documentation" in r.answer


# ---------------------------------------------------------------- resilience

def test_llm_failure_falls_back_to_extractive():
    llm = FakeLLM(error=LLMError("timeout"))
    r = service(llm).ask("What's the maximum number of rows I can export to CSV?")
    assert r.mode == "extractive_fallback" and r.status == "answered"
    assert "10,000" in r.answer


def test_extractive_mode_works_without_any_llm():
    r = service().ask("What are the API rate limits for the Growth plan?")
    assert r.mode == "extractive" and "60 requests per minute" in r.answer


def test_parse_json_handles_code_fences():
    assert parse_json_object('```json\n{"status": "not_covered"}\n```') == {"status": "not_covered"}
    with pytest.raises(LLMError):
        parse_json_object("Sorry, I cannot help with that.")


# ---------------------------------------------------------------- API

def test_api_ask_and_validation(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "false")
    monkeypatch.setenv("LOG_PATH", str(tmp_path / "q.jsonl"))
    from app.api import app

    with TestClient(app) as client:
        ok = client.post("/api/ask", json={"question": "How do I set up SSO?"})
        assert ok.status_code == 200 and ok.json()["status"] == "answered"
        assert client.post("/api/ask", json={"question": "x" * 600}).status_code == 422
        client.post("/api/ask", json={"question": "Does Solstice have a mobile app?"})
        gaps = client.get("/api/gaps").json()["gaps"]
        assert gaps[0]["question"] == "does solstice have a mobile app?"
