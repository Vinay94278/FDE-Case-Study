"""Split a multi-part question into its parts (used by extractive mode).

"How do I invite a teammate, and what are the rules for a new password?"
    -> ["How do I invite a teammate", "what are the rules for a new password?"]
"""
import re
from typing import List

QUESTION_START_WORDS = r"(?:what|how|when|where|why|which|who|can|could|is|are|do|does|will)"
AND_BEFORE_NEW_QUESTION = re.compile(r",?\s+and\s+(?=" + QUESTION_START_WORDS + r"\b)", re.IGNORECASE)
QUESTION_MARK_BETWEEN_QUESTIONS = re.compile(r"\?\s+(?=\S)")


def split_question_into_parts(question_text: str) -> List[str]:
    question_parts = []
    for question_mark_part in QUESTION_MARK_BETWEEN_QUESTIONS.split(question_text):
        for and_part in AND_BEFORE_NEW_QUESTION.split(question_mark_part):
            cleaned_part = and_part.strip(" ,")
            if len(cleaned_part) >= 3:
                question_parts.append(cleaned_part)

    if len(question_parts) == 0:
        return [question_text]
    return question_parts
