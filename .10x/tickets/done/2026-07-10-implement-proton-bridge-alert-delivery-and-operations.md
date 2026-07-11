Status: done
Created: 2026-07-10
Updated: 2026-07-10
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/done/2026-07-10-build-bird-alert-calendar-and-outbox.md

# Implement Proton Bridge alert delivery and operations

## Scope

Implement server-only SMTP settings validation, exact-CA loopback STARTTLS transport, durable sender/claim workflow, 1/5/15-minute transient retries, permanent/ambiguous classification, manual reconciliation/retry API/UI, safe status presentation, and 90-day cleanup governed by `.10x/specs/bird-alert-calendar-and-smtp-delivery.md`.

Use generic SMTP interfaces; Proton Bridge is configuration, not a proprietary SDK dependency. Preserve the existing one-test-email and one-test-invitation authorization for explicit final verification only.

## Acceptance criteria

- Settings require numeric loopback, exact exported public certificate CA, STARTTLS, Bridge-generated secret credentials, organizer=username, and one recipient; all values remain secret/redacted and absent from bundles/traces/errors/records.
- Sender atomically claims one persisted payload and marks accepted only after explicit Bridge acceptance.
- Explicit pre-acceptance transient failures retry exactly after 1, 5, and 15 minutes; permanent failures stop; post-send ambiguity becomes unknown and never auto-resends.
- Manual mark-delivered, mark-not-delivered-and-retry, and failed retry actions are confirmed, idempotent, safe, and preserve stable UID/incremented sequence.
- Startup, GETs, watch changes, failed refreshes, and tests perform zero implicit sends.
- Fake SMTP/TLS tests cover certificate/hostname/loopback rejection, commands/order, retries, crashes/claims/concurrency, redaction, update/cancel payloads, and retention.
- Explicit live verification sends at most the authorized one test message and one invitation, records only redacted acceptance evidence, and makes no inbox-rendering guarantee.

## Explicit exclusions

No remote SMTP, Gmail/Google Calendar API, TLS bypass, account password/private key, automatic unknown resend, bulk alerts, secret display, or claim of exactly-once/inbox delivery.

## Evidence expectations

Record configuration boundary without values, fake-server/TLS protocol results, retry timing/state transitions, unknown reconciliation, concurrency, bundle/log/trace redaction, no-implicit-send proofs, and bounded live Bridge acceptance if executed.

## Progress and notes

- 2026-07-10: Ticket derives from user-ratified loopback Bridge, slide/cancel, retry, unknown-reconciliation, and retention decisions.
- 2026-07-10: Implemented server-only SecretStr configuration, numeric-loopback exact-public-CA STARTTLS transport, explicit atomic sender, 1/5/15-minute pre-acceptance retries, permanent/ambiguous classification, idempotent delivered/not-delivered reconciliation, stable-UID greater-sequence retries, safe API/React operations, 90-day cleanup, explicit commands, bundle/config redaction, and no-implicit-send guards.
- 2026-07-10: Fake/state/API/UI tests pass; complete network-disabled Python suite passes 402/402 at 86.36% coverage; browser gate passes 125/125 plus typecheck/build and a 12-name/10-configured-value bundle audit; MyPy passes 89 files. Evidence: `.10x/evidence/2026-07-10-proton-bridge-alert-delivery-and-operations.md`.
- 2026-07-10: Redacted live preflight passed without sending. The already-authorized one test email and one test invitation were each attempted exactly once and explicitly accepted by the local Bridge; the durable one-attempt ledger prevents repeats. No inbox/calendar-rendering claim is made.
- 2026-07-10: Review repair preserves and strictly validates canonical unknown REQUEST/report linkage, persists accepted snapshots, never regresses a newer same-UID event, and creates coherent cancellation when an ambiguously accepted request was suppressed/inactive. Inactive unknowns now expose terminal mark-not-delivered without retry; active coherent rows alone expose retry. Missing STARTTLS is a permanent zero-retry failure. New sequence-advance/pause, suppression/delivered, concurrency/replay/rollback, action-contract, and missing-STARTTLS tests pass.
- 2026-07-10: Final automatic-acceptance repair routes both explicit SMTP acceptance and manual mark-delivered through one non-regressing snapshot propagation. The exact sequence-0-send → sequence-1-pending → sequence-0-accepted → pause/delete flow produces a sequence-2 CANCEL from sequence-0 facts; automatic replay/concurrency/rollback and newer-snapshot precedence pass. Focused backend tests pass 64/64, full Python passes 408/408 at 86.26%, and browser gate remains 125/125.
- 2026-07-11: Final independent security/acceptance review passed with no blocker or significant finding. Review: `.10x/reviews/2026-07-11-proton-bridge-alert-delivery-and-operations-review.md`.
- 2026-07-11: Retrospective preserved non-regressing accepted snapshots, ambiguity-safe action derivation, and STARTTLS fail-closed classification directly in the active specification and adversarial transport/state tests; no additional skill record is needed.

## Blockers

None.
