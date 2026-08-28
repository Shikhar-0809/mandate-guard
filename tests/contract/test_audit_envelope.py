"""Tests for contracts.audit_envelope.AuditEnvelope."""

from __future__ import annotations

from datetime import datetime

import pytest

from contracts.audit_envelope import AuditEnvelope
from contracts.verdict import Verdict, VerdictState

FROZEN_AT = datetime(2026, 6, 15, 10, 30, 0)  # noqa: DTZ001

BASE_VERDICT = Verdict(
    verdict=VerdictState.ALLOW,
    reason_code="OK",
    agent_request_id="req-001",
    mandate_id="mandate-001",
    t0_triggered=False,
    frozen_at=FROZEN_AT,
)


def test_create_succeeds_and_verify_hash_returns_true() -> None:
    envelope = AuditEnvelope.create(
        envelope_id="env-001",
        verdict=BASE_VERDICT,
        prev_envelope_hash=None,
    )
    assert envelope.verify_hash() is True


def test_tampered_envelope_hash_fails_verification() -> None:
    envelope = AuditEnvelope.create(
        envelope_id="env-002",
        verdict=BASE_VERDICT,
        prev_envelope_hash=None,
    )
    object.__setattr__(envelope, "envelope_hash", "deadbeef")
    assert envelope.verify_hash() is False


def test_tampered_verdict_fails_verification() -> None:
    envelope = AuditEnvelope.create(
        envelope_id="env-003",
        verdict=BASE_VERDICT,
        prev_envelope_hash=None,
    )
    tampered_verdict = Verdict(
        verdict=VerdictState.ALLOW,
        reason_code="TAMPERED",
        agent_request_id="req-001",
        mandate_id="mandate-001",
        t0_triggered=False,
        frozen_at=FROZEN_AT,
    )
    object.__setattr__(envelope, "verdict", tampered_verdict)
    assert envelope.verify_hash() is False


def test_hash_chaining_links_envelopes() -> None:
    first = AuditEnvelope.create(
        envelope_id="env-first",
        verdict=BASE_VERDICT,
        prev_envelope_hash=None,
    )
    second = AuditEnvelope.create(
        envelope_id="env-second",
        verdict=BASE_VERDICT,
        prev_envelope_hash=first.envelope_hash,
    )
    assert second.prev_envelope_hash == first.envelope_hash


def test_first_envelope_has_no_previous_hash() -> None:
    envelope = AuditEnvelope.create(
        envelope_id="env-root",
        verdict=BASE_VERDICT,
        prev_envelope_hash=None,
    )
    assert envelope.prev_envelope_hash is None


def test_empty_envelope_id_raises() -> None:
    with pytest.raises(ValueError):
        AuditEnvelope(
            envelope_id="",
            verdict=BASE_VERDICT,
            prev_envelope_hash=None,
            envelope_hash="abc123",
        )


def test_direct_construction_with_mismatched_hash_fails_verification() -> None:
    envelope = AuditEnvelope(
        envelope_id="env-direct",
        verdict=BASE_VERDICT,
        prev_envelope_hash=None,
        envelope_hash="not-the-real-hash",
    )
    assert envelope.verify_hash() is False
