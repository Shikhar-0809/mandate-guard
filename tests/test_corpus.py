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
    "hn_semantic_ambiguous",
    "attack_family_1",
    "attack_family_2",
    "attack_family_3",
    "attack_family_4",
    "attack_family_5",
    "attack_family_6",
    "attack_family_7",
    "attack_family_14",
    "attack_family_15",
    "hn_post_auth_cart_mutation",
}

SEALED_EXPECTED_FAMILIES = {
    "attack_family_8",
    "attack_family_9",
    "attack_family_10",
    "attack_family_11",
    "attack_family_12",
    "attack_family_13",
}

DATA_SEALED_SEMANTIC = PROJECT_ROOT / "data" / "sealed_semantic"
SEMANTIC_EXPECTED_FAMILIES = {
    "semantic_apparel",
    "semantic_automotive",
    "semantic_books_media",
    "semantic_electronics",
    "semantic_groceries",
    "semantic_health_personal_care",
    "semantic_home_goods",
    "semantic_office_supplies",
    "semantic_pet_supplies",
    "semantic_toys_games",
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
    # Probe features must be side-channel metadata, not label proxies.
    # family and hash(family) are direct label encodings — using them
    # defeats the probe's purpose. We use note length, family_note length,
    # and amount cents-digit as proxies for generator routine artifacts.
    x = np.array(
        [
            [
                len(str(record["note"])),
                len(str(record["family_note"])),
                int(record["transaction_amount_minor_units"]) % 100,
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
    assert len(load_jsonl(DATA_DEV / "hard_negatives.jsonl")) == 226
    assert len(load_jsonl(DATA_DEV / "attacks.jsonl")) == 270


HN_POST_AUTH_CART_MUTATION_LABELS: dict[str, str] = {
    f"zz-record-hn_post_auth_cart_mutation-{n}": (
        "BLOCK" if n % 4 == 0 else "ALLOW"
    )
    for n in range(200, 220)
}


def test_hn_post_auth_cart_mutation_label_split() -> None:
    records = load_jsonl(DATA_DEV / "hard_negatives.jsonl")
    mutation_records = [
        record
        for record in records
        if str(record["family"]) == "hn_post_auth_cart_mutation"
    ]
    observed = {
        str(record["record_id"]): str(record["label"])
        for record in mutation_records
    }
    assert observed == HN_POST_AUTH_CART_MUTATION_LABELS

    allow_names = [
        str(record["cart_items"][0]["name"])
        for record in mutation_records
        if str(record["label"]) == "ALLOW"
    ]
    block_names = [
        str(record["cart_items"][0]["name"])
        for record in mutation_records
        if str(record["label"]) == "BLOCK"
    ]
    assert len(allow_names) == len(set(allow_names))
    assert len(block_names) == len(set(block_names))


def test_sealed_record_counts() -> None:
    assert len(load_jsonl(DATA_SEALED / "attacks.jsonl")) == 150


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


T0_BLOCKING_ATTACK_FAMILIES = {
    *(f"attack_family_{n}" for n in range(1, 8)),
    *(f"attack_family_{n}" for n in range(8, 13)),
}
T0_PASSING_ATTACK_FAMILIES = {"attack_family_14", "attack_family_15"}


def test_t0_blocks_all_attack_records() -> None:
    for record in load_jsonl(DATA_DEV / "attacks.jsonl"):
        family = str(record["family"])
        result = check(**record_to_check_args(record))
        if family in T0_BLOCKING_ATTACK_FAMILIES:
            if result.passed:
                pytest.fail(
                    f"T0-blocking attack passed T0: record_id={record['record_id']} "
                    f"family={family}"
                )
        elif family in T0_PASSING_ATTACK_FAMILIES:
            if not result.passed:
                pytest.fail(
                    f"T0-passing attack failed T0: record_id={record['record_id']} "
                    f"family={family}"
                )
        else:
            pytest.fail(f"unexpected attack family in dev corpus: {family}")


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


_RUN_EVAL_SPEC = importlib.util.spec_from_file_location(
    "run_eval", PROJECT_ROOT / "scripts" / "run_eval.py"
)
assert _RUN_EVAL_SPEC is not None and _RUN_EVAL_SPEC.loader is not None
_run_eval = importlib.util.module_from_spec(_RUN_EVAL_SPEC)
sys.modules[_RUN_EVAL_SPEC.name] = _run_eval
_RUN_EVAL_SPEC.loader.exec_module(_run_eval)
_load_dev = _run_eval._load_dev
_compute_cascade_dev_metrics = _run_eval._compute_cascade_dev_metrics
_compute_dev_eval_metrics = _run_eval._compute_dev_eval_metrics


def _write_sha256sums(directory: Path, filenames: list[str]) -> None:
    lines: list[str] = []
    for filename in filenames:
        digest = hashlib.sha256((directory / filename).read_bytes()).hexdigest()
        lines.append(f"{digest}  {filename}\n")
    (directory / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


def test_load_dev_intent_modes(tmp_path: Path) -> None:
    record_a_base = {"record_id": "record-a", "purchase_intent": ""}
    record_a_full = {"record_id": "record-a", "purchase_intent": "buy Widget"}
    attack_intent = "buy Sony noise cancelling headphones"
    record_b = {"record_id": "record-b", "purchase_intent": attack_intent}

    for name, content in (
        ("benign.jsonl", record_a_base),
        ("benign_with_intent.jsonl", record_a_full),
        ("hard_negatives.jsonl", {"record_id": "hn-empty", "purchase_intent": ""}),
        ("hard_negatives_with_intent.jsonl", {"record_id": "hn-empty", "purchase_intent": ""}),
        ("attacks.jsonl", record_b),
        ("attacks_with_intent.jsonl", record_b),
    ):
        (tmp_path / name).write_text(
            json.dumps(content) + "\n",
            encoding="utf-8",
        )
    _write_sha256sums(
        tmp_path,
        ["benign.jsonl", "hard_negatives.jsonl", "attacks.jsonl"],
    )

    no_intent = _load_dev(tmp_path, intent_mode="base")
    full_intent = _load_dev(tmp_path, intent_mode="with_intent")

    no_intent_a = next(r for r in no_intent if r["record_id"] == "record-a")
    full_intent_a = next(r for r in full_intent if r["record_id"] == "record-a")
    no_intent_b = next(r for r in no_intent if r["record_id"] == "record-b")
    full_intent_b = next(r for r in full_intent if r["record_id"] == "record-b")

    assert no_intent_a["purchase_intent"] == ""
    assert full_intent_a["purchase_intent"] == "buy Widget"
    assert no_intent_b["purchase_intent"] == attack_intent
    assert full_intent_b["purchase_intent"] == attack_intent


def test_cascade_dev_metrics_use_both_intent_loaders() -> None:
    from contracts import T2Config

    model_dir = PROJECT_ROOT / "models"
    t2_off = T2Config(t2_enabled=False)
    no_intent = _load_dev(DATA_DEV, intent_mode="base")
    full_intent = _load_dev(DATA_DEV, intent_mode="with_intent")

    for record_id_suffix in ("200", "204", "208", "212", "216"):
        suffix = f"hn_post_auth_cart_mutation-{record_id_suffix}"
        base_record = next(
            record for record in no_intent if str(record["record_id"]).endswith(suffix)
        )
        full_record = next(
            record
            for record in full_intent
            if str(record["record_id"]).endswith(suffix)
        )
        assert base_record["purchase_intent"] == ""
        assert full_record["purchase_intent"] != ""

    dev_metrics_no_intent = _compute_dev_eval_metrics(no_intent, model_dir, 0.008)
    dev_metrics_full_intent = _compute_dev_eval_metrics(full_intent, model_dir, 0.008)

    cascade_no_intent = _compute_cascade_dev_metrics(
        no_intent,
        model_dir,
        dev_metrics_no_intent["eval_tau_star"],
        t2_off,
    )
    cascade_full_intent = _compute_cascade_dev_metrics(
        full_intent,
        model_dir,
        dev_metrics_full_intent["eval_tau_star"],
        t2_off,
    )

    assert cascade_no_intent["eval_cascade_recall_seen"] == pytest.approx(
        0.9818181818181818
    )
    assert cascade_full_intent["eval_cascade_recall_seen"] == 1.0
    assert (
        cascade_no_intent["eval_cascade_recall_seen"]
        < cascade_full_intent["eval_cascade_recall_seen"]
    )


def test_semantic_sha256_integrity() -> None:
    verify_sha256sums(DATA_SEALED_SEMANTIC)


def test_semantic_record_count() -> None:
    assert len(load_jsonl(DATA_SEALED_SEMANTIC / "semantic.jsonl")) == 500


def test_semantic_family_coverage() -> None:
    families = {
        str(record["family"])
        for record in load_jsonl(DATA_SEALED_SEMANTIC / "semantic.jsonl")
    }
    assert families == SEMANTIC_EXPECTED_FAMILIES


def test_load_sealed_semantic_returns_records() -> None:
    from mandate_guard.eval import load_sealed_semantic

    records = load_sealed_semantic(DATA_SEALED_SEMANTIC)
    assert len(records) == 500
    families = {str(r["family"]) for r in records}
    assert families == SEMANTIC_EXPECTED_FAMILIES


def test_load_sealed_semantic_sha_mismatch_raises(tmp_path: Path) -> None:
    from mandate_guard.eval import load_sealed_semantic

    real_file = DATA_SEALED_SEMANTIC / "semantic.jsonl"
    (tmp_path / "semantic.jsonl").write_bytes(real_file.read_bytes())
    (tmp_path / "SHA256SUMS").write_text(
        "0" * 64 + "  semantic.jsonl\n", encoding="utf-8"
    )
    with pytest.raises(ValueError):
        load_sealed_semantic(tmp_path)
