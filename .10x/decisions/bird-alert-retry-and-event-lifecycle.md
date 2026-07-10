Status: active
Created: 2026-07-10
Updated: 2026-07-10

# Bird alert retry and calendar-event lifecycle

## Context

Existing decisions establish post-refresh watched-bird matching, one updateable five-day event per taxon, generic SMTP through Proton Mail Bridge, and ambiguous-outcome safety. Exact morning selection, event cancellation, retry intervals, unknown-outcome operations, and retention remained unresolved.

## Decision

- Morning selection is freshness-first: choose the earliest available sunrise-centered two-hour window after a qualifying match. Weather may break ties between equally fresh candidate windows but must not postpone an outing merely for better weather.
- A later qualifying match updates the same stable iCalendar UID, increments `SEQUENCE`, and slides the five-day event/report window.
- Pausing or deleting a watch sends an RFC 5546 cancellation only when an unexpired event was previously accepted by SMTP. Expired events end naturally; no expiry cancellation is sent.
- Explicit transient failures known to occur before SMTP acceptance retry after 1, 5, and 15 minutes. After those retries the row becomes failed and requires manual action.
- An ambiguous acceptance outcome becomes `delivery_unknown` and is never automatically resent. The operator can mark it delivered or mark it not delivered and request a retry; the latter uses the stable UID and incremented sequence.
- Personal collection state persists until explicit deletion. Resolved alert match/report/event/outbox history is retained for 90 days. Unresolved `delivery_unknown` rows are retained until manually resolved, then become eligible for the 90-day retention rule.

## Alternatives considered

- Weather-first scheduling was rejected because alert evidence loses value with age.
- Never cancelling on watch removal was rejected because it leaves an event the user explicitly disabled.
- Cancelling naturally expired events adds noise without changing calendar truth.
- Automatic resend of ambiguous outcomes was rejected because SMTP cannot provide exactly-once delivery.
- Slower, single, or unbounded retries were rejected in favor of a small deterministic schedule.

## Consequences

The outbox needs explicit claim/attempt/accepted/failed/unknown/reconciled states, scheduled retry timestamps, immutable attempt records, operator reconciliation actions, stable UID/sequence state, and retention cleanup that excludes unresolved unknown outcomes. SMTP acceptance proves only Bridge acceptance, not inbox or calendar rendering.
