# CHANGES

## MUST FIX

### M7 — Fix pre-existing mypy --strict debt
- Category: REAL FIX (correctness / tooling hygiene)
- Verification: CONFIRMED via M3 implementation pass 2026-09-05 — `mypy
  --strict` on the full tree surfaces 9 pre-existing errors, none in code
  touched by M3, none newly introduced. First time mypy --strict was run
  project-wide and confirmed; RULES 6/7 require it pass as part of
  `make check` for any task to count as "done" — it currently does not,
  meaning no task closed before this point actually satisfied RULES 6 on
  the mypy axis, even though pytest was green.
- Decision: DEFERRED (Shikhar: log and proceed, fix separately)
- Status: NOT STARTED
- Effort: LOW (1-2 days, mechanical — missing type args, missing param
  annotations, two `object not iterable` issues, one missing return
  annotation; no design decisions)
- Errors (from M3 pass):
  - src/mandate_guard/features.py:41 — missing type args for generic "set"
  - src/mandate_guard/features.py:67 — missing param type annotation
  - src/mandate_guard/features.py:72 — missing type args for generic "list"
  - src/mandate_guard/features.py:88 — sklearn.metrics.pairwise untyped import
  - src/mandate_guard/t1.py:180 — sklearn.feature_extraction.text untyped import
  - src/mandate_guard/t1.py:187 — "object" not iterable
  - src/mandate_guard/t1.py:300 — missing return type annotation
  - src/mandate_guard/eval.py:57 — "object" not iterable
  - src/mandate_guard/eval.py:196 — "object" not iterable
- Notes: Until this is fixed, any "task done" claim is done-except-mypy.
  Explicitly accepted as a known gap, not an oversight, as of this entry.

## SHOULD FIX
