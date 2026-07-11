Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-evolve-product-into-rufous.md
Depends-On: .10x/tickets/done/2026-07-10-implement-proton-bridge-alert-delivery-and-operations.md

# Implement trip-plan calendar invitations

## Scope

Implement trip-plan event identity/state, canonical payload, durable outbox integration, explicit send/update/retry/reconciliation API, and fake-transport verification governed by `.10x/specs/trip-plan-calendar-invitations.md`.

## Acceptance criteria

- Stable installation+plan UID and monotonically increasing sequence; first/repeat accepted sends are REQUEST 0/1 without duplicates.
- Canonical facts exactly match complete source plan location/window/field plan/recommendations/weather/caveats and fail closed on deletion/mismatch/tamper.
- Event-kind schema cleanly separates trip plans from watches without fabricated watch identity or weakened watch constraints.
- Explicit POST only; GET/startup/plan creation/tests send nothing. Pending/unknown/accepted/failed relationships and allowed actions are strict.
- Existing exact-CA Bridge transport, 1/5/15 retries, claims, ambiguity, accepted snapshots, redaction, retention, and concurrency are reused.
- No new live message is sent because prior bounded live authorization is exhausted; fake SMTP proves transport behavior.
- Full backend/API/calendar/outbox/delivery/privacy tests pass.

## Explicit exclusions

No React controls, cancellation, plan deletion, new recipient/configuration, live verification send, browser SMTP, or watched-event identity reuse.

## Evidence expectations

Record event-kind schema/state transitions, RFC payload parser, stable UID/sequence, source-plan relationship attacks, concurrency/replay/unknown/retry, no-send proof, and independent review.

## Progress and notes

- 2026-07-11: Implemented a separate constrained `trip_plan` event/outbox relationship, stable installation+plan UID, sequence updates, canonical bounded REQUEST payload and source hash, atomic claims, 1/5/15 retry timing, ambiguity handling, accepted snapshots, explicit reconciliation, 90-day retention, safe typed API status, confirmed POST-only sending, and runtime/offline migration documentation.
- 2026-07-11: Added fake-SMTP-only tests for stable identity, deduplication, update sequencing, canonical RFC output, source tamper/deletion rollback, unknown reconciliation, no startup/GET send, API confirmation, acceptance wording, and response redaction. No live SMTP verification was run.
- 2026-07-11: Focused backend/API/calendar/outbox regression gate passes 79/79; full Python gate passes 440/440 at 86.25% coverage; browser validation/tests pass 205/205 plus typecheck/build. Ruff and MyPy pass for changed Python modules. Evidence: `.10x/evidence/2026-07-11-trip-plan-calendar-invitations.md`.
- 2026-07-11: Repaired independent review blockers: canonical source eligibility now rejects null/blank/missing/duplicate/private/invalid/unreviewed eBird identities; failed/unknown replacement enqueue is atomic and confirmed APIs immediately send it; a confirmed due-delivery endpoint handles scheduled retries; runtime integrity checks cover source plans, current intent/outbox, attempts, and snapshots; Arizona timestamps require `-07:00`; retention keeps current intent/action coherent. Added concurrency, lease recovery, API retry/reconciliation idempotency, snapshot non-regression, cleanup, migration parity, privacy, and offset tests. Focused repair/regression gate passes 100/100, repeated trip suite passes 75/75, full Python passes 457/457 at 86.51% coverage, and browser remains 205/205 with typecheck/build.
- 2026-07-11: Independent follow-up review passed every privacy, lifecycle, concurrency, retry, ambiguity, relationship, migration, retention, redaction, and no-implicit-send criterion. Review: `.10x/reviews/2026-07-11-trip-plan-calendar-invitations-review.md`.
- 2026-07-11: Retrospective preserved the initial privacy-authority and non-atomic retry failures as comprehensive regression tests and explicit local-worker documentation; no separate record is needed.

## Blockers

None.
