Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Trip-plan calendar invitations

## Purpose and scope

This specification governs explicit calendar invitations for persisted Trip Planner artifacts. It reuses the hardened calendar/outbox/SMTP transport contract while keeping trip-plan and watched-bird event identities and relational rules distinct.

## Eligibility and canonical facts

Only one complete persisted trip plan with stable ID, normalized Arizona location, start/end window, field-plan text, recommendations, weather status, and caveats may create an invite. Missing, malformed, tainted, or deleted plans fail closed.

Canonical payload fields:

- event kind `trip_plan`;
- deterministic installation+trip-plan UID;
- monotonically increasing sequence;
- `METHOD:REQUEST`;
- Arizona timezone-safe DTSTART/DTEND equal to persisted plan window;
- LOCATION equal to persisted normalized location;
- SUMMARY `Rufous trip — <bounded location>`;
- deterministic bounded DESCRIPTION containing field-plan text, ordered target common names, weather availability, evidence caveats, and a local-product caveat;
- exact source plan ID and canonical payload hash.

No arbitrary evidence payload, model trace, private source location, recipient, credential, or media URL enters calendar text. RFC escaping/folding and injection guards from the existing builder remain mandatory.

## Durable state and sending

Trip invites MUST have dedicated event identity/state linked to the source plan and use the common durable outbox/attempt/accepted-snapshot transport mechanics. Watch IDs/activation generations MUST NOT be fabricated for trip events. The schema MUST use an explicit event-kind union or separate constrained tables so each kind validates only its authoritative relationship.

An explicit POST/action atomically creates or updates the event intent, enqueues canonical payload, claims/sends through configured Bridge, and returns safe delivery status. Repeated behavior:

- pending/claimed/retry-wait: return current status, no duplicate;
- delivery-unknown: require existing reconciliation, no auto-resend;
- accepted: enqueue same UID with sequence + 1 as an update;
- failed: explicit retry only if source plan remains coherent;
- superseded older attempts cannot regress a newer accepted snapshot.

Use existing numeric-loopback exact-CA STARTTLS, authentication, explicit acceptance, 1/5/15-minute retries, permanent/unknown classification, atomic claims, redaction, and 90-day resolved-history retention. GETs and plan creation never send.

## API and browser

Plan detail exposes typed invite status and allowed actions without recipient/transport fields. The plan result provides a **Send calendar invite** button with explicit confirmation. During send/reconcile it uses native busy/live status and disables duplicate actions. Accepted wording says “Accepted by local mail bridge,” not delivered to inbox/calendar.

Replay of a plan shows persisted status without sending. Safe failed/unknown states reuse explicit reconciliation controls and fixed client-owned errors. Direct/history/focus behavior remains intact.

## Acceptance scenarios

- First explicit send creates sequence 0 REQUEST and Bridge acceptance updates status.
- Repeated send after acceptance creates sequence 1 with same UID.
- Double-click/concurrent clients create one send intent.
- Unknown outcome cannot auto-resend; reconciliation is idempotent.
- A changed/missing plan or mismatched canonical payload rolls back with no outbox row.
- GET, startup, plan creation, and tests send nothing.
- Fake SMTP and one already-consumed live-verification authorization MUST NOT cause another live verification send; this feature is proven with fake transport unless separately reauthorized.

## Explicit exclusions

No event cancellation, plan deletion workflow, Google Calendar API, new recipient setting, browser SMTP, exact inbox guarantee, automatic unknown retry, attachment/media binary, or watched-event identity reuse.
