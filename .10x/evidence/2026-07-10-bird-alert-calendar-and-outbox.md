Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Relates-To: .10x/tickets/done/2026-07-10-build-bird-alert-calendar-and-outbox.md, .10x/specs/bird-alert-calendar-and-smtp-delivery.md

# Bird-alert calendar and durable outbox

## What was observed

The evaluator's stable-UID event intent now atomically enqueues one canonical outbox row for each sendable REQUEST or CANCEL. Identity is deterministic over event UID, sequence, and method; replay with a later invocation time returns the same row and verifies the same canonical payload hash. A newer sequence supersedes only older unsent rows, while an already-started older send can finish without overwriting the newer event intent.

Persisted canonical payload JSON contains bounded event/species identity, public confirmed destination identity, derived distance/evidence, UTC morning window, five-day horizon, UID/sequence/method, and deterministic timestamps. Enqueue fails closed unless status/method is exactly `pending_request`/`REQUEST` or `pending_cancel`/`CANCEL`. Before hashing, the event is checked against its exact authoritative source report for report ID, species, watch ID, activation generation, start/end/horizon, public location ID/name/coordinates, and report lifecycle. UID/sequence are copied directly from the same event row into the canonical payload/outbox identity. It deliberately contains no organizer, attendee/recipient, SMTP address/host/port/user/password, certificate path/content, MIME bytes, arbitrary GLM prose, personal watch center, remote asset, or full message body. SHA-256 covers the exact canonical JSON.

Pure standard-library builders accept organizer and attendee only in memory and produce:

- RFC 5545 VCALENDAR/VEVENT with CRLF, 75-octet folding, UTC DTSTART/DTEND/DTSTAMP, stable UID, monotonic SEQUENCE, ORGANIZER, ATTENDEE, SUMMARY, bounded deterministic DESCRIPTION, public LOCATION/GEO, and Arizona timezone declaration;
- REQUEST/CONFIRMED for create/update and RFC 5546 CANCEL/CANCELLED for cancellation;
- deterministic multipart MIME with text alternative plus `text/calendar; method=...`, reserved deterministic Message-ID/boundary, and no binary/remote content.

Header/calendar injection, control characters, invalid addresses, inconsistent windows/horizon, missing REQUEST evidence, invalid coordinates, oversized IDs/text, and payloads over 32 KiB fail before construction/persistence.

## State and transaction contract

Runtime-owned tables are `birding_alerts.alert_outbox`, `outbox_attempts`, and `outbox_dedupe`.

| From | Operation | To | Safety property |
|---|---|---|---|
| event pending REQUEST/CANCEL | atomic enqueue | `pending` | unique UID/sequence/method and payload hash |
| `pending` / due `retry_wait` | atomic claim | `claimed` | one opaque lease token; unresolved unknown blocks later UID claims |
| expired `claimed`, send not started | recovery | `pending` | safely reclaimable; append recovery fact |
| expired `claimed`, send started | recovery | `delivery_unknown` | never auto-reclaimed/resendable |
| `claimed`, send not started | start | `claimed` | increments attempt once; append send-start fact |
| started `claimed` | accepted | `accepted` | append fact and atomically advance matching event accepted/cancelled state |
| started `claimed` | retry/failed/unknown | `retry_wait` / `failed` / `delivery_unknown` | explicit valid transition only; scheduler policy remains downstream |
| unsent older sequence | newer intent | `superseded` | cannot be claimed |
| unsent REQUEST | watch suppression/expiry | `cancelled`, payload `{}` | structurally non-sendable |
| started REQUEST | suppression/expiry | `delivery_unknown`, payload `{}` | ambiguity retained, never auto-sent |

Invalid/double starts, missing/expired claim tokens, outcome before send-start, inconsistent retry scheduling, invalid reasons, payload/hash mismatch, status/method mismatch, missing/cross-linked reports, and any report/event identity/window/location mismatch fail transactionally without an outbox row. Event/report/outbox creation rolls back together. Concurrent worker claims result in exactly one lease. Pause/delete suppression and natural expiry also suppress the matching outbox in the same event transaction. An accepted cancellation clears event payload but retains minimal stable UID/sequence identity.

Pre-release `event_intents` tables lacking `source_report_id`, public `location_id`, or the new pending-state constraints are rebuilt transactionally into the constrained schema. REQUEST rows backfill only through their exact report ID. A pending cancellation whose source report/location identity cannot be recovered fails the migration and rolls back the table replacement; it is never guessed or enqueued.

Resolved accepted/failed/cancelled/superseded rows and attempts are removed after 90 days only after copying minimal UID/sequence/method/hash identity to `outbox_dedupe`. Unresolved `delivery_unknown` remains. Replay cannot recreate a purged sequence.

## Procedure and results

### Focused calendar/outbox and evaluator integration

```text
uv run --no-sync pytest --no-cov -q \
  tests/test_bird_alert_outbox.py \
  tests/test_watched_bird_evaluator.py
41 passed
```

Twenty-eight calendar/outbox cases cover REQUEST/CANCEL semantics, MIME parsing and byte determinism, 75-octet folding, injection/bounds, payload privacy/hash/replay across different invocation times, exact five-day REQUEST horizon, both invalid status/method pairs, missing/cross-linked reports, species/watch/generation/window/horizon/public-location identity/name/coordinate mismatches, valid REQUEST/CANCEL coherence, atomic pre-release schema backfill and rollback for unrecoverable cancellation rows, update/cancel supersession, accepted event transitions, event+outbox rollback, invalid/double transitions, pre/post-send lease expiry, unknown blocking, natural expiry without CANCEL delivery, due retry state, suppression before/after send start, simultaneous two-worker claims, in-flight older acceptance versus a newer sequence, retention/dedupe, and zero socket calls. Thirteen evaluator tests prove atomic creation, pending suppression, race rollback, cancellation enqueue, and natural-expiry suppression in the real event lifecycle.

### Complete repository gates

```text
uv run --no-sync pytest -q --record-mode=none --block-network
390 passed; 3 snapshots passed; coverage 87.00%

uv run --no-sync mypy packages/
87 source files passed

task app:check
122 frontend tests, TypeScript, production build, and bundle audit passed
```

Ruff check/format, secret scan, pre-commit hooks, and `git diff --check` passed. No files were staged. No live response, SMTP connection, or email was created.

## What this supports

- Stable UID/sequence REQUEST/CANCEL intent is transactionally coupled to a unique canonical outbox record.
- Builders are deterministic, bounded, standards-shaped, injection-safe, and free of persisted server/email configuration.
- Claims, leases, attempts, recovery, outcomes, supersession, suppression, rollback, concurrency, retention, and minimal dedupe have executable evidence.
- Startup, GETs, watch mutation, and this implementation's tests perform no SMTP/network delivery.

## Limits

- The next ticket owns loopback/CA/STARTTLS/auth validation, SMTP protocol, exact 1/5/15-minute retry scheduling, delivery classification, operator reconciliation API/UI, and bounded live Bridge verification.
- SMTP exactly-once and inbox/calendar rendering are not claimed.
- Final independent adversarial review passed and is recorded at `.10x/reviews/2026-07-11-bird-alert-calendar-and-outbox-review.md`.
