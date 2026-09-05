# CHANGES

**Execution order:** M4 → M5 → M3 → M6 → M2 → S2 (M4/M3/M6/M2/S2 done, M5
  in progress — see M5 entry) → M1 → S4 → S3 → S1 → S6 → S5

## MUST FIX

### M3 — T1 returns T1Result (not bare float) when purchase_intent is empty
- Category: REAL FIX
- Verification: CONFIRMED via D035 (T1Result contract for empty
  purchase_intent), already committed prior to this session. Cross-
  referenced in D060 ("fn redefined as ALLOW-and-label=BLOCK... matching
  M3's NO_SEMANTIC_EVIDENCE").
- Decision: ACCEPTED
- Status: DONE
- Notes: Confirmed via DECISIONS.md citation and D060's cross-reference
  only — not independently re-verified against t1.py source this session.

### M4 — Repo public-flip prerequisites (secrets hygiene)
- Category: SECURITY
- Verification: CONFIRMED 2026-09-05 this session — .env present in
  .gitignore (line 2); `git log --all --oneline -- .env` returns empty
  (never committed on any branch); `gitleaks detect --source .
  --log-opts="--all"` run this session: 82 commits scanned, ~16.48MB,
  0 leaks found.
- Decision: ACCEPTED — gitleaks-only scan coverage is an explicit,
  signed-off scope decision (Shikhar, 2026-09-05), not an oversight.
  trufflehog was never installed or run against this repo at any point;
  any earlier claim that it was should be disregarded as unconfirmed.
- Status: IN PROGRESS
  - Secrets scan: DONE
  - Repo visibility flip: NOT DONE — deliberately deferred to submission
    day; Track 02 judging is confirmed post-deadline, private-until-then
    is safe.
- Notes: First real, evidence-backed CHANGES.md entry for M4. Supersedes
  all prior unwritten/narrated claims about this item.

### M5 — Reframe headline metrics/README (D059 result, D062 correction)
- Category: REPORTING
- Verification: First pass CONFIRMED via commit 0dc6d11 ("M5: reframe
  README/baselines with real current numbers..."), committed. Second
  corrective pass CONFIRMED this session via `git diff README.md` against
  the current uncommitted working tree — removes the D059 magnitudes
  (recall 0.853→0.768, HN block rate 0.133→0.164) from headline framing,
  replaces with D062-accurate language (operating point unreachable under
  corrected cost accounting; magnitude superseded; qualitative direction
  unconfirmed pending S2). Matches D062's explicit requirement.
- Decision: ACCEPTED
- Status: IN PROGRESS — first pass DONE and committed (0dc6d11); second
  corrective pass DRAFTED and correct in the working tree, but UNCOMMITTED
  and not yet run through a full make check.
- Notes: Do not cite M5 as fully DONE until the D060–D062 commit batch
  lands and make check passes against the corrected README.

### M6 — Unify cascade behind check(...) -> Verdict
- Category: REAL FIX (correctness)
- Verification: CONFIRMED via D036 (cascade.check() unifies T0→T1→T2
  behind Verdict; empty intent → ALLOW with NO_SEMANTIC_EVIDENCE) and
  D037 (cascade validation additive; continuous-score path preserved in
  run_eval for threshold/curve metrics; cascade.check() Verdict-counting
  added as a separate additive layer at fixed tau_star). Both committed
  prior to this session.
- Decision: ACCEPTED
- Status: DONE
- Notes: Confirmed via DECISIONS.md citations only — not independently
  re-verified against cascade.py source this session.

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

### M9 — make check gate does not exist; RULES 7 has never been satisfied as a whole
- Category: REAL FIX (tooling / process integrity)
- Verification: CONFIRMED 2026-09-05 this session — `make` not found in
  PowerShell or Git Bash; no Makefile in repo root; see D063.
- Decision: DEFERRED — Shikhar: continue running checks individually via
  Cursor for now; formally tracked as a gap, not resolved this session.
- Status: NOT STARTED
- Effort: UNKNOWN — depends on chosen approach (WSL2 + real Makefile,
  or a Python check-runner script); not scoped this session.
- Sub-items (for whenever this is picked up):
  - Confirm which RULES 7 components actually exist as runnable commands
    in this repo today (ruff, mypy, pytest, pytest -m contract, vulture,
    coverage, and specifically whether `eval.guard` and
    `tools/audit_verify.py --sample 200` exist at the paths RULES.md
    implies) before assuming an equivalent command list.
  - Decide: Makefile (needs make installed — not present, needs WSL2 or
    a Windows make port) vs. a Python script (e.g. scripts/check.py)
    that runs the same steps with no external tool dependency.
  - Once built, run it successfully end-to-end at least once before
    citing it in any DONE status.
- Notes: Every prior and current DONE status in this file should be read
  with this caveat: verified via individual tool runs pasted by Cursor,
  not via a combined RULES-7 gate, because that gate has never existed
  as a runnable thing. D004 (2026-08-27) flagged this originally with an
  expiry condition ("Step 7") that was apparently never reached or
  tracked; this entry supersedes that silence, not the substance of D004.

### M10 — Cost functions modeled a fictional HOLD tier for T0+T1-only evaluation
- Category: REAL FIX (correctness -- supersedes D061/D062's framing)
- Verification: CONFIRMED 2026-09-05 this session via live execution --
  see D064 for full derivation. 347/347 tests pass post-fix (was 346/348
  pre-fix, 2 real failures); dev full-intent recall_seen reaches 1.0000
  (was 0.9818); tau_star for full-intent dev is now a genuine interior
  value 0.220 (was degenerate 1.000).
- Decision: ACCEPTED
- Status: DONE. Re-derivation completed 2026-09-05 per D065/D066 --
  baselines_sealed_semantic.json re-run once under the corrected model;
  result numerically identical to the superseded D059 file (verified
  genuine, not stale -- see D066), T2 kill criterion still not met.
- Effort: Discovered and fixed within this session; started as a two-test
  failure investigation, expanded twice (first to compute_metrics's
  parallel instance of the same bug, then to the deeper architectural
  question of whether HOLD exists at all without T2) before landing on
  the real fix.
- Sub-items:
  - src/mandate_guard/eval.py: compute_cost, _cost_partition_at_tau,
    find_cost_optimal_threshold, compute_metrics, threshold_sweep all
    updated to two-way FP/FN cost, no HOLD term.
  - tests/test_eval.py: 2 tests deleted (tested removed 3-term API), 1
    new contract test added, 2 tests rewritten.
  - tests/test_eval_semantic.py: 2 tests rewritten to the two-way
    compute_cost signature.
  - scripts/run_eval_semantic.py: hold_cost/max_hold_rate removed from
    its find_cost_optimal_threshold call.
  - README.md: D061 HOLD-capacity paragraph replaced with D064
    supersession text.
  - Known remaining gap: run_eval.py's printed cost-model banner string
    still says the old three-term formula -- cosmetic, not yet fixed.
- Notes: This is the correct outcome of "no band-aids" -- what started as
  a request to fix one failing test surfaced a real architectural
  mismatch between the cost model and cascade.check()'s actual behavior,
  and got fixed at the root rather than patched at the symptom.

### M1 — Independent semantic sealed set
- Category: REAL EVAL FIX
- Verification: N/A (creates new artifacts; nothing to verify pre-work)
- Decision: PENDING
- Status: NOT STARTED
- Effort: HIGH (5-10 days)
- Blocks: S1 (simulator measures on new set), S6 (T2 calibration on new
  set), S5 (pitch needs independent-set numbers)
- Blocked on: S2 (done - category-semantic feature required before this
  corpus is meaningful)
- Sub-items:
  - 10 categories, ~50 items/category (500 total), ORIGINAL vocabulary -
    NOT Amazon Berkeley Objects or any external dataset (rejected: no
    precedent in this repo for external fetch-at-generation-time;
    contradicts D002/D022/D042's offline/keyless posture). Vocabulary
    built to align with taxonomy.py's category names from the start, not
    cross-checked after the fact.
  - Labels: ALLOW / DEVIATION / UNCERTAIN. Schema stays binary
    (ALLOW/BLOCK) project-wide - a normalization layer handles the
    3-way-to-2-way boundary, per the 4 conditions below. This is a
    deliberate design boundary, not a workaround:
    1. New function normalize_semantic_labels_for_training(records) in
       src/mandate_guard/ (not a throwaway script) - DEVIATION->BLOCK,
       ALLOW->ALLOW, UNCERTAIN dropped before reaching t1.train() /
       compute_metrics() / any shared pipeline call.
    2. Its own contract test: no UNCERTAIN record survives normalization;
       DEVIATION->BLOCK is deterministic.
    3. M1's own results file (baselines_sealed_semantic.json) reports
       real 3-way outcome counts - never reduced at the reporting layer.
    4. DECISIONS.md entry stating this plainly as a deliberate boundary
       (shared pipeline is mathematically binary by design), not a
       workaround.
  - New infrastructure (nothing generalizes as-is per recon):
    - data/sealed_semantic/ + its own SHA256SUMS, separate from
      data/sealed/ (existing sealed set stays frozen, untouched).
    - New --split sealed_semantic path in data/generate.py, or a separate
      generator script (decide at plan-turn time).
    - New load_sealed_semantic() in eval.py, parameterized rather than
      hardcoded like load_sealed_attacks().
    - New integrity test(s) in test_corpus.py, separate from
      test_sealed_family_coverage (families 8-13, must not be touched).
    - make seal-eval / evaluated_count do not exist yet (no Makefile at
      all, confirmed) - M1 either builds a minimal real version or
      explicitly defers it as its own tracked item.
  - Pre-registration BEFORE any corpus generation, matching existing
    sealed-set protocol spirit: DECISIONS.md entry committing exact
    record count, category list, label scheme, adjudication rule text,
    tau, and the T2 kill criterion for this corpus specifically (needs
    explicit sign-off as a real pre-registered number before generation,
    not asserted unilaterally). SHA-256 committed at freeze, "opened
    once."
- Notes: This spec was previously held only in Claude's session memory,
  never actually committed to CHANGES.md - this entry is the first time
  it exists as real, version-controlled project history. Prior references
  to "M1's spec" before this commit should be treated as unreliable.

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

### S3 — FastAPI /check endpoint + local demo UI
- Category: PRODUCTION-REALISM
- Verification: CONFIRMED 2026-09-05 this session -- six preset
  scenarios (legitimate purchase, amount over cap, wrong merchant, cart
  tampered, brand substitution, post-auth SKU swap) all verified via
  direct HTTP calls to /check AND via live browser screenshot
  (DevTools Elements + Console, fresh incognito load, zero real errors).
  All six verdicts/reason_codes/t1_scores matched expected values exactly,
  including the post-auth SKU swap case reproducing t1_score=0.228141
  matching the real hn_post_auth_cart_mutation archetype fixed earlier
  this session (D064).
- Decision: ACCEPTED
- Status: DONE
- Effort: Built in one session -- src/mandate_guard/api.py (FastAPI,
  reuses _record_to_t0_args + cascade.check() directly, no divergent
  contract-construction logic), web/index.html + web/app.js (vanilla,
  no framework, no build step).
- Sub-items:
  - POST /check accepts a flat record dict (same shape as corpus
    records), enable_t2 flag; returns verdict, reason_code, t0_triggered,
    t1_score, t2_evidence.
  - DEMO_TAU=0.220 (full-intent dev tau_star, verified D064/this session).
  - Malformed-request path returns 422 with clear message, confirmed
    does not crash the server.
  - UI: two-column layout, scenario picker auto-populates form and
    triggers a check immediately, staged T0/T1/T2 trace reveal, prominent
    verdict + T1 score display, raw JSON disclosure.
- Notes: Not built because Track 02 requires it -- built because it
  closes the "is this a real system" question in seconds and supports
  the pitch video demo. Local-only, not a production endpoint.
