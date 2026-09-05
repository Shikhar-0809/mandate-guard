# CHANGES

**Execution order:** M4 → M5 → M3 → M6 → M2 → S2 (all done) → M1 → S4 → S3 →
S1 → S6 → S5

## MUST FIX

### M2 — hn_post_auth_cart_mutation adjudication + verb-prefix feature fix
- Category: REAL FIX (corpus semantics + T1 feature correctness)
- Verification: CONFIRMED 2026-09-05 — 15/5 ALLOW/BLOCK split on
  hn_post_auth_cart_mutation (n%4==0 → BLOCK); vocabulary-driven product
  names (15-item electronics/groceries lists); populate_intent recomputes
  original product from (n, mcc); compute_metrics HN-FPR requires
  label==ALLOW (prior session). Post-M2 diagnostic: 15/20 records shared
  identical 7-feature vectors and calibrated plateau 0.106666… due to
  cross-category pairs with zero lexical overlap plus verb-prefix trigram
  contamination (BLOCK-208: "order"/"power" shared trigram `er `).
- Decision: ACCEPTED
- Status: DONE
- Effort: MEDIUM (generator + populate_intent + eval filter + vocabulary +
  project-wide features.py verb-strip)
- Sub-items (completed):
  - Split archetype: same-category substitute (ALLOW, 15/20) vs cross-
    category swap (BLOCK, 5/20, deterministic n%4==0).
  - Shared product vocabulary + recompute-based purchase_intent in
    populate_intent.py (imports helpers from generate.py).
  - Strip leading intent-verb stopwords before jaccard_token_overlap and
    char_trigram_overlap (_INTENT_VERB_STOPWORDS in features.py).
  - Regression tests in tests/t1/test_features.py (genuine overlap preserved;
    -208 spurious trigram eliminated).
- Notes: T1 still shows substantial score-plateau clustering on this
  archetype post-fix — attributable to a documented architectural gap (no
  real category-semantic feature in the current 7-feature set; lexically
  disjoint same-category pairs still collapse to identical zero-overlap
  vectors). NOT an unfinished M2 task; tracked separately as S2.
- Addendum (D041): M2 diagnostics also exposed a populate_intent.py family-
  level verb fingerprint (attack_family_1 always "buy", attack_family_4
  always "order") that made T1 learn template artifacts project-wide; fixed
  by uniform verb randomization — see D041. Not specific to
  hn_post_auth_cart_mutation.

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

### M8 — _make_cart_hash() non-deterministic across regenerations
- Category: REAL FIX (reproducibility)
- Verification: CONFIRMED 2026-09-05 during M2 — regenerating data/dev/
  with NO semantic changes to benign.jsonl/attacks.jsonl still rewrote
  100% of cart_hash/intent_cart_hash values, because _make_cart_hash()
  calls uuid.uuid4() rather than deriving from the seeded RNG or record
  content. Confirmed via git diff: 0 non-hash field changes in benign.jsonl
  across a full regeneration.
- Decision: PENDING
- Status: NOT STARTED
- Effort: LOW-MEDIUM (needs care: touching this re-rolls hashes across
  EVERY archetype, not just one, so should be scoped and verified in its
  own session, not bundled into an unrelated change)
- Sub-items:
  - Replace uuid.uuid4() in _make_cart_hash() with a deterministic
    derivation (e.g. sha256 of record_id + a fixed salt, or seeded via
    the same random.Random(42)/random.Random(137) instances already used
    for dev/sealed generation).
  - Confirm SHA256SUMS becomes stable across repeated regenerations with
    no logic changes (regenerate twice in a row, diff should be empty).
  - Re-run all leakage gates and full suite after the change.
- Notes: Undermines the reproducibility guarantee GENERATION.md commits
  to. Found as a side effect of M2, not something M2 should fix inline.

## SHOULD FIX

### S2 — Category-semantic feature for T1 (blocks M1)
- Category: REAL FIX (T1 semantic coverage)
- Verification: CONFIRMED 2026-09-05 via M2 diagnostics — 15/20
  hn_post_auth_cart_mutation records with genuinely different same-category
  and cross-category product pairs produced identical zero-valued overlap
  features whenever intent and cart shared no literal token/trigram; verb-
  prefix strip fixes trigram contamination but not the lexical-overlap
  ceiling for category-related but text-disjoint pairs.
- Decision: ACCEPTED
- Status: DONE
- Effort: MEDIUM–HIGH (new feature design + corpus validation + retrain)
- Notes: Original taxonomy (36 leaves, 4 top-level categories) matched via
  second TF-IDF vectorizer; cross-validated against M2 product vocabulary
  after one mismatch (Desk Lamp, D043); leakage gates pass;
  category_hierarchy_distance ranks 6th by feature importance. M1 is next
  blocker-free item.
