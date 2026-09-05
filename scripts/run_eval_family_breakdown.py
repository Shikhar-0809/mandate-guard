"""CLI entry point for sealed-set recall breakdown by attack family."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from contracts import T2Config
from mandate_guard.eval import load_sealed_attacks, recall_by_family

# Matches eval_tau_star_no_intent in baselines.json (dev corpus cost-optimal
# threshold, no-intent). Applied to sealed corpus per existing eval_recall_unseen
# baseline convention — not re-derived here.
TAU_USED = 1.0
FAMILY_13 = "attack_family_13"
OUTPUT_PATH = PROJECT_ROOT / "eval_outputs" / "sealed_family_breakdown.json"
BASELINE_RECALL_UNSEEN = 0.8333333333333334


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run sealed-set recall breakdown by attack family"
    )
    parser.add_argument("--model-dir", type=Path, default=Path("models/"))
    args = parser.parse_args()

    sealed_dir = PROJECT_ROOT / "data" / "sealed"

    print("Loading sealed attacks...")
    sealed_records = load_sealed_attacks(sealed_dir)
    print(f"  loaded {len(sealed_records)} sealed records")

    t2_off = T2Config(t2_enabled=False)
    print(f"Computing T2-off family breakdown (tau={TAU_USED}, t2_enabled=False)...")
    t2_off_breakdown = recall_by_family(
        sealed_records,
        args.model_dir,
        TAU_USED,
        t2_off,
    )
    for family in sorted(t2_off_breakdown):
        print(f"  {family}: {t2_off_breakdown[family]:.4f}")

    family_block_counts: dict[str, int] = {}
    for record in sealed_records:
        if str(record["label"]) == "BLOCK":
            family = str(record["family"])
            family_block_counts[family] = family_block_counts.get(family, 0) + 1
    total_block = sum(family_block_counts.values())
    weighted_recall = (
        sum(
            t2_off_breakdown[family] * count
            for family, count in family_block_counts.items()
        )
        / total_block
    )
    print(
        f"Reconciliation: weighted_recall={weighted_recall:.4f} vs "
        f"existing baseline eval_recall_unseen={BASELINE_RECALL_UNSEEN}"
    )
    if abs(weighted_recall - BASELINE_RECALL_UNSEEN) > 0.01:
        print(
            "ERROR: weighted_recall diverges from eval_recall_unseen baseline; "
            "stopping before T2-on family-13 run."
        )
        sys.exit(1)

    family_13_records = [
        record for record in sealed_records if str(record["family"]) == FAMILY_13
    ]
    t2_on = T2Config(t2_enabled=True)
    print(
        f"Computing T2-on family-13-only breakdown (n={len(family_13_records)}, "
        f"tau={TAU_USED}, t2_enabled=True)..."
    )
    t2_on_family_13_breakdown = recall_by_family(
        family_13_records,
        args.model_dir,
        TAU_USED,
        t2_on,
    )
    t2_on_family_13 = t2_on_family_13_breakdown[FAMILY_13]
    print(f"  {FAMILY_13}: {t2_on_family_13:.4f}")

    output = {
        "t2_off": t2_off_breakdown,
        "t2_on_family_13": t2_on_family_13,
        "tau_used": TAU_USED,
        "note": (
            "tau matches dev corpus's eval_tau_star_no_intent, applied to sealed "
            "corpus per existing eval_recall_unseen baseline convention"
        ),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing {OUTPUT_PATH}...")
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print("Done.")


if __name__ == "__main__":
    main()
