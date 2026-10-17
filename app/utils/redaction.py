"""Remove personal data from text before it is stored in the query log."""
import re

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
LONG_NUMBER_PATTERN = re.compile(r"\b\d{6,}\b")


def redact_personal_data(text: str) -> str:
    """Replace email addresses and long digit runs (account, phone, card numbers)."""
    text_without_emails = EMAIL_PATTERN.sub("[email]", text)
    return LONG_NUMBER_PATTERN.sub("[number]", text_without_emails)
