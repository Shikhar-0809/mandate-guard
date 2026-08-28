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
- **sealed**: seed `137`, attack families 8–12 only

## Integrity

Each split ships a GNU-format `SHA256SUMS`. `tests/test_corpus.py` verifies
hashes before running leakage gates.

## Research validation

`python data/validate_seeds.py --seeds 1 50` probes generator stability across
seeds. It is not part of CI.
