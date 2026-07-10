Status: open
Created: 2026-07-10
Updated: 2026-07-10
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/2026-07-10-build-bird-alert-calendar-and-outbox.md

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

## Blockers

None; local Bridge configuration and bounded verification authorization already exist outside committed records.
