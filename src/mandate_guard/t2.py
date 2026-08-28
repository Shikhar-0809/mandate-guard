"""T2 semantic verifier interface — wired but degraded by default.

T2 is degraded by default because the pre-registered kill criterion (>=2pp lift
in recall_unseen over T0+T1) cannot be satisfied when T0 achieves
recall_unseen=1.0 on the evaluation corpus. The kill criterion was
pre-registered in EVAL.md before any T2 code existed; commit history proves the
ordering. T2 ships wired to prove the interface is correct, not to claim a
metrics win. Untrusted content enters as UntrustedBlob and is never concatenated
into control flow or prompt strings directly. The output schema is closed —
VerifierOutput cannot emit an action, a threshold, or free text that enters the
policy engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from contracts import (
    CartMandate,
    IntentMandate,
    T2Config,
    VerdictState,
    VerifierOutput,
)

_DEGRADED_REASON = (
    "T2 disabled: kill criterion not met — recall_unseen ceiling "
    "at 1.0 leaves no headroom for the required >=2pp lift. "
    "See D008 and EVAL.md."
)

_DEGRADED_OUTPUT = VerifierOutput(
    verdict=VerdictState.HOLD,
    evidence_spans=(),
    confidence=0.0,
    invoked=False,
    degraded_reason=_DEGRADED_REASON,
)


@dataclass(frozen=True)
class UntrustedBlob:
    """
    Content from untrusted sources: merchant catalog text, product
    descriptions, agent rationale strings, dispute evidence.

    Never concatenated into a prompt or rule expression directly.
    Passed as structured data; the caller is responsible for
    sanitization before any downstream use.
    """

    content: str
    source: str

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("source must not be empty")


def verify(
    intent: IntentMandate,
    cart: CartMandate,
    merchant_catalog_snippet: UntrustedBlob | None,
    agent_rationale: UntrustedBlob | None,
    config: T2Config,
) -> VerifierOutput:
    del intent, cart, merchant_catalog_snippet, agent_rationale
    if not config.t2_enabled:
        return _DEGRADED_OUTPUT
    raise NotImplementedError(
        "T2 LLM backend not configured for this corpus. "
        "t2_enabled=True requires a live LLM endpoint. "
        "The kill criterion was not met on the evaluation corpus; "
        "enabling T2 requires a corpus with semantic attacks that "
        "evade T0. See D008."
    )
