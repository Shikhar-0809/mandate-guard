"""T1 calibrated GBM scorer for mandate deviation risk."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import cast

import joblib  # type: ignore[import-untyped]  # no py.typed marker in joblib
import lightgbm as lgb
import numpy as np
from sklearn.calibration import CalibratedClassifierCV  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split  # type: ignore[import-untyped]

from contracts import (
    CartItem,
    CartMandate,
    DelegationToken,
    IntentMandate,
    Money,
    Scope,
)

from .features import FEATURE_NAMES, extract_features


@dataclass(frozen=True)
class _FeatureInputs:
    intent: IntentMandate
    cart: CartMandate
    token: DelegationToken | None
    transaction_amount: Money
    merchant_id: str
    mcc: str
    now: datetime


def _record_to_args(record: dict[str, object]) -> _FeatureInputs:
    """Deserialize a flat corpus record into extract_features keyword arguments."""
    merchants_raw = record["intent_scope_merchants"]
    categories_raw = record["intent_scope_categories"]
    max_amount = None
    if record["intent_scope_max_amount_minor_units"] is not None:
        max_amount = Money(
            int(cast(int, record["intent_scope_max_amount_minor_units"])),
            str(record["intent_scope_max_amount_currency"]),
        )
    merchants = (
        frozenset(cast(list[str], merchants_raw)) if merchants_raw is not None else None
    )
    categories = (
        frozenset(cast(list[str], categories_raw))
        if categories_raw is not None
        else None
    )
    scope = Scope(
        merchants=merchants,
        categories=categories,
        max_amount=max_amount,
    )
    intent = IntentMandate(
        mandate_id=str(record["intent_mandate_id"]),
        principal_id=str(record["intent_principal_id"]),
        scope=scope,
        issued_at=datetime.fromisoformat(str(record["intent_issued_at"])),
        expires_at=datetime.fromisoformat(str(record["intent_expires_at"])),
        cart_hash=record["intent_cart_hash"],  # type: ignore[arg-type]
        purchase_intent=str(record.get("purchase_intent", "")),
    )
    cart_items = cast(list[dict[str, object]], record["cart_items"])
    items = tuple(
        CartItem(
            sku=str(item["sku"]),
            name=str(item["name"]),
            quantity=int(cast(int, item["quantity"])),
            unit_price=Money(
                int(cast(int, item["unit_price_minor_units"])),
                str(item["unit_price_currency"]),
            ),
        )
        for item in cart_items
    )
    cart = CartMandate(
        mandate_id=str(record["cart_mandate_id"]),
        items=items,
        total=Money(
            int(cast(int, record["cart_total_minor_units"])),
            str(record["cart_total_currency"]),
        ),
        cart_hash=str(record["cart_hash"]),
    )
    token = _delegation_token_from_record(record, scope, intent)
    now = datetime.fromisoformat(str(record["intent_expires_at"])) - timedelta(days=1)
    return _FeatureInputs(
        intent=intent,
        cart=cart,
        token=token,
        transaction_amount=Money(
            int(cast(int, record["transaction_amount_minor_units"])),
            str(record["transaction_amount_currency"]),
        ),
        merchant_id=str(record["merchant_id"]),
        mcc=str(record["mcc"]),
        now=now,
    )


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


def _ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Compute Expected Calibration Error over equal-width probability bins."""
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for index in range(n_bins):
        low = bin_edges[index]
        high = bin_edges[index + 1]
        if index == n_bins - 1:
            mask = (y_prob >= low) & (y_prob <= high)
        else:
            mask = (y_prob >= low) & (y_prob < high)
        if not np.any(mask):
            continue
        fraction = float(np.mean(mask))
        calibration_gap = abs(
            float(np.mean(y_prob[mask])) - float(np.mean(y_true[mask]))
        )
        ece += fraction * calibration_gap
    return ece


def train(
    records: list[dict[str, object]],
    model_dir: Path,
) -> dict[str, float]:
    """Train a calibrated LightGBM model and write baselines.json."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    tfidf_corpus = []
    for record in records:
        intent = str(record.get("purchase_intent") or "")
        cart_items = record.get("cart_items") or []
        cart_text = " ".join(
            str(item.get("name") or "") for item in cart_items
        )
        tfidf_corpus.append(intent + " " + cart_text)

    tfidf_vec = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
    )
    tfidf_vec.fit(tfidf_corpus)

    feature_rows: list[list[float]] = []
    labels: list[float] = []
    for record in records:
        feature_rows.append(
            extract_features(record, tfidf_vectorizer=tfidf_vec)
        )
        labels.append(1.0 if str(record["label"]) == "BLOCK" else 0.0)

    x = np.array(feature_rows)
    y = np.array(labels)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    base_clf = lgb.LGBMClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        random_state=42,
        verbose=-1,
    )
    clf = CalibratedClassifierCV(base_clf, method="isotonic", cv=5)
    clf.fit(x_train, y_train)

    y_prob = clf.predict_proba(x_test)[:, 1]
    auc = float(roc_auc_score(y_test, y_prob))
    y_pred = (y_prob >= 0.5).astype(int)
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall = float(recall_score(y_test, y_pred, zero_division=0))
    ece = _ece(y_test, y_prob)

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(tfidf_vec, model_dir / "tfidf_vectorizer.joblib")
    joblib.dump(clf, model_dir / "t1_model.joblib")
    (model_dir / "feature_names.json").write_text(
        json.dumps(list(FEATURE_NAMES)),
        encoding="utf-8",
    )

    baselines_path = Path(__file__).resolve().parents[2] / "baselines.json"
    existing: dict[str, object] = {}
    if baselines_path.exists():
        existing = json.loads(baselines_path.read_text(encoding="utf-8"))
    existing.update({
        "t1_auc": auc,
        "t1_precision": precision,
        "t1_recall": recall,
        "t1_ece": ece,
        "trained_on_n": len(records),
        "holdout_n": len(y_test),
        "feature_count": len(FEATURE_NAMES),
    })
    baselines_path.write_text(
        json.dumps(existing, indent=2) + "\n", encoding="utf-8"
    )

    # A2: feature importance audit
    import json as _json, pathlib as _pathlib
    _fold_imps: list[np.ndarray] = []
    for _cc in clf.calibrated_classifiers_:
        _fold_imps.append(
            _cc.estimator.booster_.feature_importance(importance_type="gain")
        )
    _avg_imp = np.mean(np.stack(_fold_imps, axis=0), axis=0)
    _imp = dict(zip(list(FEATURE_NAMES), (float(x) for x in _avg_imp)))
    _ranked = sorted(_imp.items(), key=lambda x: -x[1])
    _pathlib.Path("feature_importances.json").write_text(
        _json.dumps(_ranked, indent=2)
    )
    print("FEATURE IMPORTANCES:")
    for _name, _score in _ranked:
        print(f"  {_score:.4f}  {_name}")

    return {
        "auc": auc,
        "precision": precision,
        "recall": recall,
        "ece": ece,
    }


@lru_cache(maxsize=1)
def _load_model(model_dir: Path) -> CalibratedClassifierCV:
    path = model_dir / "t1_model.joblib"
    clf: CalibratedClassifierCV = joblib.load(path)
    names_path = model_dir / "feature_names.json"
    if names_path.exists():
        saved = cast(list[str], json.loads(names_path.read_text(encoding="utf-8")))
        assert list(FEATURE_NAMES) == saved, (
            f"feature name mismatch: model trained on {saved}, "
            f"current FEATURE_NAMES={list(FEATURE_NAMES)}"
        )
    return clf


@lru_cache(maxsize=1)
def _load_tfidf(model_dir: Path):
    tfidf_path = model_dir / "tfidf_vectorizer.joblib"
    return joblib.load(tfidf_path) if tfidf_path.exists() else None


def score(
    record: dict[str, object],
    model_dir: Path,
) -> float:
    """Return calibrated BLOCK probability for a transaction record."""
    clf = _load_model(model_dir)
    tfidf_vec = _load_tfidf(model_dir)
    features = extract_features(record, tfidf_vectorizer=tfidf_vec)
    x = np.array([features])
    prob = float(clf.predict_proba(x)[0, 1])
    assert 0.0 <= prob <= 1.0
    return prob
