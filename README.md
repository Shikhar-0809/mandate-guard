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
| T1 | Calibrated LightGBM, 7 semantic features | 100% of traffic | ~10 ms |
| T2 | LLM semantic verifier (qwen2.5:7b via Ollama) | ≤0.5% of traffic | async |

T0 catches structural violations: amount cap, merchant allowlist, category
scope, cart hash integrity, delegation monotonicity, mandate ID.

T1 catches semantic violations: brand substitution, scope creep, intent-cart
mismatch. Trained on intent-populated records only.

T2 catches ambiguous semantic cases T1 cannot resolve. Runs asynchronously;
ambiguity resolves to HOLD, never to a blocking wait. T2 produces evidence
only — enforcement is always deterministic.

## Results

| Metric | Value |
|--------|-------|
| recall_seen (dev families 1–7, 14–15) | 1.000 |
| recall_unseen (sealed families 8–12, record-level) | 1.000 |
| recall_unseen (challenge family 13, T0+T1 only) | 0.240 |
| recall_unseen (challenge family 13, T0+T1+T2) | 1.000 |
| T1 AUC | 0.999 |
| T1 precision@prior (0.8% attack rate) | 0.289 |
| T2 FPR on hard negatives (BLOCK) | 0.49% [Wilson 95% CI: 0.09%–2.70%] |
| Tests passing | 219 |

**Sealed-set integrity note:** Families 8–12 are pre-registered (SHA-256
committed before development). Family 13 is a post-hoc challenge set added
after T2 failure (D008); RULES 19 was violated and is disclosed in EVAL.md
and DECISIONS.md (D019). Results on families 8–12 and family 13 are reported
separately throughout.

**T2 kill criterion:** Pre-registered 2026-08-27. T2 lifted recall_unseen on
family 13 by +16.67pp (0.240 → 1.000), exceeding the ≥2pp threshold. This
result is post-hoc (family 13 was created after criterion registration).
T2 is architecturally justified by the AP2 gap argument; the metric result
is supporting evidence, honestly bounded.

## Corpus

| Split | Records | Families |
|-------|---------|----------|
| Dev benign | 800 | — |
| Dev hard negatives | 226 | 11 archetypes |
| Dev attacks | 270 | 1–7, 14–15 |
| Sealed attacks | 150 | 8–13 |

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
| T0+T1+T2 | 1.000 | This system |

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

To run T2 (optional): install [Ollama](https://ollama.com), pull
`qwen2.5:7b`, then set `T2_ENABLED=true`.

## Key documents

| File | Purpose |
|------|---------|
| ARCHITECTURE.md | System design, invariants, threat-to-tier mapping |
| EVAL.md | Measurement protocol, all metrics, honest limitations |
| DECISIONS.md | Append-only decision log (D001–D033) |
| RULES.md | Enforceable constraints checked by `make check` |
| docs/T2_STATE_MACHINE.md | T2 async state machine detail |
| data/GENERATION.md | Corpus generation parameters |

## Scope and safety

Defense-only. No attack payloads outside `sandbox/`. No evasion analysis.
No real merchant or bank identifiers in `data/`. The LLM tier produces
evidence only — enforcement is deterministic.
