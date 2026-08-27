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
