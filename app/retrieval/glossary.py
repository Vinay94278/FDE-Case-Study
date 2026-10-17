"""Domain glossary: synonyms and key entities.

The glossary is data, not code, so the support team can maintain it:
    synonyms      admin wording -> wording used in the docs ("add a user" -> "invite")
    key_entities  specific things a question can name (plans, file formats, integrations).
                  If a question names one and the answer passage does not mention it,
                  the answer is at best partial ("Is SSO on the Growth plan?").
"""
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Pattern, Tuple

from app.core.exceptions import ConfigurationException

logger = logging.getLogger(__name__)


@dataclass
class Glossary:
    replacement_rules: List[Tuple[Pattern, str]] = field(default_factory=list)
    key_entities: List[str] = field(default_factory=list)

    @staticmethod
    def empty() -> "Glossary":
        return Glossary()


def _build_word_pattern(phrase: str) -> Pattern:
    """Match the phrase as whole words, ignoring case."""
    return re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)


def _read_alias_length(rule: Tuple[str, str]) -> int:
    alias_phrase = rule[0]
    return len(alias_phrase)


def load_glossary(glossary_path: Path) -> Glossary:
    if not glossary_path.exists():
        logger.warning("Glossary file %s not found; synonyms and entity checks are off", glossary_path)
        return Glossary.empty()

    try:
        with open(glossary_path, encoding="utf-8") as glossary_file:
            raw_glossary = json.load(glossary_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationException(
            technical_message="Glossary file " + str(glossary_path) + " cannot be read: " + str(error)
        ) from error

    raw_synonyms: Dict[str, List[str]] = raw_glossary.get("synonyms", {})
    alias_rules: List[Tuple[str, str]] = []
    for canonical_phrase, alias_phrases in raw_synonyms.items():
        for alias_phrase in alias_phrases:
            alias_rules.append((alias_phrase, canonical_phrase))

    # Longest aliases first, so "add a new user" is replaced before "add user".
    alias_rules.sort(key=_read_alias_length, reverse=True)

    replacement_rules = []
    for alias_phrase, canonical_phrase in alias_rules:
        replacement_rules.append((_build_word_pattern(alias_phrase), canonical_phrase))

    key_entities = []
    raw_entity_groups: Dict[str, List[str]] = raw_glossary.get("key_entities", {})
    for entity_group in raw_entity_groups.values():
        for entity_name in entity_group:
            key_entities.append(entity_name.strip().lower())

    logger.info("Glossary loaded: %d synonym rules, %d key entities", len(replacement_rules), len(key_entities))
    return Glossary(replacement_rules=replacement_rules, key_entities=key_entities)


class QueryExpander:
    """Rewrites admin wording into documentation wording, for search only.

    The LLM still sees the admin's original question; only retrieval and the
    extractive answerer use the expanded text.
    """

    def __init__(self, glossary: Glossary):
        self.glossary = glossary

    def expand(self, question_text: str) -> str:
        expanded_text = question_text
        for alias_pattern, canonical_phrase in self.glossary.replacement_rules:
            expanded_text = alias_pattern.sub(canonical_phrase, expanded_text)
        return expanded_text
