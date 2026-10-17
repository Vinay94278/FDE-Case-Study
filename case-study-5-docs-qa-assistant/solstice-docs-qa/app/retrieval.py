"""Hybrid retrieval: BM25 keyword search + optional embeddings, fused with
Reciprocal Rank Fusion (RRF).

- BM25 is exact on product words ("CSV", "SSO", "429") and needs no model.
- Embeddings catch paraphrases ("add a user" vs "invite a team member").
- RRF combines the two rankings without having to compare raw scores, which
  are on different scales.

Embeddings are optional: if sentence-transformers is not installed or the model
cannot be downloaded, retrieval falls back to BM25 only and says so in /health.
"""
import logging
import math
from collections import Counter
from dataclasses import dataclass

from typing import Optional

from .ingest import Chunk
from .textproc import terms

log = logging.getLogger(__name__)
RRF_K = 60


class BM25:
    def __init__(self, corpus_terms: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(t) for t in corpus_terms]
        self.lengths = [len(t) for t in corpus_terms]
        self.n = len(corpus_terms)
        self.avg_len = (sum(self.lengths) / self.n) if self.n else 0.0
        self.df = Counter()
        for t in corpus_terms:
            self.df.update(set(t))

    def idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def scores(self, query_terms: list[str]) -> list[float]:
        out = []
        for tf, length in zip(self.tf, self.lengths):
            s = 0.0
            for term in set(query_terms):
                f = tf.get(term, 0)
                if f:
                    norm = f + self.k1 * (1 - self.b + self.b * length / (self.avg_len or 1))
                    s += self.idf(term) * f * (self.k1 + 1) / norm
            out.append(s)
        return out


class EmbeddingIndex:
    """Thin wrapper so the rest of the code does not care whether embeddings exist."""

    def __init__(self, texts: list[str], model_name: str, enabled: bool):
        self.available = False
        self.status = "disabled by config"
        if not enabled:
            return
        try:
            from sentence_transformers import SentenceTransformer  # optional dependency
            self.model = SentenceTransformer(model_name)
            self.matrix = self.model.encode(texts, normalize_embeddings=True)
            self.available = True
            self.status = f"on ({model_name})"
        except Exception as exc:  # missing package, no network, etc.
            self.status = f"unavailable, using BM25 only ({type(exc).__name__})"
            log.warning("Embeddings %s", self.status)

    def cosine(self, query: str) -> list[float]:
        q = self.model.encode([query], normalize_embeddings=True)[0]
        return [float(x) for x in self.matrix @ q]


@dataclass
class Hit:
    chunk: Chunk
    rrf: float
    bm25: float
    cosine: Optional[float]
    term_coverage: float  # share of the question's informative terms found in this chunk


class Retriever:
    def __init__(self, chunks: list[Chunk], embedding_model: str, embeddings_enabled: bool):
        self.chunks = chunks
        self.chunk_terms = [terms(c.index_text) for c in chunks]
        self.chunk_term_sets = [set(t) for t in self.chunk_terms]
        self.bm25 = BM25(self.chunk_terms)
        self.embeddings = EmbeddingIndex([c.index_text for c in chunks], embedding_model, embeddings_enabled)

    def search(self, question: str, top_k: int = 4) -> tuple[list[Hit], list[str]]:
        q_terms = list(dict.fromkeys(terms(question)))
        bm25 = self.bm25.scores(q_terms)
        cos = self.embeddings.cosine(question) if self.embeddings.available else None

        rrf = [0.0] * len(self.chunks)
        bm25_order = sorted((i for i, s in enumerate(bm25) if s > 0), key=lambda i: -bm25[i])
        for rank, i in enumerate(bm25_order):
            rrf[i] += 1 / (RRF_K + rank + 1)
        if cos is not None:
            for rank, i in enumerate(sorted(range(len(cos)), key=lambda i: -cos[i])):
                rrf[i] += 1 / (RRF_K + rank + 1)

        hits = []
        for i in sorted(range(len(self.chunks)), key=lambda i: -rrf[i]):
            if rrf[i] == 0:
                continue
            matched = sum(1 for t in q_terms if t in self.chunk_term_sets[i])
            hits.append(Hit(
                chunk=self.chunks[i],
                rrf=round(rrf[i], 5),
                bm25=round(bm25[i], 3),
                cosine=round(cos[i], 3) if cos is not None else None,
                term_coverage=round(matched / len(q_terms), 3) if q_terms else 0.0,
            ))
        return hits[:top_k], q_terms
