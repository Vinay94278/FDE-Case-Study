"""Text helpers shared by retrieval and the extractive fallback."""
import re

import snowballstemmer

_STEMMER = snowballstemmer.stemmer("english")

# Generic English stopwords plus question words. "solstice" is a domain stopword:
# it is the product name, appears in every question context, and carries no meaning
# for which article answers the question.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "of", "to", "in", "on",
    "at", "by", "for", "with", "from", "into", "about", "as", "is", "are", "was", "were",
    "be", "been", "being", "am", "do", "does", "did", "doing", "have", "has", "had",
    "i", "me", "my", "we", "our", "you", "your", "it", "its", "they", "their", "them",
    "this", "that", "these", "those", "there", "here", "what", "which", "who", "whom",
    "how", "when", "where", "why", "can", "could", "should", "would", "will", "shall",
    "may", "might", "must", "any", "some", "all", "not", "no", "yes", "just", "also",
    "get", "got", "use", "using", "used", "want", "need", "please", "tell", "know",
    "s", "t", "isn", "aren", "don", "doesn", "didn", "won", "can't", "cant", "im",
    "before", "after", "up", "out", "too", "very", "much", "many", "more", "most",
    "solstice",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens (keeps numbers)."""
    return _TOKEN_RE.findall(text.lower().replace(",", ""))


def terms(text: str) -> list[str]:
    """Informative, stemmed terms: stopwords removed, light stemming applied."""
    return [_STEMMER.stemWord(t) for t in tokenize(text) if t not in STOPWORDS]


_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    """All numbers in a text, normalised ("10,000" -> "10000", "2.0." -> "2.0")."""
    return {m.group(0).replace(",", "").rstrip(".") for m in _NUMBER_RE.finditer(text)}
