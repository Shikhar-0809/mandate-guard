"""Scan repository text for identifiers under policy-specific rules.

Policy table
============

``data/``
    DENY_ALL — synthesised corpora. No real-world identifier of any kind may
    appear. Every detector class is enforced, including RZP_OBJECT_ID and URL.

``fixtures/``
    DENY_SECRETS_AND_PII — real test-mode API output, committed deliberately
    (see D002). Test-mode object ids are permitted because they are the point
    of the fixture. Secrets and PII are not. Every detector class is enforced
    **except** RZP_OBJECT_ID and URL.

RZP_TEST is flagged under **both** policies. The key_id is public by design and
legitimately ships in Checkout HTML, but it has no business in a replay cassette,
and permitting it means the scanner cannot tell you when a key_secret appears
beside it.

RZP_LIVE is flagged under **both** policies, always, no exceptions.

Suppression
===========

A suppression requires an exact-literal ALLOWLIST entry with a non-empty reason
string **and** a DECISIONS.md entry, mirroring RULES 23 (findings are deleted,
not silenced). Never regex relaxation, never whole-file skip.

Synthetic test-harness contacts
===============================

``SYNTHETIC_CONTACTS`` holds hardcoded constants from the Checkout test harness,
chosen because they belong to no real person. ``buyer@example.invalid`` uses the
reserved ``.invalid`` TLD, which cannot resolve. A detector match whose matched
text is **exactly** one of these literals is not a finding under both policies.
This narrows what counts as PII; it is not a per-file exception. The ALLOWLIST
stays empty. No detector class emits a person's name, so the ``name`` entry in
``HARNESS_PREFILL`` is never reachable by the finding filter and exists solely
as the harness prefill source of truth.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# (exact_literal, path, reason) — exact literal match only; reason must be non-empty.
ALLOWLIST: list[tuple[str, str, str]] = []

HARNESS_PREFILL: Final[dict[str, str]] = {
    "contact": "9000090000",
    "email": "buyer@example.invalid",
    "name": "Test Buyer",
}
SYNTHETIC_CONTACTS: frozenset[str] = frozenset(HARNESS_PREFILL.values())


class Policy(Enum):
    DENY_ALL = "deny_all"
    DENY_SECRETS_AND_PII = "deny_secrets_and_pii"


@dataclass(frozen=True)
class Detector:
    name: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    detector_class: str
    matched: str


EMAIL = Detector(
    "EMAIL",
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
)
PHONE_IN = Detector(
    "PHONE_IN",
    re.compile(r"(?:\+91[6-9]\d{9}\b|\b0[6-9]\d{9}\b|\b[6-9]\d{9}\b)"),
)
VPA = Detector(
    "VPA",
    re.compile(
        r"[a-zA-Z0-9._-]+@(?:paytm|ybl|okaxis|okhdfcbank|oksbi|okicici|axl|apl|ibl|upi)\b",
        re.IGNORECASE,
    ),
)
IFSC = Detector(
    "IFSC",
    re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE),
)
PAN_CARD = Detector("PAN_CARD", re.compile(r"\b\d{13,19}\b"))
CARD_LAST4 = Detector(
    "CARD_LAST4",
    re.compile(r'"last4"\s*:\s*(?!null\b)(?:"[^"]*"|[^,\s}\]]+)'),
)
ACCOUNT_NO = Detector(
    "ACCOUNT_NO",
    re.compile(
        r'"(?:[^"]*(?:account|acct)[^"]*)"\s*:\s*"?(\d{9,18})"?',
        re.IGNORECASE,
    ),
)
RRN = Detector(
    "RRN",
    re.compile(r'"rrn"\s*:\s*(?!null\b)(?:"[^"]*"|[^,\s}\]]+)', re.IGNORECASE),
)
SECRET_KEY = Detector(
    "SECRET_KEY",
    re.compile(
        r'"(?:[^"]*(?:secret|password|private_key)[^"]*)"\s*:\s*(?!""|\s*null\b)(?:"[^"]+"|\S+)',
        re.IGNORECASE,
    ),
)
RZP_LIVE = Detector("RZP_LIVE", re.compile(r"rzp_live_"))
RZP_TEST = Detector("RZP_TEST", re.compile(r"rzp_test_"))
URL = Detector("URL", re.compile(r"https?://"))
RZP_OBJECT_ID = Detector(
    "RZP_OBJECT_ID",
    re.compile(r"\b(?:order_|pay_|plan_|sub_|inv_)[A-Za-z0-9]+\b"),
)

ALL_DETECTORS: tuple[Detector, ...] = (
    EMAIL,
    PHONE_IN,
    VPA,
    IFSC,
    PAN_CARD,
    CARD_LAST4,
    ACCOUNT_NO,
    RRN,
    SECRET_KEY,
    RZP_LIVE,
    RZP_TEST,
    URL,
    RZP_OBJECT_ID,
)

POLICY_DETECTORS: dict[Policy, tuple[Detector, ...]] = {
    Policy.DENY_ALL: ALL_DETECTORS,
    Policy.DENY_SECRETS_AND_PII: tuple(
        detector
        for detector in ALL_DETECTORS
        if detector.name not in {"RZP_OBJECT_ID", "URL"}
    ),
}

SCAN_ROOTS: tuple[tuple[Path, Policy], ...] = (
    (PROJECT_ROOT / "data", Policy.DENY_ALL),
    (PROJECT_ROOT / "fixtures", Policy.DENY_SECRETS_AND_PII),
)


def luhn_valid(digits: str) -> bool:
    total = 0
    reverse = digits[::-1]
    for index, digit_char in enumerate(reverse):
        digit = int(digit_char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def line_number_at(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def mask_prefix(matched: str, length: int = 2) -> str:
    return matched[:length]


def is_allowlisted(matched: str, path: Path) -> bool:
    path_str = str(path)
    for literal, allow_path, reason in ALLOWLIST:
        if not reason:
            raise ValueError("ALLOWLIST entry has empty reason string")
        if matched == literal and path_str.endswith(allow_path):
            return True
    return False


def findings_for_detector(detector: Detector, text: str, path: Path) -> list[Finding]:
    findings: list[Finding] = []

    if detector is PAN_CARD:
        for match in detector.pattern.finditer(text):
            candidate = match.group(0)
            if luhn_valid(candidate):
                findings.append(
                    Finding(
                        path=path,
                        line=line_number_at(text, match.start()),
                        detector_class=detector.name,
                        matched=candidate,
                    )
                )
        return findings

    if detector is ACCOUNT_NO:
        for match in detector.pattern.finditer(text):
            matched = match.group(1)
            findings.append(
                Finding(
                    path=path,
                    line=line_number_at(text, match.start()),
                    detector_class=detector.name,
                    matched=matched,
                )
            )
        return findings

    for match in detector.pattern.finditer(text):
        matched = match.group(0)
        findings.append(
            Finding(
                path=path,
                line=line_number_at(text, match.start()),
                detector_class=detector.name,
                matched=matched,
            )
        )
    return findings


def scan_text(text: str, path: Path, policy: Policy) -> list[Finding]:
    findings: list[Finding] = []
    for detector in POLICY_DETECTORS[policy]:
        for finding in findings_for_detector(detector, text, path):
            if finding.matched in SYNTHETIC_CONTACTS:
                continue
            if not is_allowlisted(finding.matched, finding.path):
                findings.append(finding)
    return findings


def scan_file(path: Path, policy: Policy) -> tuple[list[Finding], str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], f"skipped (not UTF-8): {path}"
    return scan_text(text, path, policy), None


def scan_root(root: Path, policy: Policy) -> tuple[list[Finding], int, list[str]]:
    findings: list[Finding] = []
    messages: list[str] = []
    file_count = 0

    if not root.exists():
        messages.append(f"root does not exist, skipping: {root}")
        return findings, file_count, messages

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        file_count += 1
        file_findings, skip_message = scan_file(path, policy)
        if skip_message:
            messages.append(skip_message)
        findings.extend(file_findings)

    return findings, file_count, messages


def format_finding(finding: Finding) -> str:
    prefix = mask_prefix(finding.matched)
    return (
        f"{finding.path}:{finding.line}: {finding.detector_class} "
        f"(len={len(finding.matched)}, starts='{prefix}')"
    )


def validate_allowlist() -> None:
    for literal, path, reason in ALLOWLIST:
        if not reason:
            raise ValueError(
                f"ALLOWLIST entry has empty reason string: {literal!r} at {path!r}"
            )
        if not literal:
            raise ValueError(f"ALLOWLIST entry has empty literal at {path!r}")


def run_scan(
    roots: tuple[tuple[Path, Policy], ...],
) -> tuple[list[Finding], dict[str, int], list[str]]:
    validate_allowlist()
    all_findings: list[Finding] = []
    counts: dict[str, int] = {}
    messages: list[str] = []

    for root, policy in roots:
        findings, file_count, root_messages = scan_root(root, policy)
        counts[root.name] = file_count
        messages.extend(root_messages)
        all_findings.extend(findings)

    return all_findings, counts, messages


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan text for identifiers.")
    parser.add_argument(
        "--root",
        type=Path,
        help="Optional directory to scan with --policy.",
    )
    parser.add_argument(
        "--policy",
        choices=[policy.value for policy in Policy],
        help="Policy to apply when --root is set.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    roots: tuple[tuple[Path, Policy], ...]
    if args.root is not None:
        if args.policy is None:
            print("--policy is required when --root is set", file=sys.stderr)
            return 1
        roots = ((args.root.resolve(), Policy(args.policy)),)
        label_root = str(args.root.resolve())
    else:
        roots = SCAN_ROOTS

    findings, counts, messages = run_scan(roots)

    for message in messages:
        print(message)

    if args.root is None:
        data_count = counts.get("data", 0)
        fixtures_count = counts.get("fixtures", 0)
        print(
            f"scanned {data_count} files under data/, {fixtures_count} files under fixtures/"
        )
    else:
        scanned = next(iter(counts.values()), 0)
        print(f"scanned {scanned} files under {label_root}/")

    for finding in findings:
        print(format_finding(finding))

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
