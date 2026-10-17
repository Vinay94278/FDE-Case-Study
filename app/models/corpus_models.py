"""Domain models for the documentation corpus.

These are internal models, separate from the API DTOs. DTOs describe what goes over
the wire; models describe what the business logic works with.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Document:
    """One documentation article as loaded from a source."""

    doc_id: str
    title: str
    content: str
    source_name: str
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Sentence:
    """One sentence of an article. Its ID (for example "D-01.S6") is what answers cite."""

    sentence_id: str
    doc_id: str
    title: str
    position: int
    text: str


@dataclass(frozen=True)
class Chunk:
    """A group of consecutive sentences used as the unit of search."""

    chunk_id: str
    doc_id: str
    title: str
    sentences: Tuple[Sentence, ...]

    def get_text(self) -> str:
        sentence_texts = []
        for sentence in self.sentences:
            sentence_texts.append(sentence.text)
        return " ".join(sentence_texts)

    def get_searchable_text(self) -> str:
        """Title plus body. The title is a strong signal ("Resetting Your Password")."""
        return self.title + ". " + self.get_text()

    def get_sentence_ids(self) -> List[str]:
        sentence_ids = []
        for sentence in self.sentences:
            sentence_ids.append(sentence.sentence_id)
        return sentence_ids
