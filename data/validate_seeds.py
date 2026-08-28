"""Probe corpus generator stability across random seeds."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

_GENERATE_SPEC = importlib.util.spec_from_file_location(
    "corpus_generate", PROJECT_ROOT / "data" / "generate.py"
)
assert _GENERATE_SPEC is not None and _GENERATE_SPEC.loader is not None
_corpus_generate = importlib.util.module_from_spec(_GENERATE_SPEC)
sys.modules[_GENERATE_SPEC.name] = _corpus_generate
_GENERATE_SPEC.loader.exec_module(_corpus_generate)
DEFAULT_NOW = _corpus_generate.DEFAULT_NOW
validate_generator_across_seeds = _corpus_generate.validate_generator_across_seeds
generate_attacks = _corpus_generate.generate_attacks
generate_benign = _corpus_generate.generate_benign
generate_hard_negatives = _corpus_generate.generate_hard_negatives

from tests.test_corpus import provenance_probe_auc, shuffled_label_auc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate corpus generator seeds.")
    parser.add_argument(
        "--seeds",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        required=True,
        help="Inclusive-exclusive seed range, e.g. 1 50 for range(1, 50)",
    )
    parser.add_argument(
        "--now",
        default=DEFAULT_NOW.isoformat(),
        help="ISO datetime reference for generation",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    start, end = args.seeds
    now = datetime.fromisoformat(args.now)
    summaries = validate_generator_across_seeds(range(start, end), now)

    print(
        "seed | attack_rate | shuffled_auc_mean | shuffled_auc_max | provenance_auc | all_pass"
    )
    for summary in summaries:
        seed = int(summary["seed"])
        rng_records = _records_for_seed(seed, now)
        shuffled = shuffled_label_auc(rng_records)
        shuffled_mean = sum(shuffled) / len(shuffled)
        shuffled_max = max(shuffled)
        provenance = provenance_probe_auc(rng_records)
        all_pass = (
            all(0.45 <= value <= 0.55 for value in shuffled) and provenance < 0.60
        )
        attack_rate = float(summary["attack_rate"])
        print(
            f"{seed:4d} | {attack_rate:11.4f} | "
            f"{shuffled_mean:17.4f} | {shuffled_max:16.4f} | "
            f"{provenance:14.4f} | {all_pass}"
        )


def _records_for_seed(seed: int, now: datetime) -> list[dict[str, object]]:
    import random

    rng = random.Random(seed)
    records = (
        generate_benign(rng, 800, now)
        + generate_hard_negatives(rng, 20, now)
        + generate_attacks(rng, 30, now, [1, 2, 3, 4, 5, 6, 7])
    )
    _corpus_generate._spread_decoy_families(rng, records)
    _corpus_generate._permute_provenance_fields(rng, records)
    return records


if __name__ == "__main__":
    main()
