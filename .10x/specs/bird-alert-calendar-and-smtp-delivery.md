Status: active
Created: 2026-07-10
Updated: 2026-07-10

# Bird alert calendar and SMTP delivery

## Purpose and scope

This specification governs durable outbox state, RFC-compliant iCalendar email construction, local Proton Mail Bridge SMTP transport, retries, reconciliation, cancellation, retention, and operator visibility. Matching/report generation is upstream and performs no SMTP side effect.

## Server-only configuration

Configuration MUST remain in local environment state and MUST include SMTP host, port, username/organizer, secret password, recipient, and exact exported Bridge public-certificate CA path. Values MUST never appear in repr, logs, traces, API responses, frontend bundles, records, fixtures, or committed files.

The transport MUST require:

- numeric loopback host only (`127.0.0.1` or `::1`), rejecting names and non-loopback addresses;
- STARTTLS before authentication/message transmission;
- normal hostname verification against the Bridge certificate and trust anchored only by the configured exported public certificate;
- Bridge-generated username/password, never Proton account credentials;
- organizer equal to authenticated Proton address and one configured recipient.

No disabled TLS verification, opportunistic plaintext fallback, private key, public SMTP service, OAuth calendar API, or provider-specific calendar dependency is allowed.

## Calendar contract

Each watch/taxon has one stable deterministic UID scoped to this local Databox installation and taxon. DTSTART/DTEND represent the selected Arizona-local two-hour morning; the enclosing report/event horizon lasts five days. Messages MUST include standards-compliant VCALENDAR/VEVENT fields, timezone-safe timestamps, DTSTAMP, ORGANIZER, ATTENDEE, SUMMARY, DESCRIPTION from persisted bounded facts, LOCATION from the confirmed public destination, UID, and monotonically increasing SEQUENCE.

Create/update uses `METHOD:REQUEST`. A later match slides the event and increments sequence. Pausing/deleting a watch with an accepted unexpired event produces `METHOD:CANCEL`, same UID, greater sequence, and cancelled status. Natural expiry produces no cancellation.

MIME MUST be a calendar invitation/update with a concise text alternative. No private/raw evidence, credential, arbitrary GLM text outside the validated report, tracking pixel, remote asset, or attachment binary is allowed.

## Durable outbox

Outbox creation is transactionally coupled to persisted event intent, not SMTP. Rows include immutable ID, event/watch/taxon IDs, UID/sequence/method, canonical payload hash, state, next-attempt time, claim token/expiry, attempt counters, timestamps, and safe terminal reason. Attempt records are append-only and contain no secret or full message body.

Allowed states are pending, claimed, accepted, retry_wait, failed, delivery_unknown, cancelled/superseded where applicable. Atomic claim prevents concurrent senders from sending the same row. Expired claims can be reclaimed safely only when no SMTP acceptance attempt began; ambiguous post-send outcomes become unknown.

## Delivery and retry

The worker MUST send only persisted canonical payloads. It records accepted only after explicit SMTP acceptance response. Explicit transient failures known to occur before acceptance retry after 1, 5, and 15 minutes, at most three retries after the initial attempt. Permanent failures become failed immediately. No timeout/retry policy may reinterpret an ambiguous outcome as pre-acceptance.

Any connection loss/timeout or process failure after message transmission may have begun but before acceptance is durably known MUST become `delivery_unknown`. It is never auto-resent.

## Reconciliation and operations

The local operator UI/API MUST display safe outbox/event/attempt status and provide authenticated-by-local-access actions:

- mark unknown as delivered, preserving the accepted event state;
- mark unknown as not delivered and enqueue one manual retry using the same UID and incremented sequence;
- manually retry failed rows;
- inspect sanitized failure category/timestamps.

Actions require explicit confirmation and are idempotent. They MUST NOT expose recipient, organizer, SMTP host/port/user/password, certificate path/content, or raw MIME. A test email and one test invitation may be sent only through explicit verification commands/actions and only within the user's existing bounded authorization; production code/tests MUST not send them implicitly.

## Trigger and concurrency

Delivery runs only after durable outbox intent exists and while no Quack/SQLMesh writer owns the database. It may be a separate Dagster job/sensor or explicit operator command, but must use atomic claims and one local sender. GET endpoints never send. Application startup never sends.

## Retention

Accepted, failed, cancelled, superseded, and manually resolved delivery history is retained for 90 days, then may be purged with payloads/attempt details. Unresolved `delivery_unknown` rows persist until reconciliation, after which the 90-day clock begins. Minimal event UID/sequence and deduplication state persists as long as needed to prevent stale replay.

## Acceptance scenarios

- Loopback Bridge with exact CA, STARTTLS, and generated credentials accepts a bounded test message without any secret in logs/traces/bundle.
- Request/update/cancel share UID and strictly increase sequence; expiry sends nothing.
- Pre-acceptance transient failures schedule exactly 1/5/15-minute retries; permanent failure does not retry.
- Ambiguous outcome becomes unknown and never auto-sends; manual delivered/not-delivered actions reconcile idempotently.
- Concurrent workers claim one row once; crashed pre-send claims recover without duplicate intent.
- GET/startup/watch creation cause zero SMTP calls.
- Ninety-day cleanup retains unresolved unknown and minimal dedupe/event state.

## Explicit exclusions

No Gmail/Google Calendar API, remote SMTP provider, exact inbox/calendar-rendering guarantee, automatic ambiguous resend, TLS bypass, account password, private key, credential display, bulk notifications, or alerts from non-eBird evidence.
