"""Tests for scripts/check_identifiers.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any, Protocol, cast

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_identifiers.py"


class _CheckIdentifiers(Protocol):
    ALLOWLIST: list[tuple[str, str, str]]

    def validate_allowlist(self) -> None: ...


_CHECK_SPEC = importlib.util.spec_from_file_location("check_identifiers", SCRIPT)
assert _CHECK_SPEC is not None and _CHECK_SPEC.loader is not None
_check_identifiers_raw: Any = importlib.util.module_from_spec(_CHECK_SPEC)
sys.modules["check_identifiers"] = _check_identifiers_raw
_CHECK_SPEC.loader.exec_module(_check_identifiers_raw)
check_identifiers = cast(_CheckIdentifiers, _check_identifiers_raw)

BOTH_POLICY_CASES: list[tuple[str, str]] = [
    ("contact: zzfake@example.invalid\n", "EMAIL"),
    ("mobile 9876543210\n", "PHONE_IN"),
    # VPA regex matches real PSP handles (paytm, ybl, ...); detection machinery
    # in scripts/, not governed by RULES 34 (which covers data/ and fixtures/).
    ("vpa zzfakeuser@paytm\n", "VPA"),
    ("branch FAKE0001234\n", "IFSC"),
    ("card 4111111111111111\n", "PAN_CARD"),
    ('{"mode":"rzp_live_zzfakemodekey"}\n', "RZP_LIVE"),
    ('{"mode":"rzp_test_zzfaketestkey"}\n', "RZP_TEST"),
    ('{"last4":"9999"}\n', "CARD_LAST4"),
    ('{"api_secret":"zz-not-real"}\n', "SECRET_KEY"),
    ('{"account_number": "12345678901234"}\n', "ACCOUNT_NO"),
    ('{"rrn": "ZZFAKERRN0001"}\n', "RRN"),
]


def run_scan(root: Path, policy: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--policy",
            policy,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("policy", ["deny_all", "deny_secrets_and_pii"])
@pytest.mark.parametrize(("content", "detector_class"), BOTH_POLICY_CASES)
def test_positive_detection(
    tmp_path: Path,
    content: str,
    detector_class: str,
    policy: str,
) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text(content, encoding="utf-8")

    result = run_scan(tmp_path, policy)

    assert result.returncode == 1
    assert detector_class in result.stdout


def test_epoch_is_not_a_phone(tmp_path: Path) -> None:
    sample = tmp_path / "epoch.json"
    sample.write_text('{"created_at": 1756300000}\n', encoding="utf-8")

    for policy in ("deny_all", "deny_secrets_and_pii"):
        result = run_scan(tmp_path, policy)
        assert result.returncode == 0, result.stdout
        assert "PHONE_IN" not in result.stdout


def test_policy_divergence_on_rzp_object_id(tmp_path: Path) -> None:
    sample = tmp_path / "fixture.json"
    sample.write_text('{"id": "order_TUphkNLUdCn8t3"}\n', encoding="utf-8")

    clean = run_scan(tmp_path, "deny_secrets_and_pii")
    assert clean.returncode == 0, clean.stdout

    denied = run_scan(tmp_path, "deny_all")
    assert denied.returncode == 1
    assert "RZP_OBJECT_ID" in denied.stdout


def test_url_policy_divergence(tmp_path: Path) -> None:
    sample = tmp_path / "url.txt"
    sample.write_text("https://zzfake.example.invalid/path\n", encoding="utf-8")

    denied = run_scan(tmp_path, "deny_all")
    assert denied.returncode == 1
    assert "URL" in denied.stdout

    clean = run_scan(tmp_path, "deny_secrets_and_pii")
    assert clean.returncode == 0, clean.stdout
    assert "URL" not in clean.stdout


def test_live_mode_never_allowed(tmp_path: Path) -> None:
    sample = tmp_path / "live.txt"
    sample.write_text("rzp_live_zzfakelivekey\n", encoding="utf-8")

    for policy in ("deny_all", "deny_secrets_and_pii"):
        result = run_scan(tmp_path, policy)
        assert result.returncode == 1
        assert "RZP_LIVE" in result.stdout


def test_allowlist_entries_require_non_empty_reason() -> None:
    for _literal, _path, reason in check_identifiers.ALLOWLIST:
        assert reason

    with pytest.raises(ValueError, match="empty reason"):
        original = _check_identifiers_raw.ALLOWLIST
        _check_identifiers_raw.ALLOWLIST = [("literal", "path", "")]
        try:
            check_identifiers.validate_allowlist()
        finally:
            _check_identifiers_raw.ALLOWLIST = original
