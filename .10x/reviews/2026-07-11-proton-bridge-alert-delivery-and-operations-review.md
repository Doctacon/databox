Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Target: .10x/tickets/done/2026-07-10-implement-proton-bridge-alert-delivery-and-operations.md
Verdict: pass

# Proton Bridge alert delivery and operations review

## Findings

Initial security review found accepted-state loss when an older in-flight sequence resolved after a newer event, missing-STARTTLS transient classification, and an impossible retry action for suppressed unknown rows. A follow-up found the same accepted-snapshot gap in automatic SMTP acceptance. Repairs created one canonical non-regressing accepted-snapshot path for automatic/manual acceptance, coherent greater-sequence cancellation from accepted facts, state-derived reconciliation actions, terminal inactive not-delivered reconciliation, and permanent zero-retry STARTTLS failure.

Final review verified SecretStr/redaction; numeric loopback and exact public-CA hostname verification; EHLO/STARTTLS/EHLO/auth/send ordering; explicit acceptance; atomic claims/crash/concurrency behavior; exact 1/5/15-minute pre-acceptance retries; permanent and delivery-unknown classification; no automatic unknown resend; idempotent manual reconciliation; stable UID/sequence cancellation; strict API/UI privacy/actions; 90-day retention; and bounded one-time live Bridge verification without inbox claims.

Expanded focused review passed 79/79. Implementation evidence records 408 full Python and 125 browser tests plus static, typing, bundle, secret, hook, and redacted live acceptance gates.

## Verdict

Pass. No blocker or significant finding remains.

## Residual risk

SMTP acceptance proves local Bridge acceptance only, not remote inbox delivery or calendar rendering.
