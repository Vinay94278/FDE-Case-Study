"""Split articles into sentences and pack them into overlapping chunks.

Why not fixed-size character chunks (the starter kit approach)?
    - `len(text) // 400` drops the end of every article, and articles shorter than
      400 characters produce no chunks at all. In the seed data that loses the exact
      facts asked about (15-minute link expiry, 10,000-row cap, 60 req/min limit).
    - Character cuts split words and sentences, which breaks citations.

Here every sentence gets a stable ID (for example "D-01.S6") so an answer can cite
the exact sentence and code can check that citation.
"""
import re
from typing import List

from app.models.corpus_models import Chunk, Document, Sentence

# A sentence ends at . ! or ? followed by whitespace and an uppercase letter, digit,
# quote, bracket or backtick. "Forgot password?' on the login" does not split.
SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(`])")


def split_into_sentence_texts(article_text: str) -> List[str]:
    sentence_texts = []
    for candidate_text in SENTENCE_BOUNDARY_PATTERN.split(article_text.strip()):
        cleaned_text = candidate_text.strip()
        if cleaned_text != "":
            sentence_texts.append(cleaned_text)
    return sentence_texts


def build_sentences(document: Document) -> List[Sentence]:
    sentences = []
    sentence_texts = split_into_sentence_texts(document.content)
    for position, sentence_text in enumerate(sentence_texts):
        sentence_id = document.doc_id + ".S" + str(position + 1)
        sentence = Sentence(
            sentence_id=sentence_id,
            doc_id=document.doc_id,
            title=document.title,
            position=position,
            text=sentence_text,
        )
        sentences.append(sentence)
    return sentences


def build_chunks(sentences: List[Sentence], max_chunk_chars: int, overlap_sentence_count: int) -> List[Chunk]:
    """Pack whole sentences into chunks of up to about max_chunk_chars characters.

    Consecutive chunks share `overlap_sentence_count` sentences so a fact near a
    boundary is never cut off from its context. A sentence longer than the limit
    becomes its own chunk. The end of the article is always included.
    """
    if len(sentences) == 0:
        return []

    chunks = []
    total_sentence_count = len(sentences)
    chunk_start_index = 0

    while chunk_start_index < total_sentence_count:
        chunk_end_index = chunk_start_index
        chunk_length = 0

        while chunk_end_index < total_sentence_count:
            next_sentence_length = len(sentences[chunk_end_index].text) + 1
            is_first_sentence_in_chunk = chunk_end_index == chunk_start_index
            fits_in_chunk = chunk_length + next_sentence_length <= max_chunk_chars
            if is_first_sentence_in_chunk or fits_in_chunk:
                chunk_length = chunk_length + next_sentence_length
                chunk_end_index = chunk_end_index + 1
            else:
                break

        first_sentence = sentences[chunk_start_index]
        chunk_id = first_sentence.doc_id + ".C" + str(len(chunks) + 1)
        chunk = Chunk(
            chunk_id=chunk_id,
            doc_id=first_sentence.doc_id,
            title=first_sentence.title,
            sentences=tuple(sentences[chunk_start_index:chunk_end_index]),
        )
        chunks.append(chunk)

        if chunk_end_index >= total_sentence_count:
            break

        next_start_with_overlap = chunk_end_index - overlap_sentence_count
        minimum_next_start = chunk_start_index + 1
        chunk_start_index = max(next_start_with_overlap, minimum_next_start)

    return chunks
