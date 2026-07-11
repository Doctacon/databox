Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-evolve-product-into-rufous.md
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

## Blockers

None.
