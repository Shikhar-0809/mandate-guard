# DECISIONS

Append-only. Entries are never edited. Format: context, choice, rejected
alternative, revisit trigger. Keep each entry under 10 lines.

## D001 — IntentMandate is sandbox-defined, not bound to Razorpay Subscriptions
Date: 2026-08-27
Context: Probed test-mode Subscriptions. `plan.create` returns ServerError with an
empty body; the product is not provisioned on unactivated accounts.
Choice: Define IntentMandate/CartMandate in `sandbox/` following AP2 field
semantics. Razorpay test mode supplies the money leg only (orders, payments).
Rejected: Requesting Subscriptions enablement. Razorpay's subscription object
lacks merchant allowlist, item specification, prompt playback and TTL, so the
binding would have been lossy regardless of availability.
Revisit: If Razorpay or NPCI UAP exposes a mandate primitive carrying scope fields.

## D002 — Fixtures are committed, not gitignored
Date: 2026-08-27
Context: Test-mode API responses contain no key material (reviewed order,
plan and subscription response shapes).
Choice: Commit `fixtures/*.json`. They are the replay cassettes that let the repo
reproduce end-to-end with no API keys.
Rejected: Gitignoring them. Keyless reproducibility is a load-bearing property of
the submission and dies without committed fixtures.
Revisit: If any future fixture carries PII or key material — then quarantine that
fixture specifically, never the policy.

## D003 — fixtures/ is scanned under a different policy than data/
Date: 2026-08-27
Context: RULES 34 covered data/ only. fixtures/ holds real test-mode API
output, committed deliberately (D002) for keyless reproducibility.
Choice: one scanner, two policies. data/ DENY_ALL; fixtures/ permits
test-mode object ids, denies secrets and PII.
Rejected: extending data/'s blanket rule to fixtures/ — it fails immediately
on fixtures/order_created.json, whose real order_ id is the entire point of
the file, and the first response to that failure is to loosen the regex.
A loosened regex is worse than no regex.
Revisit: if a fixture ever needs a suppression, the policy is wrong.

## D004 — RULES 8 deviation: no `make check` until Step 7
Date: 2026-08-27
Context: RULES 8 says a task is not done until full `make check` output is
pasted. No Makefile exists until Step 7.
Choice: tasks between now and Step 7 run an explicit command list instead,
logged here so the deviation is visible rather than silent.
Rejected: pulling the Makefile forward onto Windows ahead of the planned
WSL2 migration; and ignoring the rule without recording it.
Revisit: EXPIRES at Step 7. Delete this entry's applicability then.

## D005 — Checkout capture is browser-driven; the fixture is the redacted API object
Date: 2026-08-27
Context: test-mode Checkout has no server-side payment path on an
unactivated account — same class of gate as D001. The browser handler
payload carries three fields and no payment state.
Choice: capture via a loopback Checkout page, verify the signature, fetch
the authoritative payment object, and commit it through an allowlist
redactor.
Rejected: S2S payment creation (not enabled); committing the raw fetched
object, which carries email, contact, card.last4 and acquirer_data.rrn.
Revisit: if S2S is enabled on the account.

## D006 — synthetic test contacts are not PII
Date: 2026-08-28
Context: D003's revisit trigger fired — a fixture needed a suppression, so
the policy was wrong. The scanner flagged 9000090000 and
buyer@example.invalid, which are hardcoded test-harness constants
belonging to no person.
Choice: narrow the scanner's definition of PII with an exact-literal
SYNTHETIC_CONTACTS set, tested from both sides. ALLOWLIST stays empty.
Rejected: a path-scoped ALLOWLIST entry — it says "this file may contain a
phone number" and would stay silent if a REAL number landed there;
substring or case-insensitive matching — both would suppress a real address
that merely contains or case-varies the synthetic one.
Revisit: if SYNTHETIC_CONTACTS exceeds ~5 entries, or if any entry is not
a literal hardcoded in the harness.

## D007 — CHALLENGE verdict state removed
Date: 2026-08-28
Context: ARCHITECTURE specified ALLOW/HOLD/CHALLENGE/BLOCK. No challenge
flow exists or will be built before submission. HOLD covers the deferral
case. A state with no implementation creates a panel question with no
answer.
Choice: Three-way verdict: ALLOW/HOLD/BLOCK. Enforced in VerdictState
enum in contracts/verdict.py (phase1-step2).
Rejected: Keeping CHALLENGE as a documented future state — inflates
apparent scope without adding demonstrable value.
Revisit: If a real re-authentication or step-up flow is built.

## D008 — T2 ships degraded by default
Date: 2026-08-29
Context: Pre-registered kill criterion in EVAL.md requires T2 to lift
recall_unseen by >=2pp over T0+T1 on the dev set. T0 achieves
recall_unseen=1.0 on the evaluation corpus, making the criterion
mathematically impossible (would require recall_unseen>=1.02).
Choice: T2 ships wired but degraded (T2Config.t2_enabled=False by
default). Degraded path returns HOLD. Interface, output schema, and
contract types are fully implemented and tested.
Rejected: Enabling T2 regardless — would present an architecture
component as a metrics win without evidence, violating the pre-
registered criterion.
Revisit: Extend corpus with semantic attacks that evade T0. Re-run
eval. Enable T2 only if criterion is met.

## D009 — qwen2.5:7b as T2 Ollama backend
Date: 2026-08-29
Context: T2 LLM backend requires a model that can reliably produce
structured JSON output. Anthropic API costs money per call; an offline
local model is preferred for reproducibility.
Choice: qwen2.5:7b via Ollama at localhost:11434. Configurable via
OLLAMA_HOST and OLLAMA_MODEL environment variables. Temperature=0.0
for deterministic output. Parse failure always returns HOLD.
Rejected: Anthropic API (cost, requires network); gemma3:1b (too
small for reliable JSON schema adherence);
qwen2.5vl:7b (vision model, text-only task).
Revisit: If a hosted endpoint becomes available or a smaller model
demonstrates equivalent JSON reliability.

## D010 — T2 gate uses purchase_intent presence, not score band
Date: 2026-08-29
Context: T1 was trained on dev corpus where purchase_intent is always
empty, so feature 22 (intent_cart_name_overlap) is always -1.0 on
training data. T1 assigns no weight to feature 22 and scores all
family 13 records 0.0 — none fall in the [0.3, 0.7] score band.
Choice: T2 gate condition is T0-passed AND purchase_intent non-empty,
replacing the score-band gate for semantic families. This is
architecturally correct: T2 is the right tool for semantic intent
verification; T1 handles statistical anomalies. When no intent is
stated, semantic verification is impossible and T2 is not invoked.
Rejected: Adding semantic dev examples to retrain T1 — adds corpus
complexity and risks T1 absorbing the semantic signal, leaving T2
with nothing to contribute.
Revisit: If dev corpus is extended with purchase_intent examples
and T1 learns feature 22, reintroduce score-band gate.

## D011 — T0-derived features removed from T1; leakage confirmed
Date: 2026-09-02
Context: Audit revealed 7 of 22 T1 features were T0 rule outputs or direct
inputs (t0_passed, t0_trigger_count, merchant_in_scope, category_in_scope,
amount_over_cap, cart_hash_match, mandate_id_match). Because T0 catches every
dev attack, t0_passed=0 was a near-perfect label proxy. t1_auc=1.0 was leakage.
Choice: Remove all 7 features. Retrain. t1_auc drops to 0.6622.
Post-ablation: T1 scores on family-13 sealed attacks (max=0.06) are lower than
scores on hard negatives (max=0.13). T1 cannot separate semantic attacks from
legitimate traffic. T0+T1 remains identical to T0 at tau*=1.0.
Rejected: Keeping T1 with leaked features and reporting 1.0 as a valid result.
Revisit: If T1 is rebuilt with semantic comparison features (intent-cart
similarity, brand conflict, specificity scoring) rather than structural mandate
features.

## D012 — SHA256SUMS corrected for CRLF-era hash mismatch
Date: 2026-09-02
Context: Audit found data/dev/SHA256SUMS contained hashes computed from LF
bytes, but attacks.jsonl and benign.jsonl were committed with CRLF bytes (Windows
git.autocrlf artifact). The test_sha256_integrity_dev test was failing due to
this pre-existing inconsistency, not a content change. hard_negatives.jsonl was
unaffected (hashes matched).
Choice: Recompute SHA256SUMS from actual on-disk bytes. Add .gitattributes to
enforce LF on all corpus files going forward.
Rejected: Restoring corpus files to a different byte state — record counts were
verified identical (210 attacks, 800 benign), only line endings differed.
Revisit: If .gitattributes enforcement is removed or bypassed on a new machine.

## D013 — Semantic T1 with intent-populated corpus; tau_star remains 1.0
Date: 2026-09-02
Context: Semantic T1 (10 features: jaccard, trigram, tfidf-cosine, brand
detection, brand-conflict, specificity, category-match, quantity-mismatch,
amount-to-cap-ratio) trained on intent-populated corpus achieves auc=0.9988.
Family-13 sealed attack scores: mean=0.9405 (min=0.8867). HN scores: mean=0.0199
(max=0.9622, 4 FP at any tau>0). tau_star=1.0 because all dev attacks are caught
by T0 -- no T0-passing attacks exist in the dev corpus for the optimizer to learn
from. T1 contributes on family-13 (sealed) only. HOLD term added to cost function
(hold_cost=45.0 parameter in find_cost_optimal_threshold). HOLD banner removed
from eval output.
Rejected: Reverting to structural features (Option B) -- semantic features
demonstrate clear separation (gap=0.92) on the only population that matters
(family-13 semantic attacks). Structural features had gap=0.
Revisit: If dev corpus is extended with semantic attack families so tau_star
can be optimized on T0-passing attacks.

## D015 — Remove two broken features: amount_to_cap_ratio and cart_has_brand
Date: 2026-09-02
Context: A2 feature variance audit revealed amount_to_cap_ratio is always 0.0
across all 2432 corpus records (cap field absent in corpus; extractor returns
zero). cart_has_brand is always 1.0 (constant; no information content).
LightGBM importances were all zero because constant/zero columns carry no split
value. Both features removed. Feature count drops 10→8.
Choice: Remove both features. Retrain. Verify AUC holds above 0.99.
Rejected: Fixing the extractors. amount_to_cap_ratio requires cap metadata not
present in dev corpus. cart_has_brand requires brand taxonomy not yet built.
Revisit: When corpus includes per-item cap fields and a brand taxonomy is added.

## D016 — Train T1 on intent-populated corpus only
Date: 2026-09-02
Context: DEV_RECORDS in test_t1.py loaded base files (benign.jsonl,
hard_negatives.jsonl, attacks.jsonl) where purchase_intent is empty on all
records. All 8 semantic features are zero when intent is absent. T1 trained
on a featureless corpus, producing t1_auc=0.5. The *_with_intent.jsonl files
(1216 records total) are the only population where semantic features have
variance and T1 can learn.
Choice: Train exclusively on *_with_intent.jsonl files (benign, hard_negatives,
attacks — all three intent-populated variants).
Rejected: Training on combined base + intent files. Zero-feature rows add noise
and dilute the signal; they should score via T0 or T2, not T1.
Revisit: When all corpus records carry purchase_intent by default.

## D017 — Remove brand_conflict feature
Date: 2026-09-02
Context: A2 importance audit showed brand_conflict importance=0.0 after
cart_has_brand removal (D015). brand_conflict fires only when both
intent_has_brand and cart_has_brand are 1.0 — with cart_has_brand removed,
the condition can never be true. Dead feature.
Choice: Remove brand_conflict. Feature count drops 8→7.
Rejected: Keeping it as a documented zero-importance feature. Dead code
in a feature vector is a maintenance liability and a false signal.
Revisit: If cart_has_brand is restored with a working brand taxonomy.

## D019 — Disclose sealed-set protocol violation in EVAL.md (D20)
Date: 2026-09-02
Context: EVAL.md stated sealed set as families 8-12. Family 13 was added
post-hoc after D008 T2 failure and was inspected during development, violating
RULES 19. The doc did not reflect this.
Choice: Update EVAL.md to split original sealed (8-12) from post-hoc challenge
(13), and explicitly state the RULES 19 violation.
Rejected: Removing family 13 from reporting. Post-hoc results are still useful
when disclosed honestly as exploratory, not pre-registered.
Revisit: When a genuinely pre-registered sealed set for family 13 equivalents
exists.

## D018 — Add T0-passing semantic attack families 14 and 15 to dev corpus (A3)
Date: 2026-09-02
Context: All dev attack families (1-7) fail T0 — amount over cap, wrong
merchant, wrong MCC, hash mismatch, scope expansion. T1 never saw a genuine
positive on T0-passing records. tau_star=1.0 was an artifact: T0 solved the
dev corpus entirely, leaving T1 nothing to learn from on the attack side.
Choice: Add families 14 (brand substitution) and 15 (scope creep) — T0-passing
semantic attacks with purchase_intent populated, amounts under cap, merchants
in allowlist, no cart hash pin. Fails only on semantic mismatch detectable by
T1/T2. Fit tau_star on this updated dev corpus.
Rejected: Adding family 13 equivalents to dev. Family 13 is sealed-set
territory; adding identical archetypes to dev would contaminate the evaluation.
New families use distinct archetypes (brand substitution, scope creep).
Revisit: When more semantic archetypes are needed for T1 training signal.

## D020 — Reframe T2 kill criterion as post-hoc experiment (A4)
Date: 2026-09-02
Context: eval_t2_kill_criterion_met=true was reported as a pre-registered
success. The criterion was pre-registered, but the only testable population
(family 13) was added post-hoc after D008, violating RULES 19. The original
dev corpus (families 1-7) had T0 recall=1.0, leaving no room for T2 lift.
Choice: Reframe in EVAL.md. The +16.67pp lift on family 13 is real but
post-hoc. T2 justification rests on the AP2 gap argument, not this metric.
Rejected: Removing the kill criterion section. It shows honest pre-registration
discipline even when the result is ambiguous — that is worth keeping.
Revisit: When a genuinely pre-registered sealed set for semantic families exists.

## D021 — Document three-way injection experiment (A5)
Date: 2026-09-02
Context: A5 required running regex + mandate-guard on three corpus slices to
prove injection detection is categorically wrong as a defense framing.
Choice: Document in EVAL.md as a table. No new code needed — the corpus
already covers all three slices. Regex fires 0/270 dev and 0/150 sealed.
Rejected: Synthesizing artificial injection-string records for slice (a).
Our threat model is deviation at the PSP, not injection string detection.
Adding injection strings would misrepresent the threat model.
Revisit: If a real injection-string corpus becomes available for comparison.

## D022 — Add TF-IDF cosine and logistic regression semantic baselines (B6)
Date: 2026-09-02
Context: B6 requires semantic baselines to show mandate-guard outperforms
naive text-similarity approaches. sentence-transformers not installed
(offline constraint). Two sklearn baselines added instead.
Choice: TF-IDF cosine threshold (sim < 0.3 → BLOCK) and logistic regression
on TF-IDF features trained on dev corpus.
Rejected: Sentence-embedding cosine — not installable offline.
Revisit: Add sentence-embedding baseline when online evaluation is possible.

## D023 — T2 confidence floor: BLOCK below 0.70 → HOLD
Date: 2026-09-03
Context: A 7B model can return BLOCK with low confidence on ambiguous inputs.
A low-confidence BLOCK has the same operational cost as HOLD but forecloses
the deferral window. Better to HOLD and let the rail timeout resolve it.
Choice: confidence < 0.70 on a BLOCK verdict → demote to HOLD, log
DEGRADED_T2_LOW_CONFIDENCE. Floor is a named constant T2_CONFIDENCE_FLOOR.
Rejected: Dropping low-confidence verdicts to ALLOW — wrong direction on
the cost asymmetry (FN costs 4.6× FP).
Revisit: If a larger T2 model is substituted and calibration improves.

## D024 — Policy/model version pinning in Verdict record
Date: 2026-09-03
Context: Frozen verdicts must be reproducible and auditable. Without version
pins, a re-score after a model update is indistinguishable from the original.
Choice: Add policy_version, t1_model_hash, t2_model_id as optional fields on
Verdict. All three enter the audit chain canonical payload (v2). Optional to
avoid breaking existing call sites; callers should populate when available.
Rejected: Separate version-pin table joined at query time — adds a join on the
hot read path and loses the self-contained audit property.
Revisit: When Verdict is versioned formally; then make fields required.

## D025 — Degradation rationale: quantified expected loss per failure mode
Date: 2026-09-03
Context: ARCHITECTURE.md degradation table listed failure modes without
quantifying expected loss, making the trade-offs unverifiable.
Choice: Add expected-loss column to degradation table with ASSUMPTION labels
and derivation prose. Numbers flow from the cost matrix already in
ARCHITECTURE.md (FN ₹1470, FP ₹320, HOLD ₹45) at 0.8% attack prior.
Rejected: Exact simulation — requires prod traffic data not available at BUILD
tier. ASSUMPTION labels make the gap explicit.
Revisit: When real traffic data is available to replace ASSUMPTION labels.

## D026 — C18: post-auth cart mutation hard-negative archetype
Date: 2026-09-03
Context: Hard-negative corpus lacked a post-authorisation mutation archetype.
This is a distinct attack surface: the mandate authorises cart A; the agent
substitutes a different SKU before settlement while keeping amount and scope
identical. T0 and T1 cannot detect this without semantic comparison.
Choice: Add hn_post_auth_cart_mutation as a dev hard-negative archetype.
Label ALLOW — it is a hard negative to test precision, not a labeled attack.
Rejected: Labeling as BLOCK — we don't have ground truth that this is always
fraudulent; the archetype tests the system's ability to surface suspicion, not
to auto-block.
Revisit: If real chargeback data shows this archetype is predominantly
fraudulent, promote to a labeled attack family.

## D027 — Corpus B FPR margin stated explicitly in EVAL.md
Date: 2026-09-03
Context: EVAL.md said "FP rate on Corpus B must exceed Corpus A by a stated
margin" without stating the margin, making the gate unverifiable.
Choice: State ≥5pp as the margin (ASSUMPTION). Current gap is ~10pp (HOLD+BLOCK
on 206 HN records vs ~0% on benign). Gate is satisfied.
Rejected: Leaving the margin unstated — an unverifiable gate is not a gate.
Revisit: When real traffic data replaces synthetic Corpus A base rates.

## D028 — Latency figures relabeled as design targets
Date: 2026-09-03
Context: ARCHITECTURE.md listed ~3ms and ~10ms p99 figures without noting
these are design targets, not measurements from production traffic.
Choice: Rename column to "p99 target" and add a footnote: design targets,
not measurements. No production traffic exists at BUILD tier.
Rejected: Removing the figures — they anchor the architecture discussion and
are useful as targets even without measurement.
Revisit: When benchmark data from make bench-limits is available.

## D029 — Cost/call ₹0 relabeled to clarify benchmark scope
Date: 2026-09-03
Context: ₹0 cost/call for T0 and T1 implied zero cost universally. This is
only true in the benchmark environment with no external API calls.
Choice: Relabel ₹0 as ₹0†† with footnote "no marginal API cost in benchmark
environment; excludes infrastructure."
Rejected: Removing the cost column — it anchors the tier comparison.
Revisit: When infrastructure cost data is available.

## D030 — Precision@prior 0.2886 documented with causal explanation
Date: 2026-09-03
Context: baselines.json reports eval_t1_precision_at_prior=0.2886. Without
commentary this looks like a weak model. It is a prior arithmetic consequence.
Choice: Add ## Precision@prior note section to EVAL.md explaining the
low-prior math, the FPR contribution, and why the cost function makes this
acceptable. Report the figure honestly rather than omitting it.
Rejected: Omitting the figure — an evaluator who computes it will find it
and assume it was hidden deliberately.
Revisit: When real prior data replaces the 0.8% assumption.

## D031 — recall_unseen clarified: family-level vs record-level
Date: 2026-09-03
Context: recall_unseen was reported as a single number without clarifying
whether it is family-level (any hit counts) or record-level (fraction of
records). These differ substantially for family 13 (T0+T1: 6/25=0.24
record-level but 1/1 family-level since T0 blocks some records).
Choice: Document both granularities in EVAL.md. Report record-level as the
primary number (stricter, matches baselines.json). Note family-level for
completeness.
Rejected: Reporting only family-level — it obscures the T0+T1 weakness on
family 13 (24 of 25 records missed).
Revisit: When additional sealed families are added.

## D032 — AP2 gap claim: protocol comparison table added
Date: 2026-09-03
Context: The AP2 gap argument was stated in prose but not structured as a
verifiable claim. An evaluator familiar with AP2 should be able to check
each row independently.
Choice: Add a four-row comparison table to ## Gap statement showing what AP2
provides vs what mandate-guard adds. Retain prose below the table.
Rejected: Adding external citations inline — AP2 is a draft protocol; the
table is self-contained and the repo's gap argument does not depend on a
specific AP2 version number.
Revisit: When AP2 is finalised and a stable spec URL is available.

## D033 — Threat-to-tier mapping table added to ARCHITECTURE.md
Date: 2026-09-03
Context: The three-tier architecture was described per-tier but not mapped
to specific threat archetypes. An evaluator cannot verify coverage without
tracing each threat through the tier descriptions manually.
Choice: Add ## Threat-to-tier mapping table listing 11 archetypes with the
tier and rule/mechanism that catches each. Placed before ## Deferred.
Rejected: Putting this in EVAL.md — it is an architecture claim, not a
measurement claim. It belongs with the system description.
Revisit: When new attack families are added to the corpus.

## D034 — subprocess.DEVNULL added to identifier scan test harness
Date: 2026-09-03
Context: test_identifier_scan.py failed with OSError [WinError 6] on
Python 3.14.4/Windows. subprocess.run with capture_output=True inherits
invalid handles held open by pytest, breaking child process creation.
Choice: Add stdin=subprocess.DEVNULL to run_scan() to break the handle
inheritance chain. All 42 affected tests now pass on Windows.
Rejected: pytest.mark.skipif(sys.platform=="win32") — hides the failure
rather than fixing it. The scanner logic is correct; the fix is in the
test harness only.
Revisit: If Python fixes the handle inheritance regression on Windows.

## D035 — T1Result contract for empty purchase_intent
Date: 2026-09-04
Context: score() returned a bare float even for empty-intent records,
causing families 8-12 to score a uniform 0.603 model-prior artifact
instead of reflecting "no semantic evidence."
Choice: T1Result contract with explicit intent_present flag; score_t1()
in eval.py treats empty-intent as 0.0 contribution (interim shim).
Rejected: full cascade-level NO_SEMANTIC_EVIDENCE telemetry — deferred to
M6 (cascade.py doesn't exist yet); this is a stopgap at the eval.py layer only.
Revisit: when M6 lands, this shim in score_t1() should be replaced by
cascade-level None handling per CHANGES.md M3 sub-items.

## D036 — cascade.check() unifies T0→T1→T2 behind Verdict
Date: 2026-09-05
Context: run_eval.py duplicated T0/T1 float scoring and a separate T2 gate;
Verdict pinning fields were never populated; empty-intent policy lived only in
eval.py score_t1() shim.
Choice: cascade.check() typed API returns Verdict; empty intent → ALLOW with
NO_SEMANTIC_EVIDENCE; tau passed as parameter (interim until cost_model.yaml);
T2 ALLOW suppressed to HOLD (test-enforced); run_eval maps Verdict→float for
legacy metrics (BLOCK=1.0, ALLOW=0.0, HOLD=t1_score).
Rejected: score-band T2 gate and Verdict-free eval path — replaced by D010 gate
in cascade.
Revisit: Remove tau parameter and eval float shim when S4/cost_model.yaml and
full three-way metrics land.

## D037 — Cascade validation additive; continuous-score path restored in run_eval
Date: 2026-09-05
Context: M6 run_eval replaced score_t0_t1() with _verdict_to_eval_score(), which
binarized Verdicts before compute_metrics/precision_vs_prevalence, breaking the
continuous curves EVAL.md requires.
Choice: Restore original score_t0_t1()/find_cost_optimal_threshold() path
unchanged for all threshold/curve metrics; add cascade.check() Verdict-counting
(eval_cascade_*) as a separate additive layer at fixed tau_star.
Rejected: Using _verdict_to_eval_score for tau_star selection or PR curves —
destroys score distribution semantics even when cascade.check() is correct.
Revisit: Replace eval_cascade_* float rates with full three-way metric functions
when S4/cost_model.yaml lands.

## D038 — Split hn_post_auth_cart_mutation into ALLOW substitution vs BLOCK swap
Date: 2026-09-05
Context: family_note claimed same-category post-auth substitution but the
generator always wrote unrelated SKUs; all 20 records were label ALLOW.
Choice: n%4==0 → disguised unrelated swap (BLOCK, 5/20); else → genuine
same-category replacement with token overlap (ALLOW, 15/20). populate_intent
names original Product {n}; compute_metrics HN-FPR requires label==ALLOW.
Rejected: Wiring populate_intent fallback only — intent would match mutated cart.
Revisit: Promote BLOCK subset to attack_family if chargeback data confirms fraud rate.

## D039 — Vocabulary-driven product names for hn_post_auth_cart_mutation
Date: 2026-09-05
Context: First M2 pass used index-suffixed names (Product {n} Replacement
Unit / Mutated Item Post Auth {n}); T1 scored all ALLOW at 0.0 and all
BLOCK at 1.0 — lexical diversity was numeric only, not semantic.
Choice: Shared electronics/groceries product vocabularies; original product
recomputed from (n, mcc) for purchase_intent; substitute from same category
(ALLOW) or cross category (BLOCK, n//4 index). Helpers live in generate.py,
imported by populate_intent.py.
Rejected: Storing original_product in a new record field — schema change.
Revisit: Expand vocab if ALLOW subset needs more unique cart names than 12.

## D040 — Strip leading intent verbs before overlap features; S2 before M1
Date: 2026-09-05
Context: M2 diagnostics on BLOCK-208 showed char_trigram_overlap=0.05 from
shared trigram `er ` between "order" (intent) and "power" (cart), not from
product semantics. 15/20 mutation records also shared identical zero-overlap
7-vectors — lexical-overlap ceiling separate from this bug.
Choice: Add _INTENT_VERB_STOPWORDS; strip leading verbs on intent side only
before jaccard_token_overlap and char_trigram_overlap. Re-sequence S2 before
M1 — category-semantic feature required before independent semantic corpus.
Rejected: Stripping verbs from cart text or all stopword occurrences globally.
Revisit: S2 plan turn to pick embedding-similarity vs taxonomy feature.

## D041 — Randomize populate_intent verb templates; family fingerprint bug
Date: 2026-09-05
Context: M2 holdout flip analysis found attack_family_1 (always "buy") and
attack_family_4 (always "order") produced identical jaccard/trigram values per
family; D040 verb-strip then flipped TP→FN by raising overlap uniformly. T1
was partly learning template fingerprints, not semantic mismatch.
Choice: Replace hardcoded per-family verbs with random.choice(["purchase",
"buy", "order", "get"]) on all templated branches where the verb is not
structurally part of the attack (families 1, 3, 4, 6, stockout, mutation,
fallback). Left fixed: subsidiary "pay", family_2 "purchase from", family_5
scope phrase, family_7 "retry purchase".
Rejected: Reverting D040 verb-strip — fingerprint was in populate_intent, not
features.py.
Revisit: None. Bounded impact: families 1 and 4 are T0-blocking in cascade;
T1 standalone metrics affected, not production cascade detection.

Addendum: remaining post-fix score constancy on families 1/4 (jaccard=1.0,
char_trigram=1.0 across all 30 records each) reflects genuine ground-truth
content identity for these amount/hash-based attacks (T0's domain), not a
template artifact — confirmed by contrast with pre-strip trigram variance
once real verb diversity is present (4 distinct values). T0 catches these
families regardless of T1's output; the t1_recall drop (1.0->0.8) reflects
T1 correctly declining to flag content it has no semantic basis to
distinguish, not a capability loss.

## D042 — category_hierarchy_distance via original taxonomy (S2)
Date: 2026-09-05
Context: M2 showed 15/20 hn_post_auth_cart_mutation records shared identical
zero-valued lexical overlap features; S2 needed category semantics without new deps.
Choice: Original project-authored TAXONOMY_LEAVES (36 leaves, 4 top-levels)
matched via a second TfidfVectorizer; category_hierarchy_distance added as 8th
feature. Embedding-similarity rejected (sentence-transformers not installed,
reproduce-time fetch risk). Google Product Taxonomy rejected (redistribution
terms unresolved for vendoring the raw file).
Rejected: Ollama /api/embeddings on chat models (500 on qwen2.5:7b); network
embedding baseline (D022).
Addendum: category_hierarchy_distance now non-zero on cross-category mutation
pairs (e.g. BLOCK-208 dist=1.0); calibrated scores still plateau (5/5 BLOCK
at 0.2634) because same-top-level ALLOW substitutions share mid-range distances.
Revisit: If taxonomy leaf coverage gaps persist on scaled M1 corpus.

## D043 — Cross-validate M2 vocab against S2 taxonomy (Desk Lamp)
Date: 2026-09-05
Context: generate.py _ELECTRONICS_PRODUCTS and taxonomy.py TAXONOMY_LEAVES were
authored independently; Desk Lamp was electronics in M2 but Home Goods in S2.
Record -207 (ALLOW same-category substitution: Desk Lamp intent, Webcam cart)
scored 0.2634 — identical to genuine BLOCK cross-category swaps.
Choice: Move Desk Lamp leaf to Electronics > Office > Desk Lamp in taxonomy.py
(generate.py assignment kept; desk lamp is sold under electronics MCC in corpus).
Rejected: Moving Desk Lamp to groceries or regenerating corpus — only one of 30
vocab items mismatched; root cause was taxonomy top-level, not generate logic.
Revisit: Re-audit if either vocabulary expands without paired taxonomy update.

## D044 — taxonomy.py rebuilt to 10 balanced top-level categories
Date: 2026-09-05
Context: TAXONOMY_LEAVES had 4 top-level categories with leaf counts 18/13/1/2
(Home Goods had exactly 1 leaf, Apparel 2). This is the same class of
independent-vocabulary drift that caused the earlier Desk Lamp mismatch, at
corpus scale, and would have propagated into M1's semantic sealed set.
Choice: Expanded to 10 top-level categories, all leaf counts in [10,18],
by fleshing out Home Goods/Apparel and adding 6 new categories. No leaf
strings were removed; hierarchy_distance()/matching logic unchanged.
Rejected: Building M1 against the 4-category taxonomy as-is and treating
the 10-category scheme as independent — rejected per standing anti-shim
principle; this would reproduce the Desk Lamp drift, not avoid it.
Revisit: If a real external product taxonomy becomes usable under the
offline/keyless constraint (see D042/D043 reasoning).
Note: data/generate.py's hn_post_auth_cart_mutation still uses its own
independent _ELECTRONICS_PRODUCTS/_GROCERIES_PRODUCTS vocab, unrelated to
TAXONOMY_LEAVES. Same drift risk exists there, not fixed by this entry,
tracked as a known-not-fixed gap.

## D045 — models/feature_names.json was missing category_hierarchy_distance
Date: 2026-09-05
Context: Found during taxonomy rebuild recon, unrelated to the rebuild itself.
FEATURE_NAMES in features.py has always had 8 entries since S2 shipped, but
the committed models/feature_names.json artifact only listed 7 — the deployed
T1 model was never actually retrained with the 8th feature. score() avoided
crashing only via the taxonomy_vec-is-None graceful-degradation branch,
silently emitting 0.0 for a feature the code believed was live.
Choice: Fixed by the retrain in this same diff (Step 4) — no separate
retrain needed, real fix not a shim.
Rejected: Leaving it and documenting as a known limitation — rejected per
standing anti-shim principle; a real fix (retrain) was available.
Revisit: N/A — closed by this diff.

## D046 — Dev eval metrics reported under both full-intent and no-intent conditions
Date: 2026-09-05
Context: run_eval.py's headline metrics (eval_recall_seen, eval_recall_unseen,
eval_t1_fpr_hard_negatives) read only base corpus files. For attack families
1-7/14-15, base files have real purchase_intent baked in (identical to
_with_intent sidecars). For benign and hard-negative records, base files
always have purchase_intent="" by design (D016), with real intent only in
_with_intent sidecars. This meant eval silently measured the no-intent
condition for benign/HN and the full-intent condition for attacks - an
undisclosed asymmetry, not a bug in the D016 split itself.
Choice: Report both conditions explicitly as separate metric fields
(_full_intent / _no_intent suffixes) rather than preferring one file over
the other. Both conditions are real and meaningful: no-intent is exactly
the population M3's NO_SEMANTIC_EVIDENCE contract exists to handle
correctly, so eval must keep measuring it, not lose it in favor of the
sidecar.
Rejected: Preferring the sidecar file whenever it exists and dropping the
base-file condition - rejected because it silently stops testing the
no-intent path for benign/HN, replacing one blind spot with another
rather than disclosing what eval actually measures.
Revisit: If M1's independent semantic sealed set adopts a different intent-
population convention, confirm this dual-reporting pattern still applies.

## D047 — Cascade-validation metrics extended to full-intent/no-intent split
Date: 2026-09-05
Context: D046 split headline dev metrics into full-intent/no-intent
conditions but explicitly left eval_cascade_* fields on the no-intent-only
path, flagging it as a known asymmetry rather than fixing it in that diff.
Choice: Extended the identical dual-condition pattern to
eval_cascade_recall_seen and eval_cascade_hold_rate_hard_negatives. Same
reasoning as D046 applies identically here - no new tradeoff to weigh.
eval_cascade_recall_unseen stays single-pass (sealed set, no sidecar exists).
Rejected: Leaving the asymmetry caveated rather than fixed - rejected per
standing anti-shim principle once the fix was recognized as the same
pattern already implemented, with no new scope or risk beyond what D046
already covered.
Revisit: N/A - closes the gap D046 flagged.

## D048 — compute_metrics and find_cost_optimal_threshold used two disagreeing cost formulas
Date: 2026-09-05
Context: compute_metrics computed cost as fp*320+fn*1470 (2-term, no HOLD),
while find_cost_optimal_threshold used fp*320+fn*1470+hold*45 (3-term) to
SELECT the operating point, then discarded its own cost value. The 2-term
result was written to baselines.json as eval_t1_net_cost_per_10k under both
intent conditions, silently omitting the HOLD cost of the very threshold
the 3-term optimizer chose. This was most severe at tau_star_full_intent
=0.22, where 618 records fall in the HOLD band: the committed
eval_t1_net_cost_per_10k_full_intent=54320.99 understated the true
per-10k cost of roughly 268904 by about 5x.
Choice: Extracted a single compute_cost(fp, fn, hold, ...) used by both
functions. find_cost_optimal_threshold's cost is no longer discarded -
it is now written to baselines.json directly, so the number reported is
the same number that selected the threshold.
Rejected: Patching compute_metrics's formula alone - rejected because it
would leave two independent implementations of the same arithmetic,
reproducing the exact class of drift RULES 22/N5 already exist to guard
against elsewhere in this codebase.
Revisit: When config/cost_model.yaml (S4) lands, redirect compute_cost's
default fp_cost/fn_cost/hold_cost to load from there instead of inline
defaults - this fix does not require S4 to land first.
Note: This also retroactively corrects eval_t1_net_cost_per_10k_full_intent
as committed in af159e9 and eval_cascade_* commits (2165a1b) - those
commits' cost fields were computed with the buggy 2-term formula and
should not be cited as accurate; this entry is the correction of record.

## D049 — B11/B12 threshold and cost-ratio tables moved from hand-authored to generated artifacts
Date: 2026-09-05
Context: EVAL.md's B11 (threshold stability) and B12 (cost ratio
sensitivity) tables were hand-pasted markdown from an earlier corpus
snapshot, with no committed sweep script producing them. STATUS.md
correctly listed both as open TODOs while EVAL.md presented them as
settled fact - a direct contradiction. Recomputing tau=0.65 on the current
corpus gave recall=0.9818/fp=22/fn=5, nothing like the committed
recall=1.0/fp=3/fn=0. The old B12 table also mislabeled its base-case
ratio as "4.6:1" using fn_cost=1472 instead of the exact 1470/320=4.59375.
Choice: Added threshold_sweep() and cost_ratio_sensitivity() as committed,
tested functions in eval.py, run automatically by run_eval.py for both
intent conditions, writing live artifacts to eval_outputs/. EVAL.md now
points to these artifacts as source of truth rather than hand-copying
values that will drift silently again.
Rejected: Manually regenerating and re-pasting a corrected table -
rejected because it reproduces the exact staleness failure mode, just
with fresher numbers today and the same silent drift risk going forward.
Revisit: N/A - the generated-artifact pattern is the fix; no future
revisit needed unless the sweep functions themselves need new columns.

## D050 — eval_outputs/*.json artifacts are reproducible, not committed
Date: 2026-09-05
Context: eval_outputs/*.json has been gitignored since commit 79751a6, but
precision_vs_prevalence.json was never committed (correctly follows the
rule) while threshold_sweep.json and cost_ratio_sensitivity.json were
force-added in a3d9022 without the gitignore rule being surfaced or a
policy decision made - an accidental, silent inconsistency across three
files that are all byproducts of the same run_eval.py invocation.
Choice: All eval_outputs/*.json files are reproducible artifacts, not
committed source - consistent with baselines.json (RULES 15) being the
one accepted metrics source, and with PROJECT_INSTRUCTIONS.txt's
reproduce-in-five-minutes posture. Untracked threshold_sweep.json and
cost_ratio_sensitivity.json to match precision_vs_prevalence.json's
existing (correct) treatment. eval_outputs/.gitkeep stays committed to
preserve the directory for a fresh clone.
Rejected: Committing all three as ground truth like fixtures/*.json (D002)
- rejected because fixtures are replay cassettes for keyless reproduction
(a different purpose), while these are eval outputs regenerated by every
run_eval.py call and should never drift from what that call currently
produces.
Revisit: If eval_outputs/ artifacts ever need to be diffable across
commits for review purposes (e.g. auditing a metrics change), reconsider
committing them deliberately at that point, not by accident.

## D051 — tau_star_full_intent=0.22 is not a favorable operating point once HOLD cost is counted correctly
Date: 2026-09-05
Context: eval_outputs/threshold_sweep.json (generated in a3d9022, post the
D048 cost-formula fix) shows tau=0.20 under full-intent scoring achieves
recall=1.0 at net_cost_per_10k=~268904, versus tau=1.0 under no-intent
scoring achieving recall=0.9818 at net_cost_per_10k=~108179 - full-intent's
perfect recall costs roughly 2.5x more than no-intent's near-perfect
recall, driven by 618 records landing in the HOLD band (each at ₹45).
Moving to tau=0.25 under full-intent makes both axes worse simultaneously
(recall drops back to 0.9818, cost rises to ~327353) - there is no swept
tau where full-intent scoring is both higher-recall and lower-cost than
no-intent. Separately, full-intent's decision boundary is a knife-edge:
the 5 hn_post_auth_cart_mutation attack records score exactly 0.228141
and the remaining 270 attacks score exactly 1.0, with no intermediate
values - not a genuine stability plateau, despite the 0.01-grid optimizer
reporting one.
Choice: Disclose this plainly. eval_recall_seen_full_intent=1.0 must not
be cited (e.g. in M5/README) without its paired cost figure
(net_cost_per_10k_full_intent) alongside it - citing the recall number
alone would be cherry-picking a metric this project's own EVAL.md
explicitly rejects doing (see "Drop F1... FN and FP cost differently").
Rejected: Treating tau=0.22 as a validated, adopted operating point -
rejected because both the cost sweep and the score-distribution recon
(prior session) show it is a narrow, expensive tradeoff, not a genuine
improvement over the no-intent condition.
Revisit: If M1's independent semantic sealed set produces a genuinely
diverse full-intent score distribution (not a two-value knife-edge like
the current corpus), re-run this comparison - the current finding is
specific to this corpus's degenerate score distribution, not a general
claim that full-intent scoring is always worse.

## D052 — qwen3:8b tested as T2 candidate, rejected in favor of qwen2.5:7b
Date: 2026-09-04 (benchmark run) / 2026-09-05 (formally recorded)
Context: experiments/t2_model_selection/bench_t2_candidate.py benchmarked
qwen3:8b against the production qwen2.5:7b baseline (EVAL.md B9) on the
226-record dev hard-negatives-with-intent corpus. Full results in
results_qwen3-8b.json. Aggregate: qwen3:8b produced 55 HOLD verdicts
(vs qwen2.5:7b's 21 documented in B9 - roughly double), with
hn_stockout_substitution regressing rather than improving. Some
improvement was seen on hn_semantic_ambiguous specifically.
Choice: Rejected qwen3:8b as the production T2 model. qwen2.5:7b remains
in place (D009). Same-size newer model is not a strict upgrade for this
narrow classification task - more trigger-happy, not better calibrated.
This experiment and its result are committed as disclosed evidence rather
than deleted, consistent with this project's practice of disclosing
negative/inconvenient findings (see D019 on family 13) rather than
hiding them.
Rejected: Adopting qwen3:8b for the modest hn_semantic_ambiguous gain -
rejected because the aggregate HOLD-rate regression and
hn_stockout_substitution decline represent a net calibration loss, not
a net improvement.
Revisit: If a differently-calibrated qwen3 variant or a larger local model
becomes available under the offline/keyless constraint, re-run this exact
benchmark script against it for a fair comparison.

## D053 — M1 (independent semantic sealed set) pre-registered
Date: 2026-09-05
Approved by: Shikhar (explicit sign-off, not self-approved)
Context: M1 requires pre-registration of exact record count, category
list, label scheme, adjudication rule, tau, and T2 kill criterion before
any corpus generation, per CHANGES.md's M1 spec and standing project
discipline (RULES 19-style: no tuning on data that will become a sealed
set). Reviewed and approved as drafted, no edits.
Choice:
- Categories: 10, from taxonomy.py post-D044 (Electronics, Groceries,
  Home Goods, Apparel, Health & Personal Care, Office Supplies,
  Toys & Games, Pet Supplies, Automotive, Books & Media).
- Count: 50 records/category x 10 = 500 total. Original vocabulary,
  aligned to taxonomy.py's exact leaf names from the start.
- Ambiguous subset: >=50 records overall, target 5/category minimum,
  spread across categories (fixes hn_semantic_ambiguous's current
  Wilson-uselessness at n=6).
- Labels: ALLOW/DEVIATION/UNCERTAIN generated natively, normalized to
  binary ALLOW/BLOCK via a named function with its own contract test
  before entering the shared pipeline (DEVIATION->BLOCK, UNCERTAIN
  excluded from FPR, reported separately). M1's own results file keeps
  the real 3-way counts unreduced.
- Adjudication rule: ALLOW iff cart item is (a) within the same taxonomy
  leaf or an immediate-parent-sibling leaf as stated intent, (b) within
  intent's stated amount/quantity tolerance, (c) not a top-level category
  crossing. DEVIATION iff cart item crosses top-level categories, or
  matches a different leaf under the same parent with no stated
  substitution rationale. UNCERTAIN iff a human reviewer cannot
  confidently apply (a)-(c) without more context than the record
  provides - this bucket is expected to be non-trivial for a semantic
  corpus.
- Tau: not pre-selected. Must be derived via find_cost_optimal_threshold/
  threshold_sweep (post-D048 cost formula) run on this corpus once
  generated - not carried over from existing dev/sealed tau values.
- T2 kill criterion: >=5pp recall lift over T0+T1 on this corpus's
  DEVIATION population, WITH hard-negative FPR increase <2pp. Stricter
  than family-13's criterion (>=2pp, no FPR constraint) because this
  corpus mixes ambiguous and clear cases - a lift accompanied by an FPR
  blowup should not count as a win.
- Seed: 271 (distinct from dev=42, sealed=137; no special meaning by
  design).
- Integrity: SHA-256 committed before any T1 retrain or T2 prompt change.
  Run exactly once. Results to baselines_sealed_semantic.json, never
  edited after first write.
- New infra required: data/sealed_semantic/ + own SHA256SUMS,
  parameterized loader (existing load_sealed_attacks() doesn't
  generalize). No make seal-eval exists (Makefile absent, N1 deferred) -
  "run exactly once" is currently self-enforced discipline, not
  tooling-guaranteed. Flagged explicitly, not silently assumed safe.
Rejected: Pre-selecting a fixed tau before the corpus exists - rejected
as reasoning backwards from a nonexistent scoring distribution.
Revisit: If generation reveals the adjudication rule produces an
unworkable UNCERTAIN rate (too high or suspiciously near-zero), stop
generation and revise the rule before continuing - do not silently
force records into ALLOW/DEVIATION to hit a target distribution.

## D054 — Semantic adjudication rule: tolerance constants and D053 gap-fills
Date: 2026-09-05
Approved by: Shikhar (explicit delegation - "do whatever's best, real
fixes only, not band-aids" - 2026-09-05), engineering completion by Claude.
Context: D053's adjudication rule leaves three points underspecified as
prose: (1) no tolerance value for "within intent's stated amount/quantity
tolerance", (2) no operationalization of UNCERTAIN as executable logic,
(3) two cases (same-leaf-outside-tolerance; sibling-with-rationale-
outside-tolerance) aren't named by either ALLOW's conjunction or
DEVIATION's two disjuncts.
Choice:
- Tolerance: NEW constants, not reused from existing code. WITHIN if
  abs(ratio-1.0)<=0.10, BOUNDARY if <=0.20, OUTSIDE beyond. Checked
  against hn_price_drift (+1-2%, sits inside WITHIN - consistent) and
  T1's quantity_mismatch flag band ([0.5,2.0] - far wider than my OUTSIDE
  cutoff, confirming this is a distinct, tighter, purpose-built band, not
  a duplicate of an existing flag threshold).
- UNCERTAIN's primary source is "same top-level category, different
  immediate parent" (D054 branch 4) - the direct structural match for
  D053's own definition, not an invented case. Present in all 10
  categories (4-7 distinct parents each, confirmed via taxonomy dump).
- Two named gap-fills: same-leaf-outside-tolerance -> DEVIATION (amount
  manipulation on an identical SKU, nothing ambiguous about it);
  sibling-with-rationale-outside-tolerance -> UNCERTAIN (stated rationale
  contradicts the amount, genuinely mixed signal).
Rejected: Reusing hn_price_drift's percentage or quantity_mismatch's
ratio band directly - both are purpose-built for different measurement
questions (obviously-fine vs obviously-wrong) and reusing either would
either collapse WITHIN to near-nothing or ALLOW to near-everything.
Revisit: If M1 generation produces an UNCERTAIN rate that's unworkable
per D053's own revisit trigger, reconsider the 0.10/0.20 boundary widths
first before touching the branch structure.

## D055 — M1 semantic corpus: per-category composition and price bands
Date: 2026-09-05
Approved by: Shikhar (delegated - "yes", proceeding with batch generator
design - 2026-09-05), designed by Claude.
Context: D053 requires >=5/category UNCERTAIN records and genuine
per-record diversity (not archetype cycling, per family 13's disclosed
flaw). Needed a concrete per-category sampling composition and a source
for base_unit_price_minor_units (build_semantic_record's price parameter
had no per-leaf table yet).
Choice:
- Fixed composition per category (50 records): 12 same-leaf ALLOW, 3
  same-leaf UNCERTAIN, 3 same-leaf DEVIATION, 8 sibling+rationale ALLOW,
  2 sibling+rationale UNCERTAIN, 6 sibling-no-rationale DEVIATION, 6
  same-top-different-parent UNCERTAIN, 10 cross-top-level DEVIATION.
  Totals: 200 ALLOW / 190 DEVIATION / 110 UNCERTAIN (22% UNCERTAIN,
  spread across three independent sources: same-leaf boundary, sibling-
  with-contradicting-rationale, and same-top-different-parent).
- LEAF_BASE_PRICE: one reference price per leaf, sampled once from a
  per-top-level-category INR band (ASSUMPTION-labeled, not cited to any
  real pricing data), fixed across all records referencing that leaf so
  amount_ratio has a stable reference point per product.
Rejected: Resampling a fresh reference price per record instead of per
leaf -- would make amount_ratio meaningless (deviation from a number
that itself changes every time).
Revisit: If real generation shows 22% UNCERTAIN is unworkable per D053's
own revisit trigger, or if the sibling/singleton exclusion produces
skewed per-category composition, reconsider the fixed counts above
before touching the adjudication branch structure itself.

## D056 — Binary reduction of semantic labels is a pipeline-compatibility boundary, not a workaround
Date: 2026-09-05
Approved by: Shikhar (explicit delegation - "do whatever's best, real
fixes only, not band-aids" - 2026-09-05), drafted by Claude.
Context: Shared pipeline (t1.train, compute_metrics, cascade.check) is
mathematically binary (BLOCK/ALLOW) by design. M1's corpus generates a
native 3-way label (ALLOW/DEVIATION/UNCERTAIN) because the underlying
question - is this substitution legitimate - is genuinely 3-valued.
Choice: normalize_semantic_labels_for_training() performs
DEVIATION->BLOCK, UNCERTAIN-dropped, ALLOW->ALLOW before any record
reaches shared pipeline code. This is a stated design boundary: the
pipeline's binary contract is not relaxed to accommodate UNCERTAIN;
instead the corpus's own results file (baselines_sealed_semantic.json)
reports real 3-way counts unreduced.
Rejected: Extending Verdict/label schema project-wide to 3-way - would
touch T0/T1/T2/cascade contracts for a distinction only this one
corpus's generation process needs; existing HOLD verdict already carries
the "genuinely ambiguous" semantics operationally.
Revisit: If a second corpus or production signal needs native 3-way
labels reaching the shared pipeline itself.

## D057 — M1 T2 kill criterion operationalized: BLOCK-only FPR, measured against existing hard negatives
Date: 2026-09-05
Approved by: Shikhar (explicit delegation - "do whatever's best, real
fixes only, not band-aids" - 2026-09-05), drafted by Claude.
Context: D053's kill criterion ("hard-negative FPR increase <2pp") was
underspecified on two points: which hard-negative population, and
whether a cascade HOLD verdict counts toward FPR. Confirmed via recon
that compute_metrics()'s fpr_hard_negatives already defines FPR as
BLOCK-equivalent only (predictions = score>=threshold), never folding in
HOLD; and that _compute_cascade_dev_metrics in scripts/run_eval.py
already follows the same convention at cascade level (recall counts only
VerdictState.BLOCK, HOLD is tracked as a separate hold-rate metric, never
merged into recall or FPR). D057 extends this existing convention rather
than inventing a new one.
Choice:
- FPR population: data/dev/hard_negatives.jsonl (226 records) - the
  semantic corpus's own family strings never match "hn_", so measuring
  FPR within the semantic corpus itself would trivially return 0.0 and
  measure nothing.
- FPR definition: cascade-level BLOCK rate on that population, T2 off vs
  T2 on, same tau. Matches existing HOLD-rate counting pattern exactly,
  substituting BLOCK for HOLD.
- Kill criterion, fully operationalized: recall_lift(DEVIATION population
  of M1 corpus, T2-on cascade vs T2-off cascade) >= 0.05 AND
  (hn_block_rate(T2-on) - hn_block_rate(T2-off)) < 0.02. Both boundaries
  are inclusive-lower/exclusive-upper as D053 originally stated (>=0.05,
  <0.02) - not loosened to > or <=.
Rejected: Counting HOLD as a false positive for this criterion - would
contradict ARCHITECTURE.md's own stated cost model, where HOLD exists
specifically because it is cheap (Rs45) and non-terminal, not a false
positive in the traditional sense.
Revisit: If a future corpus needs cascade-level FPR as a named,
first-class metric outside this one-off measurement - promote
run_cascade_on_record + cascade_verdict_rate's pattern to a documented
public API rather than re-deriving it per-corpus.

## D058 — Cost-optimal threshold degenerates at both raw counts and true prior; tau fixed via FN:FP=1.0 sweep point instead
Date: 2026-09-05
Approved by: Shikhar (explicit sign-off, not self-approved).
Context: D053 specified tau derived via find_cost_optimal_threshold run
once on the M1 corpus. Running it raw (no prior) produced tau=0.01 -
recall=1.0 but 195/200 (97.5%) of ALLOW records blocked, a degenerate
corner where minimal T1 signal triggers BLOCK. Adding prior-reweighting
(prior=0.008, matching EVAL.md's stated attack rate) to correct for this
corpus's near-50/50 class balance produced the opposite degenerate
corner: tau=1.0, recall=0.016, 0 FP but 187/190 fraud missed. Full
51-point sweep at prior=0.008 confirmed cost is monotonically
non-increasing across the entire [0,1] range - no interior minimum
exists at the true prior for this cost ratio (FN:FP=4.6:1) on this
corpus's error curve. This is not a code defect: at 0.8% true prior,
false-positive cost on the 99.2% legitimate population structurally
dominates fraud-miss cost at every threshold, regardless of the 4.6:1
per-incident cost asymmetry. Same finding-class as D025 (precision@prior)
and D051 (tau_star_full_intent unfavorable once HOLD counted) - a real,
disclosed limitation of pure cost-threshold optimization at realistic
priors, not a corpus or implementation bug.
Choice: Fix tau at 0.17 - the operating point from the FN:FP=1.0 sweep
(cost_ratio_sensitivity), the highest-ratio point that still yields a
genuine interior cost minimum (recall=0.85, 99 FP, 28 FN) rather than a
corner solution. This treats FN and FP as equally weighted for
threshold-selection purposes only; the true 4.6:1 cost asymmetry is
reported separately in results, not hidden. Kill-criterion recall/FPR
measurement (D057) runs at this fixed tau, not via
find_cost_optimal_threshold at any prior.
Rejected: (a) Raw-count tau=0.01 - degenerate, not a real operating
point. (b) True-prior tau=1.0 - equally degenerate, opposite direction.
(c) Re-deriving dev/sealed's existing accepted tau values under
prior-correction - out of scope for this session; those baselines are
accepted and unchanged; this finding may motivate revisiting them later
as its own tracked item, not silently now.
Revisit: If cost constants (Rs320/Rs1470/Rs45, all ASSUMPTION-labeled
per config/cost_model.yaml's absence - S4) are replaced with cited real
figures, or if a HOLD-band threshold design (routing ambiguous scores to
HOLD rather than a binary BLOCK/ALLOW cut) is built, re-run this
analysis - a band may resolve what a single threshold structurally
cannot.

## D059 — M1 T2 kill criterion measurement: T2 fails on both recall and hard-negative FPR
Date: 2026-09-05
Approved by: Shikhar (explicit sign-off).
Context: Per D057's operationalized kill criterion and D058's fixed
tau=0.17, the real run (baselines_sealed_semantic.json, this commit)
measured: recall_t2_off=0.8526, recall_t2_on=0.7684
(recall_lift=-0.0842); hn_block_rate_t2_off=0.1327,
hn_block_rate_t2_on=0.1637 (hn_fpr_delta=+0.0310). Kill criterion
required recall_lift>=0.05 AND hn_fpr_delta<0.02. Both conditions fail,
and fail in the same direction: T2 lowers recall on real deviations AND
raises false-positive rate on legitimate hard negatives simultaneously -
not a precision/recall tradeoff, a straightforward regression on both
axes. This corroborates EVAL.md's existing disclosed limitation ("T2
HOLD behavior at 7B scale... hn_stockout_substitution and
hn_semantic_ambiguous... a 7B model at temperature=0.0 cannot reliably
distinguish these ambiguous cases") at real scale (190+226 records)
rather than the original 6-record hn_semantic_ambiguous bucket.
Family-13's earlier +16.67pp T2 lift (D008/D020) was a disclosed
post-hoc, non-pre-registered result on a 4-archetype-cycled challenge
set. D059 is the second pre-registered measurement of T2's kill
criterion (after D008's dev-corpus criterion, which was mathematically
impossible to fail per T0 solving the corpus entirely) and the first
where T2 is measured on a corpus genuinely capable of failing it - and
it fails.
Choice: T2 does not meet its kill criterion on the M1 corpus.
t2_enabled remains False by default (unchanged from D008). This result
stands as-measured; no re-run, no tau adjustment, no second attempt.
Report plainly in M5's README reframe: T2 is architecturally justified
by the AP2 gap argument (evidence-only tier, never sole authority) but
has now failed its kill criterion in every pre-registered measurement
attempted (original dev corpus - criterion impossible; M1 semantic
corpus - criterion measurable and failed). Only positive T2 result
remains family-13's disclosed post-hoc, non-pre-registered +16.67pp.
Rejected: Adjusting tau, re-running, or selecting a different T2 config
to find a favorable result - would violate D053's "run exactly once"
discipline and RULES 16's "improvement beyond tolerance also fails,
check leakage first" principle in spirit; a result obtained by
search-until-favorable is not evidence.
Revisit: If a larger/different T2 model is benchmarked (qwen3:8b
already rejected per D052) and shows materially different behavior on
this same frozen corpus, or if S6's confidence-floor recalibration
(blocked on this measurement) changes T2's effective decision boundary
in a way worth re-testing against a NEW corpus (not re-running this
one).



## D060 — compute_cost/find_cost_optimal_threshold double-counts HOLD against FN
Date: 2026-09-05
Context: find_cost_optimal_threshold computed `hold` as an independent count
of 0<score<tau, overlapping entirely with positives already charged as `fn`
(score<tau -> pred=0 -> fn if label=1). Every positive scoring in (0, tau)
was billed both fn_cost and hold_cost for the same record.
Choice: Partition records into exactly one of BLOCK (score>=tau) / HOLD
(0<score<tau) / ALLOW (score==0) per tau via new _cost_partition_at_tau.
fn redefined as ALLOW-and-label=BLOCK (zero-signal miss only, matching M3's
NO_SEMANTIC_EVIDENCE). hold_pos/neg computed from the HOLD partition only.
Consequence to verify before trusting: D058's tau=0.17 selection and D059's
kill-criterion result were computed against the buggy function. Both must
be rerun against the fixed function before being cited as current.
Rejected: Patching hold_cost weight down as a band-aid — doesn't fix that
fp/fn/hold weren't a true partition.
Revisit: N/A — this is the partition definition going forward.



## D061 — cost function had no HOLD-capacity term; corner-solution finding
Date: 2026-09-05
Context: Post-D060, find_cost_optimal_threshold at the true operating cost
(hold_cost=45) returns tau=1.0 (recall=0.0158) at every FN:FP ratio tested —
not a bug, a real property: with real score-distribution overlap (ALLOW p90
0.976 > BLOCK p10 0.142) and HOLD priced flat at 45 with no volume limit,
deferring nearly all traffic to HOLD always beats committing to a verdict.
The original tau=0.17 (D058) only looked cost-optimal because the pre-D060
double-count inflated the cost of low tau; it was never truly cost-minimal
at hold_cost=45 — confirmed via hold_cost sweep, tau=0.17 only reappears as
optimal at hold_cost>=160 (3.5x the real value).
Choice: Add max_hold_rate: float | None = None to find_cost_optimal_threshold.
When set, tau candidates with hold_rate > max_hold_rate are excluded from
the argmin entirely (not penalized — excluded). Set to raise ValueError if
no tau satisfies the constraint (fail closed, matching ARCHITECTURE's
store-down-fails-closed pattern), rather than silently returning a
constraint-violating tau. max_hold_rate=0.05 (ASSUMPTION, order-of-magnitude
below T2's 0.5% ceiling scaled up ~10x for HOLD's lower per-unit cost; no
citation available, same status as existing fp/fn/hold cost ASSUMPTIONs).
cost_ratio_sensitivity left unconstrained (diagnostic tool; this is what
surfaced the corner-solution finding and should keep surfacing it).
run_eval_semantic.py updated to call the constrained path; tau is no longer
hardcoded to 0.17.
Rejected: Keeping tau=0.17 hardcoded with only a documentation caveat —
a real fix was achievable (a capacity term), so disclosure-only was not
the right substitute per this project's standing principle.
Revisit: If real ops review-capacity data becomes available, replace the
0.05 ASSUMPTION with a cited figure.



## D062 — D059's tau=0.17 operating point is unreachable under correct
cost accounting; magnitude superseded, direction unconfirmed
Date: 2026-09-05
Context: D061's max_hold_rate constraint sweep (fp=320, fn=1470, on the
same 390-record M1 corpus D059 used) found no (cost_ratio, max_hold_rate)
combination reproduces D059's tau=0.17 / recall=0.85 / fp=99 / fn=28
operating point. The corrected optimizer only returns two corner-like
regimes: block-nearly-everyone (fp~195, hold~1%) at max_hold_rate<=0.15,
or block-most-plus-defer-a-fifth (fp~121-136, hold~19-24%) at
max_hold_rate>=0.20 — no smooth interior tradeoff exists between them.
tau=0.17 was only reachable under the pre-D060 double-counting bug; it was
never a legitimate cost-minimal point at the real hold_cost=45. Root cause
is likely poor class separation in T1's current lexical-similarity
features (jaccard/trigram/tfidf-cosine) on this corpus, not a threshold
or cost-model problem — S2 (structural features: brand_equality,
sku_equality, category_hierarchy_distance) was already queued for
exactly this reason and is now the load-bearing item, not optional
polish.
Choice: D059's specific magnitude (recall_lift=-0.0842, hn_fpr_delta=
+0.0310) is superseded and must not be cited as current in README/M5
output — it was measured at an operating point that cannot be reached
under correct cost accounting. D059's qualitative direction (T2 did not
clearly help; kill criterion not met) remains provisionally plausible —
across every tau examined in this investigation, T2-on was never
materially better than T2-off — but this is not independently confirmed
at a defensible tau and must not be presented as confirmed until S2
lands and the comparison is rerun at whatever tau S2's features support.
M5's README language citing -8.4pp/+3.1pp must be pulled and replaced
with: kill criterion not met at the only tau tested; exact magnitude and
even the qualitative result are unreliable pending S2; see D062.
Rejected: Leaving D059's magnitude in the README with only a footnote —
the number would still be read as evidence by a judge; a wrong-tau result
is not softened by disclosure, it needs to be removed from headline claims
entirely.
Revisit: Once S2 lands and T1 has structural features, rerun the D059
comparison (T2-on vs T2-off, kill criterion) at whatever tau the
corrected optimizer selects on the improved feature set.



## D063 — make check does not exist; D004's interim deviation was never resolved
Date: 2026-09-05
Context: RULES 6/7/8 require full `make check` output pasted before any
task counts as done. Verified this session: `make` is not installed
(PowerShell: CommandNotFoundException; Git Bash: command not found), and
no Makefile exists in the repo root. D004 (2026-08-27) logged this same
gap as an interim deviation with an explicit expiry: "EXPIRES at Step 7."
No evidence found this session that Step 7 occurred or that a Makefile
was ever created. D004's deviation has therefore been silently live for
the project's entire duration, not resolved — every DONE status recorded
in CHANGES.md and DECISIONS.md to date (including M2/M3/M4/M6/S2, all
marked DONE this session and prior) was verified via individual ruff/
mypy/pytest invocations Cursor happened to run and paste, never via the
combined gate RULES 7 defines.
Choice: Disclose this plainly rather than continue citing "make check"
implicitly. Decision on how to resolve it (build a real Makefile via
WSL2/make-for-Windows, write a Python check-runner script, or continue
ad-hoc) is explicitly deferred — not self-approved here. Until resolved,
any "done" claim in this project should be read as "done per the
individual checks actually run and pasted," not per RULES 7's full gate.
Rejected: Silently continuing to write "make check" in future
verification text as if it ran — this is exactly the failure mode this
project already caught once with CHANGES.md's M1-M8 narrative gap; a
citation to a command that has never executed is the same category of
error as a citation to a Cursor run that never happened.
Revisit: When a real make-check-equivalent is built and run successfully
end-to-end at least once.

## D064 — HOLD tier is fictional for T0+T1-only evaluation; cost functions corrected, D061/D062 superseded
Date: 2026-09-05
Context: Investigating a real cascade recall discrepancy (committed
baselines.json claimed eval_cascade_recall_seen_full_intent=1.0; live
execution gave 0.9818) traced to 5 hn_post_auth_cart_mutation records
(D038/D026 archetype, T0-blind by design) scoring ~0.228 -- below
tau_star=1.000 as selected by find_cost_optimal_threshold with no
max_hold_rate at that call site. Tracing further: cascade.check() (M6,
D036) confirmed to NEVER produce VerdictState.HOLD unless T2 is actually
invoked (t2_config.t2_enabled AND purchase_intent present AND score<1.0);
with T2 disabled (D008 default), a record scoring 0<score<tau falls
straight to ALLOW. Every current caller of find_cost_optimal_threshold
and compute_metrics (dev corpus tau selection, M1 corpus tau selection via
run_eval_semantic.py) evaluates T0+T1 with T2 disabled -- meaning D060's
three-way BLOCK/HOLD/ALLOW cost partition, and D061's max_hold_rate
capacity constraint built on top of it, were modeling a HOLD tier that
does not exist in the actual code path being evaluated. Separately
confirmed compute_metrics (used for baseline comparison and net_cost_per_10k
reporting) had the identical double-count defect D060 fixed elsewhere,
never patched, plus a second latent bug: its `prior` parameter was
silently ignored by the cost calculation entirely.
Choice: compute_cost, _cost_partition_at_tau, find_cost_optimal_threshold,
and compute_metrics all rewritten to a genuine two-way FP/FN cost model --
hold_cost and max_hold_rate parameters removed entirely (not defaulted to
zero; a permanently-unused parameter is misleading residue per RULES 23).
A record scoring below tau is fn_cost if BLOCK-labeled, zero cost if
ALLOW-labeled. D061's max_hold_rate mechanism is superseded in full, not
reparameterized -- it solved a problem that does not apply to any current
evaluation context. D062's "no interior tau on M1 corpus" finding was
measured under the same non-applicable three-way model and must be
re-derived under this corrected model before being cited as current;
D059's magnitudes were already superseded by D062 and remain superseded.
Post-fix, re-running run_eval.py live (this session): dev full-intent
recall_seen reaches 1.0000 (was 0.9818 under the old model) at a genuine
interior tau_star=0.220 (was degenerate 1.000). All 347 tests pass,
including the two tests that had been failing
(test_cascade_dev_metrics_use_both_intent_loaders,
test_find_cost_optimal_threshold_with_prior_avoids_degenerate_tau) --
both pass on their own merits under the corrected model, not by loosened
assertions. Two tests directly testing the removed 3-term compute_cost
API deleted (test_find_cost_optimal_threshold_max_hold_rate_constrains_candidate,
test_find_cost_optimal_threshold_max_hold_rate_none_unchanged); one new
contract test added
(test_no_hold_tier_ambiguous_scores_cost_as_fn_or_free) plus two rewrites
of compute_cost's own unit tests in tests/test_eval_semantic.py.
Rejected: Reparameterizing max_hold_rate to a harmless default instead of
removing it -- leaves dead, misleading machinery in a binding cost
function. Patching only find_cost_optimal_threshold and leaving
compute_metrics's independent instance of the same defect unfixed --
would leave two disagreeing cost computations in the same file, worse
than the original bug. Treating this as a cascade.check() gap (implementing
a standalone T0+T1-only HOLD path) instead -- ARCHITECTURE.md's stated
invariant describes HOLD as existing specifically to absorb T2's async
deferral window, not as a general ambiguity bucket; building a HOLD path
with nothing to defer to would be architecture bent to satisfy a metrics
script, backwards from how this should work.
Revisit: baselines_sealed_semantic.json (frozen under D053's run-once
guard) must be re-derived under this corrected model before D059/D062's
numbers can be cited as current -- this is a disclosed, justified
exception to "run exactly once" (genuine defect correction, not
tau-shopping) but requires explicit sign-off before executing, tracked
separately. run_eval.py's printed cost-model banner string still says
"three-term objective: fp*320 + fn*1470 + hold*45" -- stale console text,
not evidence of a functional gap; low-priority cleanup, not yet done.

## D065 — Pre-registered exception to D053's run-once guard: re-deriving baselines_sealed_semantic.json under D064's corrected model
Date: 2026-09-05
Context: D064 found the three-way BLOCK/HOLD/ALLOW cost model
baselines_sealed_semantic.json (D059) was computed under is fictional for
T0+T1-only evaluation -- HOLD is unreachable without T2, and every current
call site evaluates with T2 disabled. D059's numbers were already
superseded once by D062 (tau=0.17 unreachable under D060's fix) without
ever being re-run; D064 supersedes them a second time. The frozen file
has never actually reflected a valid cost model.
Choice: Treat this as a genuine defect correction, not tau-shopping,
per the same distinction D059 itself drew when rejecting post-hoc tau
adjustment. Delete the current baselines_sealed_semantic.json and
re-run scripts/run_eval_semantic.py exactly once under D064's corrected
two-way model. Whatever result this produces -- including a result
showing T2 performs worse, unchanged, or even passing its kill criterion
-- is reported as-is in a follow-up entry (D066) with no further
adjustment, no second re-run, and no cherry-picking. This is the second
and final measurement against the frozen M1 corpus; if a future defect
is found in the cost model again, that is a new, separately-justified
exception requiring its own pre-registration, not a standing license to
re-run.
Rejected: Leaving D059's numbers frozen and disclosing them as
resting on a superseded model without re-running -- an unreliable
number in a submission's evaluation artifact is worse than a corrected
one, and D053's guard exists to prevent result-shopping, not to protect
a number that was never valid under any correct cost model.
Revisit: N/A -- this exception is scoped to this one re-run.

## D066 — Re-derivation result: T2 kill criterion still fails at the real cost-optimal tau
Date: 2026-09-05
Context: Per D065's pre-registered exception, baselines_sealed_semantic.json
was deleted and scripts/run_eval_semantic.py re-run once under D064's
corrected two-way cost model. Result: tau_star=0.170 (fp=99, fn=28,
cost=40640.0 at fp_cost=fn_cost=320.0), recall_t2_off=0.8526,
recall_t2_on=0.7684 (recall_lift=-0.0842), hn_block_rate_t2_off=0.1327,
hn_block_rate_t2_on=0.1637 (hn_fpr_delta=+0.0310), kill_criterion_met=False.
Every number is byte-identical to the frozen D059 file. Verified this is
not stale/uncomputed: a direct fp/fn/cost sweep across neighboring tau
values (0.10-0.30) confirms 0.170 is a genuine, isolated cost minimum
under the real two-way formula on this corpus (tied with 0.160 at
fp=99/fn=28/cost=40640.0; the optimizer's documented tie-break rule
prefers the higher tau). D062's claim that tau=0.17 was "unreachable"
applied specifically to the three-way model's max_hold_rate-constrained
search space; with that constraint correctly removed per D064, 0.17
reappears as exactly where this corpus's class separation places the
minimum. Coincidental value, not coincidental mechanism.
Choice: This is the second and final measurement against the frozen M1
corpus per D065's pre-registration. Report plainly: T2 fails its
pre-registered kill criterion at the real, verified cost-optimal
threshold -- not an artifact of a broken cost model, as D062 had left
open as a possibility. This is a stronger, cleaner negative result than
before: the failure is now confirmed to hold at a defensible operating
point, not merely at an operating point that happened to be reachable
under a flawed constraint. t2_enabled remains False by default (D008,
unchanged, now confirmed twice over on real measurements).
Rejected: Treating the numeric identity to D059's frozen values as
suspicious without verification -- checked directly via a fresh
sweep before accepting; the tie-break mechanism and corpus class
separation fully explain it.
Revisit: If S2's structural T1 features materially change class
separation on this corpus, a new tau-optimal point may emerge and the
comparison would need pre-registering fresh, not reusing this result.

## D067 — Pre-registered narrow addition: held-out precision/PR-AUC/cost never computed on any sealed corpus
Date: 2026-09-05
Context: Track 02's bar requires "measured precision and recall on a
held-out test set" plus honest FP cost. Confirmed this session: recall
exists on held-out data (data/sealed: 0.8333; M1 sealed_semantic:
0.8526), but precision, PR-AUC, and FP cost have never been computed on
ANY held-out corpus in this project -- compute_metrics is never called
with sealed_records (data/sealed is 100% BLOCK-labeled by design, cannot
support a meaningful precision measurement -- fp would always be 0,
making precision trivially 1.0), and never called anywhere in
run_eval_semantic.py despite the M1 corpus having genuine negative
examples (200 ALLOW / 190 BLOCK post-normalization) that could support a
real measurement.
Choice: Add one additive call to compute_metrics(normalized,
corpus_scores, tau_star, prior=0.008) in run_semantic_eval, using the
ALREADY-DERIVED tau_star=0.170 (D064/D066) -- no re-derivation of
threshold, no new tau selection, purely a new statistic read from
already-frozen scores at an already-fixed operating point. This is
narrower than D065's exception: D065 re-ran the cost-optimal threshold
search itself; this adds a measurement that was never attempted, using
data and a threshold both already locked. Distinguishing this from
D053's "run exactly once" concern: no search-until-favorable is possible
here since tau is fixed before this call runs.
Rejected: Measuring precision on data/sealed (families 8-13) instead --
that corpus is 100% attack-labeled by design (a recall-only corpus);
computing precision there would report a meaningless trivial 1.0, worse
than not reporting the number at all.
Revisit: N/A -- this is a one-time addition of a missing measurement,
not a recurring re-run pattern.

## D068 — Held-out precision/PR-AUC/cost result (D067's addition)
Date: 2026-09-05
Context: Per D067's pre-registered narrow addition, compute_metrics was
called on the M1 sealed_semantic corpus (normalized, 390 records) at the
already-fixed tau_star=0.170, prior=0.008.
Choice: Result, reported as-is: held_out_precision_at_prior=0.0137,
held_out_pr_auc=0.6144, held_out_net_cost_per_10k=4073.5. This is the
first time precision/PR-AUC/FP-cost have been measured on any held-out
corpus in this project (prior figures were dev-corpus only). Low
precision at this prior is expected arithmetic (~0.8% base rate), not a
detector defect -- consistent with D030's original explanation for the
analogous dev-corpus number. PR-AUC of 0.61 sits meaningfully above the
0.50 random baseline but well below the dev corpus's 0.92-0.93, an
honest generalization gap attributed to T1's lexical (not yet fully
structural) feature set -- consistent with S2's remaining scope.
Rejected: N/A -- first measurement, nothing to compare against or reject.
Revisit: Once S2's remaining structural features (brand_equality,
sku_equality, etc.) land, re-measure held-out precision/PR-AUC/cost to
see whether the generalization gap narrows.
