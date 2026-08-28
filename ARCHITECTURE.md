# ARCHITECTURE

## Loss class
Mandate deviation: a payment executed by an AI agent under a valid delegated
mandate, where beneficiary, amount, or purchase intent materially deviates from
what the principal consented to. Injection, cart tampering, scope expansion and
counterfeit merchant selection are CAUSES, not separate loss classes.

## Gap statement
AP2 anchors agent purchases in signed Intent, Cart and Payment Mandates, then
delegates cart-versus-intent verification to the buyer-side agent — the exact
component that can be injected. AP2 proves the agent was authorised. It does not
prove the agent did what it was authorised to do. That check belongs at the party
that sees the money move: the PSP.

## Tiers

| Tier | Runs on | p99 | Cost/call |
|------|---------|-----|-----------|
| T0 deterministic mandate constraints | 100% | ~3 ms | ₹0 |
| T1 calibrated GBM, 40–60 features | 100% | ~10 ms | ₹0 |
| T2 LLM semantic verifier | ≤0.5% | 600–1500 ms | ₹0.4–2.0 |

T0 checks: amount vs per-txn cap, cumulative vs period cap, beneficiary in
allowlist, MCC allowed, mandate active and in window, pre-debit notification
satisfied, cart manifest hash matches approved snapshot, delegation scope
monotonicity.
T0 covers three concept classes: authorization violations (expiry,
amount, beneficiary, category), integrity violations (cart hash),
and structural delegation violations (scope expansion, mandate ID).
Behavioral/semantic risk at the content level is T1/T2 territory.

T1 runs on 100% deliberately — a censored score distribution blinds drift monitors.

T2 gate: T0 passed AND `purchase_intent` is non-empty AND
(`calibrated_score ∈ [τ_low, τ_high]` OR `deviation_type ∈
{SKU_SEMANTIC, BENEFICIARY_IDENTITY}`). Numeric deviation never
reaches T2; arithmetic does not need a language model. When
`purchase_intent` is empty, semantic verification is impossible
and T2 is not invoked.

## Invariants

1. The LLM produces evidence. It never holds authority. Enforcement is
   deterministic and lives in the policy engine.
2. T2 is never on the synchronous blocking path. Mandate rails have a deferral
   window; ambiguity resolves to HOLD, not to a 1.5 s wait.
3. The availability floor is T0: a constraint check needing no model, no network
   call, no feature store. Load shedding never sheds T0.
4. T0 reads only strongly-consistent state. Approximate or cached values are
   T1 features only.
5. A retry returns the frozen verdict, never a re-score. Same `agent_request_id`
   with a different `cart_hash` is not a duplicate — it is a tampering signal
   (`IDEMPOTENCY_PAYLOAD_MISMATCH`).
6. Untrusted content is typed `UntrustedBlob` and is never concatenated into a
   prompt or a rule expression.
7. A delegation chain may only narrow scope. Widening is a deterministic T0
   violation (`SCOPE_EXPANSION`).
8. Money is minor units, integer, always. No float currency anywhere.
9. No per-tenant code branches. Tenant variation is config via `PolicyResolver`.
10. Every field in a log or audit envelope is schema-declared with a `pii` class.

## Verdicts
`ALLOW` / `HOLD` / `BLOCK`. Three-way rather than binary because HOLD
costs ~₹45 against BLOCK at ~₹320 — the deferral window is a property of
the rail, so exploit it. CHALLENGE is absent: no challenge flow exists or
will be built; HOLD is the correct deferral state.

## Cost matrix
All inputs are ASSUMPTIONS until cited in `config/cost_model.yaml`.

```
FP   ₹320   ticket 2600 × 0.40 non-retry × 0.25 margin + 60 support
FN   ₹1470  ticket 2600 × 0.22 unrecoverable + 900 dispute ops
HOLD ₹45
```

FN:FP ≈ 4.6:1. This ratio, not F1, chooses the threshold. Per-tenant thresholds
are derived by expected-cost minimisation over the calibrated probability, which
requires calibration — report ECE.

## Degradation

| Failure | Degrade to | Open or closed |
|---------|-----------|----------------|
| T2 down | T1 with shifted threshold | fail to HOLD |
| T1 down | T0 only | fail open below per-txn cap, CHALLENGE above |
| Features down | T0 + request-local | fail open, log `DEGRADED_FEATURES` |
| Store down | reject 503 | fail CLOSED — cannot verify consent |

## Storage (BUILD tier)
SQLite for decisions/mandates/config. In-process counters. Local FS audit
envelopes. Outbox table, not Kafka. Postgres/Redis/ObjectLock are STUB seams
running the same contract suite.

First bottleneck is the SQLite single writer, found empirically by
`make bench-limits`, not asserted.

## Trust boundary
Untrusted inputs: merchant catalog text, product descriptions and reviews,
dispute evidence documents, agent rationale strings, third-party tool outputs,
delegation tokens minted by other agents. All enter as data, never as instruction.

T2 has a closed output schema: `{verdict: enum, evidence_spans, confidence}`.
It cannot emit an action, a threshold, a scope change, or free text that enters
control flow.

## Audit record
Hash-chained per tenant, `prev_envelope_hash` on each envelope, hourly signed
Merkle root. `tools/audit_verify.py` recomputes the chain and reports the first
divergence. Retention 400 days (dispute cycle), 7-year digest.

## Deferred — DOCUMENT tier, reasons in DECISIONS.md
Partitioning and merchant skew. Storage tiering and retention. Rollout controller
as running code. Observability UI. Multi-tenancy beyond the cost matrix.
mTLS, KMS, RBAC, SBOM.
