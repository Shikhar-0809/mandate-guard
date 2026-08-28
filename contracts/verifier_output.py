"""T2 verifier output schema: closed evidence record, no policy authority."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.verdict import VerdictState


@dataclass(frozen=True)
class EvidenceSpan:
    field: str
    text: str
    relevance: str

    def __post_init__(self) -> None:
        if not self.field:
            raise ValueError("field must not be empty")
        if not self.text:
            raise ValueError("text must not be empty")
        if not self.relevance:
            raise ValueError("relevance must not be empty")


@dataclass(frozen=True)
class VerifierOutput:
    verdict: VerdictState
    evidence_spans: tuple[EvidenceSpan, ...]
    confidence: float
    invoked: bool
    degraded_reason: str | None = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0.0, 1.0]")
        if not self.invoked and self.evidence_spans != ():
            raise ValueError("degraded VerifierOutput must have empty evidence_spans")
        if not self.invoked and self.degraded_reason is None:
            raise ValueError("degraded VerifierOutput must have a degraded_reason")
        if not self.invoked and self.degraded_reason == "":
            raise ValueError("degraded_reason must not be empty")
        if self.invoked and self.degraded_reason is not None:
            raise ValueError("invoked VerifierOutput must not have a degraded_reason")
