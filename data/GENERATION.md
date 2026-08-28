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

## purchase_intent field

Every serialized record includes `purchase_intent`, a string stating what the
principal authorized the mandate for. Benign, hard-negative, and dev attack
records leave it empty (`""`), meaning no stated purchase intent. Sealed
family 13 records populate it with archetype-specific strings (ASSUMPTION — the
exact wording is synthetic, not sourced from production mandate text).

## Family 13 — semantic attacks (sealed only)

Family 13 adds 25 sealed-only attack records across four archetypes (cycled by
record index mod 4):

1. **semantic_category_drift** — grocery purchase intent, electronics cart item
2. **semantic_quantity_abuse** — single-item intent, cart quantity 8
3. **semantic_brand_substitution** — Brand-A intent, Brand-B product name
4. **semantic_purpose_mismatch** — office-supplies intent, luxury item cart

All family 13 records pass T0 by design: amount under cap, merchant and MCC in
scope, no cart hash pin, no delegation violations. The violation is semantic
mismatch between `purchase_intent` and cart content — T1/T2 territory.

## Integrity

Each split ships a GNU-format `SHA256SUMS`. `tests/test_corpus.py` verifies
hashes before running leakage gates.

## Research validation

`python data/validate_seeds.py --seeds 1 50` probes generator stability across
seeds. It is not part of CI.
