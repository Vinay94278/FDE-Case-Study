"""Guard checks and small utilities, tested in isolation."""
import pytest

from app.core.exceptions import LlmResponseFormatException
from app.llm.json_response_parser import parse_json_object
from app.models.corpus_models import Chunk, Sentence
from app.models.query_models import RetrievalHit
from app.retrieval.glossary import QueryExpander, load_glossary
from app.services.guards.entity_coverage_checker import EntityCoverageChecker
from app.services.guards.grounding_verifier import GroundingVerifier
from app.services.guards.relevance_gate import RelevanceGate
from app.utils.question_splitter import split_question_into_parts
from app.utils.redaction import redact_personal_data
from tests.helpers import build_test_settings

SETTINGS = build_test_settings()
GLOSSARY = load_glossary(SETTINGS.glossary_path)
EXPIRY_SENTENCE = Sentence("D-01.S6", "D-01", "Resetting Your Password", 5,
                           "Note: password reset links expire after 15 minutes.")
LIMIT_SENTENCE = Sentence("D-03.S5", "D-03", "Exporting Reports to CSV", 4,
                          "Important limit: CSV exports are capped at 10,000 rows.")
CONTEXT_BY_ID = {"D-01.S6": EXPIRY_SENTENCE, "D-03.S5": LIMIT_SENTENCE}


def make_hit(term_coverage, cosine_similarity=None):
    chunk = Chunk("D-01.C1", "D-01", "Resetting Your Password", (EXPIRY_SENTENCE,))
    return RetrievalHit(chunk, 0.01, 1.0, cosine_similarity, term_coverage)


# ---------------------------------------------------------------- relevance gate (layer 1)

def test_gate_fails_without_hits():
    assert RelevanceGate(0.35).evaluate([], 0.2, True).passed is False


def test_gate_passes_on_term_coverage():
    assert RelevanceGate(0.35).evaluate([make_hit(0.5)], 0.2, False).passed is True


def test_gate_uses_cosine_only_when_allowed():
    gate = RelevanceGate(0.35)
    low_coverage_hit = make_hit(0.0, cosine_similarity=0.6)
    assert gate.evaluate([low_coverage_hit], 0.2, True).passed is True
    assert gate.evaluate([low_coverage_hit], 0.2, False).passed is False


# ---------------------------------------------------------------- grounding verifier (layer 3)

def test_verifier_accepts_grounded_answer():
    result = GroundingVerifier().verify("Links expire after 15 minutes.", ["D-01.S6"], CONTEXT_BY_ID)
    assert result.passed is True


def test_verifier_accepts_number_with_thousands_separator():
    result = GroundingVerifier().verify("The cap is 10000 rows.", ["D-03.S5"], CONTEXT_BY_ID)
    assert result.passed is True


@pytest.mark.parametrize("answer_text, citation_ids, expected_reason_start", [
    ("", ["D-01.S6"], "empty_answer"),
    ("Links expire quickly.", [], "no_citations"),
    ("Yes, via the API.", ["D-99.S1"], "citation_not_in_context"),
    ("Links expire after 24 hours.", ["D-01.S6"], "numbers_not_in_cited_text"),
])
def test_verifier_rejects_ungrounded_answers(answer_text, citation_ids, expected_reason_start):
    result = GroundingVerifier().verify(answer_text, citation_ids, CONTEXT_BY_ID)
    assert result.passed is False
    assert result.failure_reason.startswith(expected_reason_start)


# ---------------------------------------------------------------- entity check, glossary, splitter

def test_entity_checker_finds_missing_plan():
    checker = EntityCoverageChecker(GLOSSARY)
    missing = checker.find_missing_entities("Is SSO on the Growth plan?", "Enterprise plans support SSO via SAML 2.0.")
    assert missing == ["growth"]


def test_entity_checker_accepts_present_plan():
    checker = EntityCoverageChecker(GLOSSARY)
    missing = checker.find_missing_entities("Growth plan rate limit?", "Growth plans are limited to 60 requests per minute.")
    assert missing == []


def test_query_expander_maps_admin_wording_to_doc_wording():
    expanded_text = QueryExpander(GLOSSARY).expand("How do I add a new user to my team?")
    assert "invite" in expanded_text
    assert "add a new user" not in expanded_text


def test_question_splitter_splits_two_questions():
    parts = split_question_into_parts("How do I invite a teammate, and what are the rules for a new password?")
    assert parts == ["How do I invite a teammate", "what are the rules for a new password?"]


def test_question_splitter_keeps_single_question():
    assert split_question_into_parts("How do I reset my password?") == ["How do I reset my password?"]


def test_redaction_hides_email_and_long_numbers():
    redacted_text = redact_personal_data("I am jane.doe@acme.com, account 12345678")
    assert "jane.doe" not in redacted_text
    assert "12345678" not in redacted_text


def test_json_parser_handles_code_fences_and_rejects_text():
    assert parse_json_object('```json\n{"status": "not_covered"}\n```') == {"status": "not_covered"}
    with pytest.raises(LlmResponseFormatException):
        parse_json_object("Sorry, I cannot help with that.")
