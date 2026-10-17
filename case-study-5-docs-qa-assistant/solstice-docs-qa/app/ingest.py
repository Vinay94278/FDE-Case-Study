"""Load docs and split them into sentences and overlapping chunks.

Why not fixed-size character chunks (the starter kit approach)?
- `len(text) // 400` silently drops the end of every doc, and docs shorter than
  400 characters produce no chunks at all. In the seed data that loses the exact
  facts asked about (15-minute link expiry, 10,000-row cap, 60 req/min limit).
- Character cuts split words and sentences, which breaks citations.

Here every sentence gets a stable ID (e.g. "D-01.S7") so answers can cite the exact
sentence and the citation can be verified in code.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(`])")


@dataclass(frozen=True)
class Sentence:
    id: str
    doc_id: str
    title: str
    index: int
    text: str


@dataclass(frozen=True)
class Chunk:
    id: str
    doc_id: str
    title: str
    sentences: tuple[Sentence, ...]

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.sentences)

    @property
    def index_text(self) -> str:
        # The title is indexed too: "Resetting Your Password" is a strong signal.
        return f"{self.title}. {self.text}"


def load_docs(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    docs = data.get("docs", [])
    for doc in docs:
        missing = {"doc_id", "title", "content"} - doc.keys()
        if missing:
            raise ValueError(f"Doc is missing fields {missing}: {doc}")
    return docs


def split_sentences(text: str) -> list[str]:
    return [p.strip() for p in _SENTENCE_SPLIT.split(text.strip()) if p.strip()]


def doc_sentences(doc: dict) -> list[Sentence]:
    return [
        Sentence(id=f"{doc['doc_id']}.S{i + 1}", doc_id=doc["doc_id"], title=doc["title"], index=i, text=t)
        for i, t in enumerate(split_sentences(doc["content"]))
    ]


def build_chunks(sentences: list[Sentence], max_chars: int = 400, overlap: int = 1) -> list[Chunk]:
    """Pack whole sentences into chunks of up to ~max_chars, overlapping by `overlap`
    sentences. A sentence longer than max_chars becomes its own chunk. The end of the
    doc is always included."""
    if not sentences:
        return []
    chunks, start, n = [], 0, len(sentences)
    while start < n:
        end, length = start, 0
        while end < n and (end == start or length + len(sentences[end].text) + 1 <= max_chars):
            length += len(sentences[end].text) + 1
            end += 1
        first = sentences[start]
        chunks.append(Chunk(id=f"{first.doc_id}.C{len(chunks) + 1}", doc_id=first.doc_id,
                            title=first.title, sentences=tuple(sentences[start:end])))
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_corpus(docs: list[dict], max_chars: int = 400, overlap: int = 1):
    """Return (sentences_by_id, chunks) for all docs."""
    sentences_by_id: dict[str, Sentence] = {}
    chunks: list[Chunk] = []
    for doc in docs:
        sents = doc_sentences(doc)
        sentences_by_id.update({s.id: s for s in sents})
        chunks.extend(build_chunks(sents, max_chars, overlap))
    return sentences_by_id, chunks
