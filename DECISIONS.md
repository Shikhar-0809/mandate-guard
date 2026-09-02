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
