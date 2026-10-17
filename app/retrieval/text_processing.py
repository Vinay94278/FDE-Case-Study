"""Text helpers shared by search, the guards and the extractive answerer."""
import re
from typing import List, Set

import snowballstemmer

ENGLISH_STEMMER = snowballstemmer.stemmer("english")

# Generic English stopwords and question words. Domain stopwords:
#   "solstice"   the product name; it says nothing about which article answers the question
#   "available"  question filler ("Is X available on Y?"); the subject is X and Y, not "available"
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "of", "to", "in", "on",
    "at", "by", "for", "with", "from", "into", "about", "as", "is", "are", "was", "were",
    "be", "been", "being", "am", "do", "does", "did", "doing", "have", "has", "had",
    "i", "me", "my", "we", "our", "you", "your", "it", "its", "they", "their", "them",
    "this", "that", "these", "those", "there", "here", "what", "which", "who", "whom",
    "how", "when", "where", "why", "can", "could", "should", "would", "will", "shall",
    "may", "might", "must", "any", "some", "all", "not", "no", "yes", "just", "also",
    "get", "got", "use", "using", "used", "want", "need", "please", "tell", "know",
    "s", "t", "isn", "aren", "don", "doesn", "didn", "won", "cant", "im",
    "before", "after", "up", "out", "too", "very", "much", "many", "more", "most",
    "solstice", "available",
}

WORD_PATTERN = re.compile(r"[a-z0-9]+")
NUMBER_PATTERN = re.compile(r"\d[\d,]*(?:\.\d+)?")


def tokenize(text: str) -> List[str]:
    """Lowercase words and numbers. Thousands separators are removed first ("10,000" -> "10000")."""
    lowercase_text = text.lower().replace(",", "")
    return WORD_PATTERN.findall(lowercase_text)


def extract_search_terms(text: str) -> List[str]:
    """Informative stemmed terms in order: stopwords removed, "expires" -> "expir"."""
    search_terms = []
    for word in tokenize(text):
        if word in STOPWORDS:
            continue
        search_terms.append(ENGLISH_STEMMER.stemWord(word))
    return search_terms


def extract_unique_search_terms(text: str) -> List[str]:
    """Same as extract_search_terms but without duplicates, order kept."""
    unique_terms = []
    seen_terms = set()
    for search_term in extract_search_terms(text):
        if search_term not in seen_terms:
            seen_terms.add(search_term)
            unique_terms.append(search_term)
    return unique_terms


def extract_numbers(text: str) -> Set[str]:
    """All numbers in a text, normalised: "10,000" -> "10000", "2.0." -> "2.0"."""
    normalized_numbers = set()
    for number_match in NUMBER_PATTERN.finditer(text):
        number_text = number_match.group(0).replace(",", "").rstrip(".")
        normalized_numbers.add(number_text)
    return normalized_numbers
