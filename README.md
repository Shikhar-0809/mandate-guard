# mandate-guard

Defensive detection for one loss class: **mandate deviation** — a payment
executed by an AI agent under a valid delegated mandate, where beneficiary,
amount, or purchase intent materially deviates from what the principal
consented to.

Built for Razorpay AI Buildathon 2026, Track 02 (AI Risk Manager).

## The problem

Agent Payment Protocol (AP2) delegates cart-versus-intent verification to the
buyer-side agent — the exact component that can be prompt-injected. AP2 proves
the agent was authorised. It does not prove the agent did what it was
authorised to do. That check belongs at the PSP.

## How it works

Three-tier cascade, each tier adding a layer of detection:

| Tier | Mechanism | Runs on | p99 target |
|------|-----------|---------|------------|
| T0 | Deterministic mandate constraints | 100% of traffic | ~3 ms |
| T1 | Calibrated LightGBM, 8 semantic features | 100% of traffic | ~10 ms |
| T2 | LLM semantic verifier (qwen2.5:7b via Ollama) | ≤0.5% of traffic | async |

T0 catches structural violations: amount cap, merchant allowlist, category
scope, cart hash integrity, delegation monotonicity, mandate ID.

T1 catches semantic violations: brand substitution, scope creep, intent-cart
mismatch, category-hierarchy distance. Trained on intent-populated records only.

T2 catches ambiguous semantic cases T1 cannot resolve. Runs asynchronously;
ambiguity resolves to HOLD, never to a blocking wait. T2 produces evidence
only — enforcement is always deterministic.

## Results

Three separate populations, reported separately — not one blended number.

| Population | Recall | Notes |
|------------|--------|-------|
| Dev families 1–7, 14–15 (recall_seen) | 1.000 | T0+T1 |
| Sealed families 8–12, pre-registered (recall_unseen) | 1.000 | T0+T1, τ=1.0 |
| Sealed family 13, post-hoc challenge, T0+T1 only | 0.000 | T0 passes by design; T1 alone does not catch it |
| Sealed family 13, post-hoc challenge, T0+T1+T2 | 1.000 | +100pp with T2 enabled |

| Metric | Value |
|--------|-------|
| T1 AUC (holdout) | 0.9646 |
| T1 precision@prior (0.8% attack rate) | 0.288 |
| Tests passing | 342 |

**Sealed-set integrity note:** Families 8–12 are pre-registered (SHA-256
committed before development). Family 13 is a post-hoc challenge set added
after an earlier T2 kill-criterion failure; this protocol deviation is
disclosed in EVAL.md and DECISIONS.md (D019). Results on families 8–12 and
family 13 are reported separately throughout, never blended into one number.

## T2: two kill-criterion measurements, one pass and one fail

T2's kill criterion has now been measured twice, independently:

**Family 13 (post-hoc, disclosed):** T2 lifts recall from 0.000 to 1.000 on
this 25-record, 4-archetype-cycled challenge set — a clear pass, but this
criterion was not pre-registered before family 13 existed (D008/D020).

**M1 semantic corpus (pre-registered, D053/D057):** a purpose-built 500-record
corpus with genuine per-record diversity, designed specifically to test
semantic substitution/ambiguity at real scale. The T2 kill criterion was
**not met** on this corpus at the only operating point tested (τ=0.17,
chosen under pre-D060 cost accounting later found incorrect). That operating
point is unreachable under corrected cost accounting (D062); the previously
reported magnitudes (recall 0.853→0.768 on deviations, hard-negative block
rate 0.133→0.164) cannot be cited as current. T2 has not demonstrated a
benefit in any measurement attempted so far on a pre-registered corpus at a
defensible τ. The qualitative direction of the M1 comparison (T2 did not
clearly help) remains provisionally plausible but is unconfirmed pending S2
(structural T1 features) and a rerun at whatever τ the corrected optimizer
selects on the improved feature set. See D062.

**Read together:** T2 has not demonstrated a metrics win on any
pre-registered measurement at a defensible operating point. Its one favorable
number is post-hoc and drawn from a narrow, repetitive challenge set. This is
reported plainly rather than leading with the favorable number and omitting
the negative one. `t2_enabled=False` remains the default (D008, unchanged).
T2 ships wired, tested, and documented — an architectural bet on the AP2 gap
argument, not a confirmed metrics win.

## A second honest finding: cost-threshold optimization breaks at realistic priors

While deriving an operating threshold for the M1 corpus, cost-optimal threshold
selection (`argmin_τ FP·₹320 + FN·₹1470 + HOLD·₹45`) fails to yield a usable
interior operating point. Post-fix (D060), both raw-count and true-prior
(0.008) optimization land at the **same** corner — τ=1.00, missing ~98% of
fraud — not opposite corners as originally reported. The original
"opposite-direction" framing was partly an artifact of the pre-D060
double-counting bug.

D061 added a HOLD-capacity constraint (`max_hold_rate`) so the optimizer cannot
treat unlimited deferral as free. This eliminates that corner but still does
not produce a usable interior threshold: the corrected optimizer only offers
two corner-like regimes depending on the capacity assumption — block nearly all
traffic (fp~195/200 ALLOW) at low HOLD capacity, or block most traffic while
deferring ~20% (fp~121–136) at higher HOLD capacity. No smooth interior
tradeoff exists between them on this corpus.

This is now understood as likely a class-separation problem in T1's current
features on the M1 corpus, not a cost-model problem per se — see D062 and S2
(structural features, CHANGES.md). Full derivation: D058, D060, D061, D062.
This is disclosed as a real, general limitation of single-threshold cost
optimization at low prevalence — not a defect specific to this corpus, and
directly relevant to anyone deploying a similar detector at a realistic fraud
rate.

## Corpus

| Split | Records | Families |
|-------|---------|----------|
| Dev benign | 800 | — |
| Dev hard negatives | 226 | 11 archetypes |
| Dev attacks | 270 | 1–7, 14–15 |
| Sealed attacks | 150 | 8–13 |
| Sealed semantic (M1) | 500 | 10 categories, ALLOW/DEVIATION/UNCERTAIN |

Corpora are fully synthetic. All generation parameters live in
`data/GENERATION.md` with ASSUMPTION labels where uncited.

## Baselines

| Baseline | Recall | Notes |
|----------|--------|-------|
| allow-everything | 0.000 | — |
| block-everything | 1.000 | FPR = 1.000 |
| amount-threshold | 0.407 | Misses non-amount families |
| regex injection detector | 0.000 | Wrong task — see EVAL.md §Three-way injection experiment |
| T0 only | 0.870 | Misses semantic families 13–15 |
| T0+T1+T2 | 1.000 | This system, sealed families 8–13 combined |

Beating the regex baseline is not a close win — it is a category mismatch.
Mandate deviation is a property of (intent, cart, payment) triples. A regex
detector operates on individual field strings.

## Reproduce

Requires Python 3.11+, offline, no API keys.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python data/generate.py --split dev
python -m pytest
```

To run T2 in evaluation (optional): install Ollama, pull qwen2.5:7b, then run
`python scripts/run_eval.py --enable-t2`. T2 itself is controlled via
`T2Config(t2_enabled=...)` in code (default `False` — see D008), not an
environment variable.

## Key documents

| File | Purpose |
|------|---------|
| `ARCHITECTURE.md` | System design, invariants, threat-to-tier mapping |
| `EVAL.md` | Measurement protocol, all metrics, honest limitations |
| `DECISIONS.md` | Append-only decision log (D001–D059; D014 unused, numbering skip) |
| `RULES.md` | Enforceable constraints checked by `make check` |
| `docs/T2_STATE_MACHINE.md` | T2 async state machine detail |
| `data/GENERATION.md` | Corpus generation parameters |

## Scope and safety

Defense-only. No attack payloads outside `sandbox/`. No evasion analysis. No
real merchant or bank identifiers in `data/`. The LLM tier produces evidence
only — enforcement is deterministic.
