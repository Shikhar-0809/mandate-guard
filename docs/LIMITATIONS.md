# LIMITATIONS

This document states the known scope boundaries of mandate-guard as of
the current evaluation corpus. Each limitation is a measurement gap,
not a design flaw. Where a measurement plan exists, it is stated.

## 1. Synthetic corpus

All training and evaluation data is generated from a parametric model
in data/generate.py. Every distributional parameter is documented in
data/GENERATION.md as either a cited source or an explicit ASSUMPTION.
Real attack distributions may differ from the generator's assumptions
in ways that inflate apparent performance. The family-split evaluation
protocol (dev on families 1-7, sealed on families 8-12) mitigates
within-distribution overfitting but does not substitute for real data.

Measurement plan: replace the synthetic corpus with real Razorpay
transaction data when available. The evaluation protocol in
scripts/run_eval.py is corpus-agnostic and requires no modification.

## 2. Prior-dependent precision

Precision at the production prior is reported at an assumed 0.8%
mandate fraud rate. This figure is labeled ASSUMPTION throughout the
codebase. The actual Razorpay mandate fraud rate is unknown. Precision
is highly sensitive to the prior at low prevalence; a 10x change in
the prior moves precision by roughly an order of magnitude.

Measurement plan: calibrate the assumed prior against observed fraud
labels quarterly. The cost-optimal threshold tau_star is derived by
minimizing expected cost over the calibrated probability, so it moves
automatically when the prior changes.

## 3. Consent-time compromise out of scope

mandate-guard detects deviation at payment execution time: the moment
when the PSP sees a money movement request. If the user's intent was
compromised before the mandate was signed — for example, if the user
was deceived into authorizing a fraudulent mandate in the first place —
mandate-guard cannot detect this. The system verifies that the agent
acted within the mandate; it cannot verify that the mandate itself
reflects the user's genuine intent.

Measurement plan: out of scope for this system. Consent-time
compromise requires a separate layer at mandate issuance time.

## 4. Reject inference out of scope

mandate-guard does not model adversarial adaptation. When an attack is
blocked, the attacker may adjust their strategy. The evaluation
measures recall on a fixed corpus of attack strategies; it does not
measure whether blocking degrades the attack distribution over time or
causes attackers to find new evasion paths. This is a standard
limitation of static evaluation benchmarks.

Measurement plan: red-team exercises with adaptive adversaries after
deployment. Out of scope for the current submission.

## 5. T2 did not earn its place on this corpus

T2 ships wired but degraded by default. The pre-registered kill
criterion (documented in EVAL.md before any T2 code existed) requires
T2 to lift recall_unseen by at least 2 percentage points over T0+T1.
T0 achieves recall_unseen=1.0 on the evaluation corpus, making the
criterion mathematically impossible to satisfy.

This outcome is a consequence of corpus construction: every attack in
the dev and sealed corpora violates at least one T0-detectable
constraint (amount cap, beneficiary allowlist, cart hash, mandate ID,
scope monotonicity). In a production deployment, semantic attacks may
evade T0 — subtle beneficiary substitution, category confusability at
the description level, or injection that manipulates the cart manifest
without triggering a hash mismatch. Those cases are where T2 would
provide marginal lift. The current corpus cannot measure this.

The honest outcome is reported: T2 is an architecture decision, not a
metrics win. The kill criterion was honored.

Measurement plan: extend the corpus with semantic attacks that evade
T0. Re-run scripts/run_eval.py unchanged. Enable T2 if and only if the
criterion is met.
