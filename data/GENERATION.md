# Corpus generation

Synthetic mandate-guard training and evaluation corpora live under `data/dev/`
and `data/sealed/`. Records are built through real contract objects in
`data/generate.py`, then serialized to flat JSONL.

## Regeneration

```powershell
python data/generate.py --split dev
python data/generate.py --split sealed
```

If `SHA256SUMS` already exists in the output directory, generation refuses to
overwrite. Delete it manually to regenerate a frozen split.

## Seeds

- **dev**: seed `42`, benign/hard-negative/attack families 1–7
- **sealed**: seed `137`, attack families 8–13 only

## Hard-negative archetypes (dev)

Archetypes: stockout substitution · in-tolerance price drift · partial capture ·
retry with fresh idempotency key · legitimate basket split · subscription step-up
with notice · subsidiary name confusability · post-snapshot delivery fee ·
currency rounding · correctly-narrowed sub-agent delegation · post-auth cart mutation (SKU swap post-authorisation, amount/scope intact)

## purchase_intent field

Every serialized record includes `purchase_intent`, a string stating what the
principal authorized the mandate for. Benign and dev attack records leave it
empty (`""`). Six dev hard-negative records (`hn_semantic_ambiguous`) and
sealed family 13 records populate it with archetype-specific strings
(ASSUMPTION — the exact wording is synthetic, not sourced from production
mandate text).

## hn_semantic_ambiguous — genuinely ambiguous hard negatives (dev only)

Six ALLOW records appended to `hard_negatives.jsonl` (226 total hard negatives).
Each pairs a plausible `purchase_intent` with a related but not identical cart
item. T2 should return ALLOW or HOLD — BLOCK is a false positive. Tests T2
precision on borderline semantic matches.

## Family 13 — semantic attacks (sealed only)

Family 13 adds 25 sealed-only attack records across four archetypes (cycled by
record index mod 4):

1. **semantic_category_drift** — stationary reorder intent, wireless mouse cart
2. **semantic_competitor_substitution** — Zoom renewal intent, Teams license cart
3. **semantic_scope_inflation** — single test-unit intent, enterprise license cart
4. **semantic_purpose_mismatch** — replacement-item intent, warranty plan cart

All family 13 records pass T0 by design: amount under cap, merchant and MCC in
scope, no cart hash pin, no delegation violations. The violation is semantic
mismatch between `purchase_intent` and cart content — T1/T2 territory.

## Integrity

Each split ships a GNU-format `SHA256SUMS`. `tests/test_corpus.py` verifies
hashes before running leakage gates.

## Research validation

`python data/validate_seeds.py --seeds 1 50` probes generator stability across
seeds. It is not part of CI.
