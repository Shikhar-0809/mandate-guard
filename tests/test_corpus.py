"""Corpus integrity and leakage gates for generated mandate-guard data."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import cross_val_score
from sklearn.tree import DecisionTreeClassifier

from contracts import (
    CartItem,
    CartMandate,
    DelegationToken,
    IntentMandate,
    Money,
    Scope,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_GENERATE_SPEC = importlib.util.spec_from_file_location(
    "corpus_generate", PROJECT_ROOT / "data" / "generate.py"
)
assert _GENERATE_SPEC is not None and _GENERATE_SPEC.loader is not None
_corpus_generate = importlib.util.module_from_spec(_GENERATE_SPEC)
sys.modules[_GENERATE_SPEC.name] = _corpus_generate
_GENERATE_SPEC.loader.exec_module(_corpus_generate)
RECORD_FIELDS = _corpus_generate.RECORD_FIELDS

from mandate_guard.t0 import check

DATA_DEV = PROJECT_ROOT / "data" / "dev"
DATA_SEALED = PROJECT_ROOT / "data" / "sealed"

DEV_EXPECTED_FAMILIES = {
    "benign",
    "hn_stockout_substitution",
    "hn_price_drift",
    "hn_partial_capture",
    "hn_retry_fresh_idempotency",
    "hn_basket_split",
    "hn_subscription_stepup",
    "hn_subsidiary_confusability",
    "hn_post_snapshot_delivery",
    "hn_currency_rounding",
    "hn_narrowed_delegation",
    "attack_family_1",
    "attack_family_2",
    "attack_family_3",
    "attack_family_4",
    "attack_family_5",
    "attack_family_6",
    "attack_family_7",
}

SEALED_EXPECTED_FAMILIES = {
    "attack_family_8",
    "attack_family_9",
    "attack_family_10",
    "attack_family_11",
    "attack_family_12",
}


def load_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            records.append(json.loads(line))
    return records


def load_dev_records() -> list[dict[str, object]]:
    return (
        load_jsonl(DATA_DEV / "benign.jsonl")
        + load_jsonl(DATA_DEV / "hard_negatives.jsonl")
        + load_jsonl(DATA_DEV / "attacks.jsonl")
    )


def verify_sha256sums(directory: Path) -> None:
    sums_path = directory / "SHA256SUMS"
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, filename = line.split("  ", 1)
        computed = hashlib.sha256((directory / filename).read_bytes()).hexdigest()
        assert computed == digest, f"{filename}: recorded={digest} computed={computed}"


def record_to_check_args(record: dict[str, object]) -> dict[str, object]:
    merchants = record["intent_scope_merchants"]
    categories = record["intent_scope_categories"]
    max_amount = None
    if record["intent_scope_max_amount_minor_units"] is not None:
        max_amount = Money(
            int(record["intent_scope_max_amount_minor_units"]),
            str(record["intent_scope_max_amount_currency"]),
        )
    scope = Scope(
        merchants=frozenset(merchants) if merchants is not None else None,
        categories=frozenset(categories) if categories is not None else None,
        max_amount=max_amount,
    )
    intent = IntentMandate(
        mandate_id=str(record["intent_mandate_id"]),
        principal_id=str(record["intent_principal_id"]),
        scope=scope,
        issued_at=datetime.fromisoformat(str(record["intent_issued_at"])),
        expires_at=datetime.fromisoformat(str(record["intent_expires_at"])),
        cart_hash=record["intent_cart_hash"],  # type: ignore[arg-type]
    )
    items = tuple(
        CartItem(
            sku=str(item["sku"]),
            name=str(item["name"]),
            quantity=int(item["quantity"]),
            unit_price=Money(
                int(item["unit_price_minor_units"]),
                str(item["unit_price_currency"]),
            ),
        )
        for item in record["cart_items"]  # type: ignore[index]
    )
    cart = CartMandate(
        mandate_id=str(record["cart_mandate_id"]),
        items=items,
        total=Money(
            int(record["cart_total_minor_units"]),
            str(record["cart_total_currency"]),
        ),
        cart_hash=str(record["cart_hash"]),
    )
    token = _delegation_token_from_record(record, scope, intent)
    now = datetime.fromisoformat(str(record["intent_expires_at"])) - timedelta(days=1)
    return {
        "intent": intent,
        "cart": cart,
        "token": token,
        "transaction_amount": Money(
            int(record["transaction_amount_minor_units"]),
            str(record["transaction_amount_currency"]),
        ),
        "merchant_id": str(record["merchant_id"]),
        "mcc": str(record["mcc"]),
        "now": now,
    }


def _delegation_token_from_record(
    record: dict[str, object],
    parent_scope: Scope,
    intent: IntentMandate,
) -> DelegationToken | None:
    token_id = record.get("delegation_token_id")
    if not token_id:
        return None
    family = str(record["family"])
    if family == "hn_narrowed_delegation":
        delegated_scope = Scope(
            merchants=frozenset({str(record["merchant_id"])}),
            categories=parent_scope.categories,
            max_amount=parent_scope.max_amount,
        )
    elif family in {"attack_family_5", "attack_family_12"}:
        assert parent_scope.max_amount is not None
        delegated_scope = Scope(
            merchants=parent_scope.merchants,
            categories=parent_scope.categories,
            max_amount=Money(
                parent_scope.max_amount.minor_units + 10000,
                parent_scope.max_amount.currency,
            ),
        )
    else:
        return None
    return DelegationToken(
        token_id=str(token_id),
        parent_mandate_id=intent.mandate_id,
        parent_scope=parent_scope,
        delegated_scope=delegated_scope,
        issued_at=intent.issued_at,
        expires_at=intent.expires_at,
    )


def t0_pass_feature(records: list[dict[str, object]]) -> list[int]:
    features: list[int] = []
    for record in records:
        result = check(**record_to_check_args(record))
        features.append(1 if result.passed else 0)
    return features


def labels_from_records(records: list[dict[str, object]]) -> list[int]:
    return [1 if str(record["label"]) == "BLOCK" else 0 for record in records]


def shuffled_label_auc(records: list[dict[str, object]]) -> list[float]:
    features = np.array(t0_pass_feature(records))
    base_labels = np.array(labels_from_records(records))
    aucs: list[float] = []
    for seed in range(10):
        rng = np.random.default_rng(seed)
        shuffled = rng.permutation(base_labels)
        aucs.append(float(roc_auc_score(shuffled, features)))
    return aucs


def provenance_probe_auc(records: list[dict[str, object]]) -> float:
    x = np.array(
        [
            [
                len(str(record["note"])),
                len(str(record["family"])),
                hash(str(record["family"])) % 1000,
            ]
            for record in records
        ]
    )
    y = np.array(labels_from_records(records))
    clf = DecisionTreeClassifier(max_depth=3, random_state=0)
    aucs = cross_val_score(clf, x, y, cv=5, scoring="roc_auc")
    return float(np.mean(aucs))


def test_sha256_integrity_dev() -> None:
    verify_sha256sums(DATA_DEV)


def test_sha256_integrity_sealed() -> None:
    verify_sha256sums(DATA_SEALED)


def test_dev_record_counts() -> None:
    assert len(load_jsonl(DATA_DEV / "benign.jsonl")) == 800
    assert len(load_jsonl(DATA_DEV / "hard_negatives.jsonl")) == 200
    assert len(load_jsonl(DATA_DEV / "attacks.jsonl")) == 210


def test_sealed_record_counts() -> None:
    assert len(load_jsonl(DATA_SEALED / "attacks.jsonl")) == 125


def test_dev_attack_rate() -> None:
    total = 1210
    attacks = 210
    rate = attacks / total
    assert abs(rate - (210 / 1210)) <= 0.005


def test_dev_family_coverage() -> None:
    families = {str(record["family"]) for record in load_dev_records()}
    assert families == DEV_EXPECTED_FAMILIES


def test_sealed_family_coverage() -> None:
    families = {
        str(record["family"]) for record in load_jsonl(DATA_SEALED / "attacks.jsonl")
    }
    assert families == SEALED_EXPECTED_FAMILIES


def test_schema_completeness() -> None:
    for record in load_dev_records():
        for field in RECORD_FIELDS:
            assert field in record
        assert record["label"] in {"ALLOW", "BLOCK"}


def test_t0_blocks_all_attack_records() -> None:
    for record in load_jsonl(DATA_DEV / "attacks.jsonl"):
        result = check(**record_to_check_args(record))
        if result.passed:
            pytest.fail(
                f"attack passed T0: record_id={record['record_id']} family={record['family']}"
            )


def test_t0_passes_all_benign_records() -> None:
    for record in load_jsonl(DATA_DEV / "benign.jsonl"):
        result = check(**record_to_check_args(record))
        assert result.passed is True


def test_hard_negatives_t0_pass_rate() -> None:
    records = load_jsonl(DATA_DEV / "hard_negatives.jsonl")
    passed = sum(
        1 for record in records if check(**record_to_check_args(record)).passed
    )
    assert passed / len(records) >= 0.60


def test_shuffled_label_auc() -> None:
    records = load_dev_records()
    for seed, auc in enumerate(shuffled_label_auc(records)):
        assert 0.45 <= auc <= 0.55, f"seed={seed} auc={auc}"


def test_provenance_probe_auc() -> None:
    assert provenance_probe_auc(load_dev_records()) < 0.60


def test_hard_negative_difficulty() -> None:
    benign = load_jsonl(DATA_DEV / "benign.jsonl")
    hard_negatives = load_jsonl(DATA_DEV / "hard_negatives.jsonl")
    benign_fp = 1.0 - (
        sum(1 for record in benign if check(**record_to_check_args(record)).passed)
        / len(benign)
    )
    hn_fp = 1.0 - (
        sum(
            1
            for record in hard_negatives
            if check(**record_to_check_args(record)).passed
        )
        / len(hard_negatives)
    )
    assert hn_fp >= benign_fp + 0.05, f"benign_fp={benign_fp} hn_fp={hn_fp}"
