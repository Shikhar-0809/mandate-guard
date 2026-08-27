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
