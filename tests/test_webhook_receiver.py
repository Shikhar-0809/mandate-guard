"""Tests for scripts/webhook_receiver.py."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "webhook_receiver.py"

_SPEC = importlib.util.spec_from_file_location("webhook_receiver", SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_webhook_receiver = importlib.util.module_from_spec(_SPEC)
sys.modules["webhook_receiver"] = _webhook_receiver
_SPEC.loader.exec_module(_webhook_receiver)
handle_capture = _webhook_receiver.handle_capture

_DUMMY_SECRET = "dummy_secret_for_offline_tests"
_RAW_BODY = (
    b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_test"}}}}'
)


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_valid_signature_writes_byte_identical_raw_file(tmp_path: Path) -> None:
    signature = _sign(_RAW_BODY, _DUMMY_SECRET)

    status, raw_path = handle_capture(
        _RAW_BODY,
        signature,
        _DUMMY_SECRET,
        tmp_path,
    )

    assert status == 200
    assert raw_path is not None
    assert raw_path.read_bytes() == _RAW_BODY


def test_invalid_signature_writes_nothing(tmp_path: Path) -> None:
    signature = _sign(_RAW_BODY, _DUMMY_SECRET)

    status, raw_path = handle_capture(
        _RAW_BODY,
        signature,
        "wrong_secret",
        tmp_path,
    )

    assert status == 400
    assert raw_path is None
    assert list(tmp_path.iterdir()) == []


def test_empty_secret_raises_value_error(tmp_path: Path) -> None:
    signature = _sign(_RAW_BODY, _DUMMY_SECRET)

    with pytest.raises(ValueError, match="secret must not be empty"):
        handle_capture(_RAW_BODY, signature, "", tmp_path)


def test_missing_signature_header_returns_rejected(tmp_path: Path) -> None:
    status, raw_path = handle_capture(_RAW_BODY, "", _DUMMY_SECRET, tmp_path)

    assert status == 400
    assert raw_path is None
    assert list(tmp_path.iterdir()) == []


def test_creates_captures_dir_when_missing(tmp_path: Path) -> None:
    captures_dir = tmp_path / "nested" / "captures"
    signature = _sign(_RAW_BODY, _DUMMY_SECRET)

    status, raw_path = handle_capture(
        _RAW_BODY,
        signature,
        _DUMMY_SECRET,
        captures_dir,
    )

    assert status == 200
    assert raw_path is not None
    assert captures_dir.is_dir()
    assert raw_path.read_bytes() == _RAW_BODY
