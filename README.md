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
| Dev, no-intent (recall_seen) | 0.982 | T0+T1; misses 5 records (hn_post_auth_cart_mutation cross-category swaps, D064) that score below τ=1.0 without intent signal |
| Dev, full-intent (recall_seen) | 1.000 | T0+T1 at τ=0.220; same 5 records caught once intent is available |
| Sealed families 8–12, pre-registered (recall_unseen) | 1.000 | T0+T1, τ=1.0 |
| Sealed family 13, post-hoc challenge, T0+T1 only | 0.000 | T0 passes by design; T1 alone does not catch it |
| Sealed family 13, post-hoc challenge, T0+T1+T2 | 1.000 | +100pp with T2 enabled |

| Metric | Value |
|--------|-------|
| T1 AUC (holdout) | 0.9646 |
| T1 precision@prior, no-intent (0.8% attack rate) | 0.288 |
| T1 precision@prior, full-intent | 0.272 |
| T1 PR-AUC, no-intent | 0.918 |
| T1 PR-AUC, full-intent | 0.931 |
| Net cost/10k txns, no-intent | ₹49.6 |
| Net cost/10k txns, full-intent | ₹52.8 |
| Cost-optimal τ, no-intent | 1.000 |
| Cost-optimal τ, full-intent | 0.220 |
| Tests passing | 347 |

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

## Precision, PR-AUC, and cost — measured on held-out data (D067/D068)

Recall above is reported on both dev (tuned) and sealed (held-out)
populations. Precision and FP cost were, until this session, only ever
measured on the dev corpus that tau and features are tuned against.
D067/D068 close that gap: `compute_metrics` run against the M1 semantic
corpus (390 frozen records, 200 ALLOW / 190 BLOCK, held out, never
tuned on) at its independently-derived cost-optimal τ=0.170.

| Metric | Held-out value | Dev value (context) |
|--------|-----------------|----------------------|
| Precision@prior (0.8%) | 0.0137 | 0.272–0.288 |
| PR-AUC | 0.614 | 0.918–0.931 |
| Net cost/10k txns | ₹4,073.50 | ₹49.6–52.8 |

Both drops are expected, not defects. Precision at a ~0.8% real-world
attack prior is low arithmetic regardless of detector quality — 0.0137
means roughly 1-in-73 BLOCK verdicts is a genuine attack, which is why
this project reports cost-weighted metrics (FN:FP ≈ 4.6:1) rather than
precision or F1 as the operating criterion. The PR-AUC gap (0.93→0.61)
is an honest generalization gap: T1's current features are lexical
similarity measures (jaccard, trigram, tf-idf, plus one structural
feature), which separate classes well on the corpus they were validated
against and less well on genuinely held-out data. Closing this gap is
S2's remaining, unshipped scope (brand_equality, sku_equality,
numeric_amount_difference_ratio, attribute_conflict).

## A second honest finding: cost-threshold optimization breaks at realistic priors

While deriving an operating threshold for the M1 corpus, cost-optimal threshold
selection (`argmin_τ FP·₹320 + FN·₹1470 + HOLD·₹45`) fails to yield a usable
interior operating point. Post-fix (D060), both raw-count and true-prior
(0.008) optimization land at the **same** corner — τ=1.00, missing ~98% of
fraud — not opposite corners as originally reported. The original
"opposite-direction" framing was partly an artifact of the pre-D060
double-counting bug.

An intermediate fix (D061) introduced a HOLD-capacity constraint
(`max_hold_rate`) on the theory that unlimited-cost-free deferral to HOLD
was driving the degenerate corner. Further investigation (D064) found this
diagnosis was itself wrong: `cascade.check()` never produces a HOLD
verdict without T2 actually being invoked, and every evaluation context
this project uses to select a threshold (dev corpus, M1 corpus) evaluates
T0+T1 only, with T2 disabled by default. There is no HOLD tier to price or
cap in that configuration. D061's `max_hold_rate` mechanism has been
removed; cost is now a plain two-way FP/FN calculation with no discount
for ambiguous scores.

The τ=1.00 corner is now understood as a real property of this corpus's
class separation at low prevalence, not an artifact of how HOLD was
priced. Whether a genuinely usable interior threshold exists depends on
T1's features separating attacks from legitimate traffic well enough -
tracked as S2's continued relevance. Full derivation: D058, D060, D061
(superseded), D062 (superseded pending re-derivation), D064. This remains
a real, disclosed limitation of single-threshold cost optimization at low
prevalence.

Note on threshold-selection methodology, stated plainly rather than left
for a reader to reverse-engineer: dev-corpus τ is selected on raw FP/FN
counts with no prior-weighting applied at selection time (D069); the
M1-corpus τ (D058) uses a simplified 1:1 FN:FP ratio rather than this
project's stated 4.6:1 cost ratio. Both are disclosed, deliberate
choices — but they are different conventions, not one consistent rule
applied across corpora.

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
| T0 only | 0.833 | Misses family 13; identical to T0+T1 on this population -- T1 adds no recall without intent populated |
| T0+T1+T2 | 1.000 | This system, sealed families 8–13 combined |

Beating the regex baseline is not a close win — it is a category mismatch.
Mandate deviation is a property of (intent, cart, payment) triples. A regex
detector operates on individual field strings.

## Local demo

A FastAPI endpoint and single-page UI let you exercise the cascade
interactively, locally, no cloud dependency.

```powershell
python -m uvicorn mandate_guard.api:app --app-dir src --reload --port 8000
```

Open http://localhost:8000. Six preset scenarios cover T0 (amount over
cap, wrong merchant, cart tampering after approval), T1 (brand
substitution, post-auth SKU swap — the exact archetype whose scoring bug
this session's cost-model investigation started from; τ=0.220 correctly
blocks it at score 0.228), and one legitimate baseline. Each preset runs
the check immediately on click — no typing required for the core demo.
An "Enable T2" toggle exercises the LLM verifier live (requires Ollama
running locally with qwen2.5:7b pulled; adds 0.6–1.5s latency per call).

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
| `DECISIONS.md` | Append-only decision log (D001–D069; D014 unused, numbering skip) |
| `RULES.md` | Enforceable constraints checked by `make check` |
| `docs/T2_STATE_MACHINE.md` | T2 async state machine detail |
| `data/GENERATION.md` | Corpus generation parameters |

## Scope and safety

Defense-only. No attack payloads outside `sandbox/`. No evasion analysis. No
real merchant or bank identifiers in `data/`. The LLM tier produces evidence
only — enforcement is deterministic.
