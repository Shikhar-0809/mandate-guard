"""Tests for scripts/webhook_verify.py."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "webhook_verify.py"

_SPEC = importlib.util.spec_from_file_location("webhook_verify", SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_webhook_verify = importlib.util.module_from_spec(_SPEC)
sys.modules["webhook_verify"] = _webhook_verify
_SPEC.loader.exec_module(_webhook_verify)
verify_webhook_signature = _webhook_verify.verify_webhook_signature

_DUMMY_SECRET = "dummy_secret_for_offline_tests"
_RAW_BODY = b'{"amount":123456,"currency":"INR","order_id":"order_test"}'


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_correct_secret_and_exact_raw_bytes() -> None:
    signature = _sign(_RAW_BODY, _DUMMY_SECRET)
    assert verify_webhook_signature(_RAW_BODY, signature, _DUMMY_SECRET) is True


def test_reserialized_json_does_not_match_original_signature() -> None:
    signature = _sign(_RAW_BODY, _DUMMY_SECRET)
    parsed = json.loads(_RAW_BODY)
    reserialized = json.dumps(
        parsed,
        separators=(", ", ": "),
        sort_keys=True,
    ).encode("utf-8")
    assert verify_webhook_signature(reserialized, signature, _DUMMY_SECRET) is False


def test_wrong_secret() -> None:
    signature = _sign(_RAW_BODY, _DUMMY_SECRET)
    assert verify_webhook_signature(_RAW_BODY, signature, "wrong_secret") is False


def test_tampered_body() -> None:
    signature = _sign(_RAW_BODY, _DUMMY_SECRET)
    tampered = bytearray(_RAW_BODY)
    tampered[0] ^= 0x01
    assert verify_webhook_signature(bytes(tampered), signature, _DUMMY_SECRET) is False


def test_malformed_signature() -> None:
    assert verify_webhook_signature(_RAW_BODY, "", _DUMMY_SECRET) is False
    assert (
        verify_webhook_signature(_RAW_BODY, "not-valid-hex!!!", _DUMMY_SECRET) is False
    )
