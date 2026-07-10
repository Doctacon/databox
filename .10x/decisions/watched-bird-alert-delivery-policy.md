Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Define watched-bird alert matching and delivery policy

## Context

Watched-bird alerts are an external side effect: they create and email calendar invitations based on third-party sighting data. Duplicate, stale, private, or weak observations could send the user to the wrong place or create repeated calendar events. Databox is local-only, and its daily refresh runs only while the Dagster daemon and machine are running.

The source and baseline eligibility rules are governed by `.10x/decisions/local-single-user-birding-pokedex-expansion.md` and `.10x/decisions/arizona-catalog-observation-and-watch-match-boundaries.md`.

## Decision

1. Each active watch will store its own Arizona center and maximum radius; there is no required global home location.
2. A first match MUST have been observed after the watch became active and no more than 48 hours before evaluation.
3. Only valid, reviewed/confirmed, non-private eBird observations with usable public destination data are eligible.
4. Matching will run only after the scheduled parallel Quack refresh and SQLMesh transformation complete successfully. Individual source jobs, GET requests, app startup, failed/partial refreshes, and stale warehouse reads MUST NOT send alerts.
5. Eligible observations will be clustered by public location. The best location will be chosen by most independent eligible submissions, then newest observation, shortest distance from the watch center, and a stable source-key tie-break.
6. Databox will maintain at most one active five-day calendar event per watched taxon. Stronger/newer eligible evidence MAY update that event using the same stable iCalendar UID and an incremented sequence rather than creating another invitation.
7. The event will represent a deterministic two-hour morning outing within the next five days and explain why its date/time and location were selected.
8. A fresh report MAY use only Cloudflare Workers AI model `@cf/zai-org/glm-5.2` under the existing strict grounding/no-fallback contract. If fresh model synthesis is unavailable, Databox will still send a deterministic report assembled from persisted species-profile facts, the selected sighting cluster, location, weather, and explicit model-unavailable caveat. This is not an alternate model or parser fallback.
9. Calendar delivery will use a durable outbox and standard iCalendar email invitation over configurable SMTP. Explicit transient failures before server acceptance may be retried at most three times. An ambiguous outcome after possible acceptance MUST become `delivery_unknown` and MUST NOT be automatically resent.
10. Recipient and SMTP credentials/configuration remain server-side and MUST NOT appear in browser assets, traces, logs, persisted report payloads, or committed files.

## State and side-effect inventory

The implementation will need explicit durable states for:

- watch: active or paused,
- match: eligible, superseded, or rejected with safe reason,
- report: ready, deterministic-degraded, or failed,
- outbox: pending, sending, accepted, transient-failure, permanent-failure, or delivery-unknown,
- calendar event: active, updated, expired, or cancelled.

Every transition must be idempotent against watch ID, conformed taxon key, source submission keys, stable calendar UID, and event sequence.

## Alternatives considered

- **Statewide matching:** rejected in favor of per-watch travel bounds.
- **24-hour freshness:** rejected because the daily refresh could miss eligible sightings at its boundary.
- **Seven-day freshness:** rejected because it weakens evidence that the bird remains near the location.
- **One email per source row/location:** rejected because overlapping refreshes and repeated reports would create spam.
- **Closest/newest record only:** rejected in favor of independent confirmation clusters before recency and distance tie-breaks.
- **App-startup or GET-side evaluation:** rejected because alert state must follow a successful transformed refresh and remain network/write-free on reads.
- **Block all delivery when GLM is unavailable:** rejected; persisted deterministic facts can produce an honest degraded report without another model.
- **Direct Google Calendar API:** rejected in favor of open iCalendar/SMTP.
- **Unbounded retry:** rejected because ambiguous SMTP outcomes can duplicate invitations.

## Consequences

- The product must disclose that monitoring occurs only while the local machine and Dagster scheduler run.
- A stable calendar UID/sequence and durable outbox are mandatory; exactly-once SMTP delivery cannot be claimed.
- The exact morning-window scoring, retry intervals, expiration/cancellation behavior, retention, SMTP operational setup, and persisted species-profile source contract remain to be specified before implementation.
