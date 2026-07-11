Status: open
Created: 2026-07-10
Updated: 2026-07-10
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/done/2026-07-10-implement-watched-bird-evaluator-and-reports.md

# Build bird-alert calendar and durable outbox

## Scope

Implement stable UID/sequence event state, RFC iCalendar REQUEST/CANCEL and MIME builders, transactional durable outbox/attempt schema, canonical payload hashing, atomic claims, supersession, cancellation, and retention governed by `.10x/specs/bird-alert-calendar-and-smtp-delivery.md`. This child does not open an SMTP socket.

## Acceptance criteria

- Create/update/cancel share stable UID and strictly increasing sequence; events use Arizona-local timezone-safe two-hour windows and five-day horizon; natural expiry emits nothing.
- Canonical bounded persisted facts produce standards-valid REQUEST/CANCEL calendar MIME with text alternative and no remote assets/private/raw/arbitrary payload.
- Event intent and outbox enqueue are atomic; uniqueness, hashes, claims, lease expiry, attempts, supersession, and terminal states prevent duplicate intent under replay/concurrency.
- Claim recovery is allowed only before send ambiguity; state machine rejects invalid transitions.
- Ninety-day cleanup retains unresolved unknown and minimal UID/sequence/dedupe state.
- Pure builder/state tests validate RFC fields, injection resistance, payload bounds, concurrency, rollback, update/cancel/expiry, and zero network calls.

## Explicit exclusions

No SMTP connection, TLS/auth settings, retry scheduler, live email, operator reconciliation UI, Google Calendar API, or matching logic.

## Evidence expectations

Record schema/state-transition table, RFC parser results/golden semantic assertions, UID/sequence lifecycle, atomic claims/concurrency, payload privacy/injection guards, retention, and no-network proof.

## Progress and notes

- 2026-07-10: Ticket isolates deterministic event/outbox mechanics from external delivery side effects.

## Blockers

None.
