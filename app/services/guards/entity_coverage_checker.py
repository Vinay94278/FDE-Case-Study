"""Partial-coverage check for extractive mode (no LLM).

If the question names a specific thing (a plan, file format, integration, billing
term) and the passage chosen as the answer never mentions it, the passage does
not really answer the question:

    "Is SSO available on the Growth plan?"  ->  passage: "Enterprise plans support SSO..."
    "growth" is missing                      ->  partial, not answered

The entity list comes from data/glossary.json, so the client can extend it.
"""
import re
from typing import List

from app.retrieval.glossary import Glossary


class EntityCoverageChecker:
    def __init__(self, glossary: Glossary):
        self.key_entities = glossary.key_entities

    def find_entities_in_text(self, text: str) -> List[str]:
        found_entities = []
        for entity_name in self.key_entities:
            entity_pattern = r"\b" + re.escape(entity_name) + r"\b"
            if re.search(entity_pattern, text, re.IGNORECASE):
                found_entities.append(entity_name)
        return found_entities

    def find_missing_entities(self, question_text: str, evidence_text: str) -> List[str]:
        """Entities named in the question that the evidence text never mentions."""
        missing_entities = []
        evidence_entities = set(self.find_entities_in_text(evidence_text))
        for entity_name in self.find_entities_in_text(question_text):
            if entity_name not in evidence_entities:
                missing_entities.append(entity_name)
        return missing_entities
