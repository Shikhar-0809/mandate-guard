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

import json as _json
import os
from dataclasses import dataclass
from typing import Any

import requests as _requests

from contracts import (
    CartMandate,
    EvidenceSpan,
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


def _call_ollama(
    intent: IntentMandate,
    cart: CartMandate,
    merchant_catalog_snippet: UntrustedBlob | None,
    agent_rationale: UntrustedBlob | None,
) -> VerifierOutput:
    """
    Call the local Ollama instance with a structured prompt.
    The system prompt contains only instructions — never untrusted
    content. Untrusted content (catalog snippet, agent rationale)
    is passed in the user message as labeled data fields, never
    interpolated into instructions.
    Parse failure or network error always returns HOLD, never ALLOW.
    """
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

    system_prompt = (
        "You are a payment fraud detector analyzing mandate deviation. "
        "Determine whether the cart matches the stated purchase intent. "
        "Respond with ONLY valid JSON, no markdown, no explanation: "
        '{"verdict": "ALLOW" or "HOLD" or "BLOCK", '
        '"evidence": "one sentence", '
        '"confidence": 0.0 to 1.0}'
    )

    cart_summary = "; ".join(
        f"{item.quantity}x {item.name} @ "
        f"{item.unit_price.minor_units} {item.unit_price.currency}"
        for item in cart.items
    )
    user_parts = [
        f"Purchase intent: {intent.purchase_intent or '(not stated)'}",
        f"Cart: {cart_summary}",
        f"Merchant: {cart.mandate_id}",
        f"Total: {cart.total.minor_units} {cart.total.currency}",
    ]
    if merchant_catalog_snippet is not None:
        user_parts.append(
            f"Catalog data [{merchant_catalog_snippet.source}]: "
            f"{merchant_catalog_snippet.content}"
        )
    if agent_rationale is not None:
        user_parts.append(
            f"Agent rationale [{agent_rationale.source}]: {agent_rationale.content}"
        )
    user_message = "\n".join(user_parts)

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "options": {"temperature": 0.0},
    }

    try:
        response = _requests.post(
            f"{ollama_host}/api/chat",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        raw = response.json()
        content = raw["message"]["content"].strip()

        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        parsed = _json.loads(content)
        verdict_str = str(parsed.get("verdict", "HOLD")).upper()
        verdict = VerdictState(verdict_str)
        evidence_text = str(parsed.get("evidence", ""))
        confidence = float(parsed.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        span = (
            EvidenceSpan(
                field="cart_vs_intent",
                text=evidence_text[:200] if evidence_text else "none",
                relevance="LLM semantic analysis",
            )
            if evidence_text
            else None
        )

        return VerifierOutput(
            verdict=verdict,
            evidence_spans=(span,) if span else (),
            confidence=confidence,
            invoked=True,
            degraded_reason=None,
        )

    except _requests.exceptions.ConnectionError:
        return VerifierOutput(
            verdict=VerdictState.HOLD,
            evidence_spans=(),
            confidence=0.0,
            invoked=False,
            degraded_reason="Ollama unreachable at " + ollama_host,
        )
    except Exception:  # noqa: BLE001
        return VerifierOutput(
            verdict=VerdictState.HOLD,
            evidence_spans=(),
            confidence=0.0,
            invoked=False,
            degraded_reason="T2 parse or network error — degraded",
        )


def verify(
    intent: IntentMandate,
    cart: CartMandate,
    merchant_catalog_snippet: UntrustedBlob | None,
    agent_rationale: UntrustedBlob | None,
    config: T2Config,
) -> VerifierOutput:
    if not config.t2_enabled:
        return _DEGRADED_OUTPUT
    return _call_ollama(
        intent,
        cart,
        merchant_catalog_snippet,
        agent_rationale,
    )
