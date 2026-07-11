Status: done
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
- 2026-07-10: Implemented canonical bounded calendar payloads and SHA-256 identity, RFC 5545/5546 REQUEST/CANCEL and deterministic multipart calendar MIME pure builders, atomic evaluator enqueue/suppression/expiry integration, runtime outbox/attempt/dedupe tables, UID/sequence/method replay protection, supersession, claims/leases, pre/post-send recovery, validated attempt outcomes, accepted event transitions, 90-day payload cleanup, and privacy/injection bounds. No SMTP/configuration/retry scheduler/operator surface was added.
- 2026-07-10: Review repair enforces exact pending-status/method pairs; adds explicit source-report and public-location IDs to constrained event intent; atomically migrates recoverable pre-release REQUEST rows while rolling back unrecoverable CANCEL rows; and validates report/species/watch/generation/window/horizon/location coherence before canonical payload creation.
- 2026-07-10: Twenty-eight calendar/outbox cases plus thirteen real evaluator integration tests pass 41/41, including malformed relational state, migration, concurrency, rollback, in-flight supersession, ambiguous recovery, cancellation, natural expiry, payload privacy, and zero sockets. Complete network-disabled Python passes 390/390 with 87.00% coverage; browser gate passes 122/122 plus typecheck/build/bundle audit; Ruff, MyPy (87 files), secret scan, hooks, and diff checks pass. Evidence: `.10x/evidence/2026-07-10-bird-alert-calendar-and-outbox.md`.
- 2026-07-11: Final independent review passed with no blocker or significant finding. Review: `.10x/reviews/2026-07-11-bird-alert-calendar-and-outbox-review.md`.
- 2026-07-11: Retrospective preserved method/status pairing and report/event relational coherence as fail-closed state-machine invariants in the active specification and adversarial tests; no additional skill record is needed.

## Blockers

None.
