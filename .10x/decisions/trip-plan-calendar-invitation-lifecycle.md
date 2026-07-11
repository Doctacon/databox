Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Trip-plan calendar invitation lifecycle

## Context

Rufous can email watched-bird invitations through the local Proton Bridge transport, but completed Trip Planner results cannot be sent to the calendar. The user wants an explicit option on each trip plan.

## Decision

- A completed persisted trip plan exposes an explicit **Send calendar invite** action. GET, replay, startup, and plan creation MUST NOT send implicitly.
- One stable deterministic UID is derived from the local installation identity and trip-plan ID. Repeated accepted sends update the same calendar event with a strictly increasing sequence rather than creating duplicates.
- DTSTART/DTEND use the persisted outing window and Arizona timezone; LOCATION uses the persisted normalized plan location. SUMMARY identifies Rufous and the outing. DESCRIPTION is deterministic and bounded from persisted field-plan text, target names, weather status, and caveats.
- Sending uses the existing server-only generic SMTP/Proton Bridge configuration, exact-CA STARTTLS transport, durable claims/attempts, explicit acceptance, retry classification, delivery-unknown handling, reconciliation, redaction, and recipient boundary.
- A pending or delivery-unknown invite cannot be duplicated by another click. Failed/unknown outcomes use safe explicit retry/reconciliation semantics. Repeat after accepted creates the next sequence.
- No cancellation behavior is required because Rufous currently has no trip-plan deletion/cancellation workflow. A later deletion feature must specify cancellation before changing that lifecycle.

## Alternatives considered

- Creating a new event on every click was rejected because it produces duplicates.
- Direct browser SMTP/calendar APIs were rejected because credentials and side effects belong server-side.
- Fire-and-forget synchronous email without durable state was rejected because ambiguous outcomes and retries already have a hardened outbox contract.

## Consequences

The existing calendar/outbox model must support a bounded trip-plan event kind without weakening watch-event relationships. API/UI status and reconciliation must distinguish trip invites from bird alerts while exposing no recipient or transport configuration.
