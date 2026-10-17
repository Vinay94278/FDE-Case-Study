"""Constants shared across layers. User-facing wording lives here so it stays consistent."""

API_VERSION_PREFIX = "/api/v1"
REQUEST_ID_HEADER = "X-Request-ID"

RESPONSE_STATUS_SUCCESS = "success"
RESPONSE_STATUS_ERROR = "error"

NOT_COVERED_MESSAGE = "I don't have an answer for that in the documentation."
LLM_UNAVAILABLE_MESSAGE = (
    "I can't verify an answer from the documentation right now. "
    "Please try again shortly, or see the related articles."
)
NOT_COVERED_PREFIX = "Not covered in the documentation: "

ANSWERED_ENVELOPE_MESSAGE = "Answer found in the documentation."
PARTIAL_ENVELOPE_MESSAGE = "The documentation partly covers this question."
NOT_COVERED_ENVELOPE_MESSAGE = "The documentation does not cover this question."
UNAVAILABLE_ENVELOPE_MESSAGE = "An answer could not be verified right now."

MAX_QUESTION_LENGTH = 500
MIN_QUESTION_LENGTH = 3
MAX_HISTORY_TURNS_ACCEPTED = 10
MAX_HISTORY_ANSWER_LENGTH = 2000
MAX_RELATED_DOCUMENTS = 2
MAX_EXTRACTIVE_SENTENCES = 2
