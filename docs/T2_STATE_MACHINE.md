# T2 State Machine

A HOLD-pending record transitions through five states:

RECEIVED → T0_DECIDED → T1_SCORED → HOLD_PENDING_T2 → FINALIZED


## State rules

**RECEIVED**: Request accepted; idempotency key recorded. Duplicate
`agent_request_id` with a different `cart_hash` exits immediately as
`IDEMPOTENCY_PAYLOAD_MISMATCH` (Invariant 5).

**T0_DECIDED**: All deterministic mandate checks complete. BLOCK or ALLOW
exits the pipeline here; only records that pass T0 continue to T1.

**T1_SCORED**: Calibrated score appended to the record. If the score exits
the ambiguous band `[τ_low, τ_high]`, the record finalises immediately as
ALLOW or BLOCK. HOLD_PENDING_T2 is entered only when the T2 gate condition
is also satisfied: `amount ≥ X` OR `deviation_type ∈ {SKU_SEMANTIC,
BENEFICIARY_IDENTITY}`.

**HOLD_PENDING_T2**: T2 is invoked asynchronously. The deferral window is
rail-defined (typically 30–120 s) and is the SLA for this state. Three exit
paths:

| Exit condition | Final verdict | Logged reason |
|----------------|---------------|---------------|
| T2 returns within window | T2 verdict (BLOCK or HOLD) | — |
| Timeout | HOLD | `DEGRADED_T2_TIMEOUT` |
| Parse failure | HOLD | `DEGRADED_T2_PARSE` |
| Confidence below floor | HOLD | `DEGRADED_T2_LOW_CONFIDENCE` |

**FINALIZED**: Verdict is frozen and immutable. Any retry on the same
`agent_request_id` returns the frozen verdict without re-scoring.

## Disagreement rule

T2 can upgrade HOLD → BLOCK or confirm HOLD → HOLD. It cannot override a
T1 BLOCK to ALLOW. When T2 returns ALLOW on a record the pipeline holds,
the higher-risk verdict (HOLD) stands.

## Retry discipline

T2 is invoked exactly once per HOLD_PENDING_T2 entry. Transient Ollama
errors produce immediate FINALIZED(HOLD), not a retry loop. This prevents
retry storms from converting a degraded T2 into a latency event on the
blocking path.
