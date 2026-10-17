"""Turn an LLM reply into a JSON object, tolerating ```json fences and stray text."""
import json
import re
from typing import Any, Dict, Optional

from app.core.exceptions import LlmResponseFormatException

CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$")


def parse_json_object(reply_text: Optional[str]) -> Dict[str, Any]:
    if reply_text is None:
        raise LlmResponseFormatException(technical_message="LLM reply was empty")

    trimmed_text = CODE_FENCE_PATTERN.sub("", reply_text.strip())
    object_start = trimmed_text.find("{")
    object_end = trimmed_text.rfind("}")
    if object_start == -1 or object_end == -1:
        raise LlmResponseFormatException(technical_message="LLM reply contained no JSON object")

    json_text = trimmed_text[object_start:object_end + 1]
    try:
        parsed_value = json.loads(json_text)
    except json.JSONDecodeError as error:
        raise LlmResponseFormatException(technical_message="LLM reply was invalid JSON: " + str(error)) from error

    if not isinstance(parsed_value, dict):
        raise LlmResponseFormatException(technical_message="LLM reply JSON was not an object")
    return parsed_value
