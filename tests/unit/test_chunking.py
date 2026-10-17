"""Chunking keeps every sentence; the starter kit's chunker did not."""
import pytest

from app.dao.document_source_dao import JsonFileDocumentSourceDAO
from app.ingestion.sentence_chunker import build_chunks, build_sentences
from baseline.docs_qa_utils import chunk_text
from tests.helpers import build_test_settings

SETTINGS = build_test_settings()
DOCUMENTS = JsonFileDocumentSourceDAO(SETTINGS.docs_path).load_documents()


def find_document(doc_id):
    for document in DOCUMENTS:
        if document.doc_id == doc_id:
            return document
    raise KeyError(doc_id)


def build_all_chunks():
    all_chunks = []
    for document in DOCUMENTS:
        all_chunks.extend(build_chunks(build_sentences(document), 400, 1))
    return all_chunks


def test_starter_chunker_loses_text():
    """Documents the starter-kit bug this project fixes."""
    assert chunk_text(find_document("D-02").content) == []
    assert "15 minutes" not in "".join(chunk_text(find_document("D-01").content))


def test_every_sentence_is_indexed_and_text_is_preserved():
    for document in DOCUMENTS:
        sentences = build_sentences(document)
        chunks = build_chunks(sentences, 400, 1)
        indexed_sentence_ids = set()
        for chunk in chunks:
            for sentence_id in chunk.get_sentence_ids():
                indexed_sentence_ids.add(sentence_id)
        all_sentence_ids = set()
        rebuilt_parts = []
        for sentence in sentences:
            all_sentence_ids.add(sentence.sentence_id)
            rebuilt_parts.append(sentence.text)
        assert indexed_sentence_ids == all_sentence_ids
        assert " ".join(" ".join(rebuilt_parts).split()) == " ".join(document.content.split())


@pytest.mark.parametrize("fact", ["15 minutes", "10,000 rows", "60 requests per minute", "Invite Member", "SAML 2.0"])
def test_key_facts_are_in_some_chunk(fact):
    fact_found = False
    for chunk in build_all_chunks():
        if fact in chunk.get_text():
            fact_found = True
    assert fact_found


def test_chunk_ids_are_unique():
    seen_chunk_ids = set()
    for chunk in build_all_chunks():
        assert chunk.chunk_id not in seen_chunk_ids
        seen_chunk_ids.add(chunk.chunk_id)
