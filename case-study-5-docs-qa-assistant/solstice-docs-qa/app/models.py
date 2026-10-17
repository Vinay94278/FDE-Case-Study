"""API request/response schemas."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Status = Literal["answered", "partial", "not_covered"]


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)

    @field_validator("question")
    @classmethod
    def clean(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 3:
            raise ValueError("Question is too short")
        return v


class Citation(BaseModel):
    sentence_id: str
    doc_id: str
    title: str
    text: str


class RelatedDoc(BaseModel):
    doc_id: str
    title: str


class AskResponse(BaseModel):
    question: str
    status: Status
    answer: str
    citations: list[Citation] = []
    related_docs: list[RelatedDoc] = []
    mode: str  # "llm", "extractive", or "extractive_fallback"
    reason: str  # short machine-readable reason for the decision
    latency_ms: int
    debug: dict = {}


class FeedbackRequest(BaseModel):
    question: str = Field(..., max_length=500)
    status: Status
    helpful: bool
    comment: str | None = Field(default=None, max_length=500)
