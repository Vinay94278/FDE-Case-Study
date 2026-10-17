"""Results returned by the guard checks (relevance gate and grounding verifier)."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GateDecision:
    passed: bool
    explanation: str


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    failure_reason: Optional[str] = None
