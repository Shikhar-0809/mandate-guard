"""Offline tests for committed payment fixtures."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Protocol, cast

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "fixtures" / "payment_success.json"
CHECK_IDENTIFIERS_SCRIPT = PROJECT_ROOT / "scripts" / "check_identifiers.py"
FIXTURE_REDACT_SCRIPT = PROJECT_ROOT / "scripts" / "fixture_redact.py"


class _CheckIdentifiers(Protocol):
    class Policy:
        DENY_SECRETS_AND_PII: object

    def scan_file(
        self, path: Path, policy: object
    ) -> tuple[list[object], str | None]: ...


class _FixtureRedact(Protocol):
    TOP_LEVEL_ALLOWLIST: frozenset[str]

    def redact_payment(self, payment: dict[str, Any]) -> dict[str, Any]: ...


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_check_identifiers_raw = _load_module("check_identifiers", CHECK_IDENTIFIERS_SCRIPT)
check_identifiers = cast(_CheckIdentifiers, _check_identifiers_raw)
_fixture_redact_raw = _load_module("fixture_redact", FIXTURE_REDACT_SCRIPT)
fixture_redact = cast(_FixtureRedact, _fixture_redact_raw)


@pytest.fixture
def payment_fixture() -> dict[str, Any]:
    if not FIXTURE_PATH.is_file():
        pytest.skip(
            "fixtures/payment_success.json not present — run scripts/checkout_local.py"
        )
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        pytest.fail("fixture root must be a JSON object")
    return payload


def test_fixture_top_level_keys_are_allowlisted_subset(
    payment_fixture: dict[str, Any],
) -> None:
    allowed = set(fixture_redact.TOP_LEVEL_ALLOWLIST) | {"card", "notes"}
    extra = set(payment_fixture) - allowed
    assert not extra, f"unexpected top-level keys: {sorted(extra)}"


def test_fixture_passes_identifier_scanner(payment_fixture: dict[str, Any]) -> None:
    del payment_fixture
    findings, skip_message = check_identifiers.scan_file(
        FIXTURE_PATH,
        check_identifiers.Policy.DENY_SECRETS_AND_PII,
    )
    assert skip_message is None
    assert findings == []


def test_fixture_amount_is_expected_minor_units(
    payment_fixture: dict[str, Any],
) -> None:
    amount = payment_fixture["amount"]
    assert isinstance(amount, int)
    assert amount == 123456


def test_fixture_payment_id_prefix(payment_fixture: dict[str, Any]) -> None:
    assert payment_fixture["id"].startswith("pay_")


def test_redact_payment_drops_sensitive_fields() -> None:
    raw = {
        "id": "pay_ZZFAKEPAYMENT01",
        "entity": "payment",
        "amount": 123456,
        "currency": "INR",
        "status": "captured",
        "email": "zzfake@example.invalid",
        "contact": "9876543210",
        "vpa": "zzfakeuser@paytm",
        "token_id": "token_ZZFAKE",
        "acquirer_data": {"rrn": "ZZFAKERRN0001"},
        "card": {
            "id": "card_ZZFAKE",
            "entity": "card",
            "last4": "4242",
            "name": "ZZ FAKE",
            "network": "Visa",
            "type": "credit",
        },
        "notes": {"purpose": "smoke"},
    }
    redacted = fixture_redact.redact_payment(raw)
    dumped = json.dumps(redacted)
    assert "email" not in redacted
    assert "contact" not in redacted
    assert "vpa" not in redacted
    assert "acquirer_data" not in redacted
    assert "token_id" not in redacted
    assert "last4" not in dumped
    assert "name" not in redacted.get("card", {})
    assert redacted["notes"] == {}
