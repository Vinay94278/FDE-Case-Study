"""Prompts live in versioned text files, not inside Python code.

Changing a prompt is then a reviewable diff, and the version name is returned in
debug output so each answer can be traced to the prompt that produced it.
"""
from pathlib import Path

from app.core.exceptions import ConfigurationException

PROMPTS_DIRECTORY = Path(__file__).resolve().parent / "prompts"

ANSWER_PROMPT_NAME = "answer_system_prompt_v1"
FOLLOWUP_REWRITE_PROMPT_NAME = "followup_rewrite_prompt_v1"


def load_prompt(prompt_name: str) -> str:
    prompt_path = PROMPTS_DIRECTORY / (prompt_name + ".txt")
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ConfigurationException(
            technical_message="Prompt file missing: " + str(prompt_path)
        ) from error
