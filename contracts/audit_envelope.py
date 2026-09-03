"""Audit envelope: hash-chained integrity wrapper around a verdict."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from contracts.verdict import Verdict


@dataclass(frozen=True)
class AuditEnvelope:
    envelope_id: str
    verdict: Verdict
    prev_envelope_hash: str | None
    envelope_hash: str

    def __post_init__(self) -> None:
        if not self.envelope_id:
            raise ValueError("envelope_id must not be empty")
        if not self.envelope_hash:
            raise ValueError("envelope_hash must not be empty")

    @classmethod
    def create(
        cls,
        envelope_id: str,
        verdict: Verdict,
        prev_envelope_hash: str | None,
    ) -> AuditEnvelope:
        payload = cls._canonical_payload(envelope_id, verdict, prev_envelope_hash)
        envelope_hash = hashlib.sha256(payload).hexdigest()
        return cls(
            envelope_id=envelope_id,
            verdict=verdict,
            prev_envelope_hash=prev_envelope_hash,
            envelope_hash=envelope_hash,
        )

    @staticmethod
    def _canonical_payload(
        envelope_id: str,
        verdict: Verdict,
        prev_envelope_hash: str | None,
    ) -> bytes:
        # Deterministic serialisation — field order is fixed, not dict-keyed.
        # This must never change once in production; changing it breaks the
        # chain. Any future field addition requires a new envelope version.
        parts = [
            envelope_id,
            verdict.verdict.value,
            verdict.reason_code,
            verdict.agent_request_id,
            verdict.mandate_id,
            str(verdict.t0_triggered),
            verdict.frozen_at.isoformat(),
            "" if verdict.t1_score is None else str(verdict.t1_score),
            "" if verdict.t2_evidence is None else verdict.t2_evidence,
            # v2: policy_version, t1_model_hash, t2_model_id added after t2_evidence
            "" if verdict.policy_version is None else verdict.policy_version,
            "" if verdict.t1_model_hash is None else verdict.t1_model_hash,
            "" if verdict.t2_model_id is None else verdict.t2_model_id,
            "" if prev_envelope_hash is None else prev_envelope_hash,
        ]
        return "|".join(parts).encode("utf-8")

    def verify_hash(self) -> bool:
        payload = self._canonical_payload(
            self.envelope_id,
            self.verdict,
            self.prev_envelope_hash,
        )
        return hashlib.sha256(payload).hexdigest() == self.envelope_hash
