"""Verdict: frozen decision record from the mandate guard pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class VerdictState(str, Enum):
    ALLOW = "ALLOW"
    HOLD = "HOLD"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class Verdict:
    verdict: VerdictState
    reason_code: str
    agent_request_id: str
    mandate_id: str
    t0_triggered: bool
    frozen_at: datetime
    t1_score: float | None = None
    t2_evidence: str | None = None
    policy_version: str | None = None
    t1_model_hash: str | None = None
    t2_model_id: str | None = None

    def __post_init__(self) -> None:
        if not self.reason_code:
            raise ValueError("reason_code must not be empty")
        if not self.agent_request_id:
            raise ValueError("agent_request_id must not be empty")
        if not self.mandate_id:
            raise ValueError("mandate_id must not be empty")
        if self.verdict == VerdictState.ALLOW and self.t0_triggered:
            raise ValueError("ALLOW verdict is inconsistent with a triggered T0 rule")
        if self.t1_score is not None and not (0.0 <= self.t1_score <= 1.0):
            raise ValueError("t1_score must be in [0.0, 1.0]")
        if self.policy_version is not None and not self.policy_version:
            raise ValueError("policy_version must not be empty if set")
        if self.t1_model_hash is not None and not self.t1_model_hash:
            raise ValueError("t1_model_hash must not be empty if set")
        if self.t2_model_id is not None and not self.t2_model_id:
            raise ValueError("t2_model_id must not be empty if set")
