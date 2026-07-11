Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Relates-To: .10x/tickets/done/2026-07-10-implement-proton-bridge-alert-delivery-and-operations.md, .10x/specs/bird-alert-calendar-and-smtp-delivery.md

# Proton Bridge alert delivery and operations

## What was observed

Databox now has an explicit generic-SMTP sender and local operator surface over the durable bird-alert outbox.

- Every SMTP configuration value is a server-only `SecretStr`. Validation requires enabled delivery, exact STARTTLS mode, numeric `127.0.0.1` or `::1`, a canonical numeric port, organizer equal to authenticated username, bounded email syntax, and a CA file containing exactly one public certificate and no private key.
- TLS uses a new client-only `SSLContext`, required certificate verification, hostname checking, and only the configured exported public certificate as its loaded trust anchor. The transport performs EHLO, STARTTLS, EHLO, Bridge-generated authentication, then message transmission; it never falls back to plaintext or SMTP-over-SSL.
- One explicit sender invocation atomically claims at most one due canonical outbox row. Connection/TLS/auth preparation occurs before `send_started`; the durable send boundary is recorded immediately before `send_message`. Explicit SMTP acceptance alone records accepted.
- Known pre-acceptance transient failures retry after exactly 1, 5, and 15 minutes and fail after the third retry. Explicit permanent rejection fails immediately. Disconnect, timeout, or unclassified failure once message transmission may have begun becomes `delivery_unknown` and is never automatically claimed again.
- Manual unknown-as-delivered reconciliation is idempotent and validates the unknown row's preserved canonical payload/hash plus exact species/watch/activation/UID/sequence/morning/horizon/public-destination/source-report linkage before mutation. Accepted REQUEST snapshots persist all facts needed for cancellation. A newer same-UID event keeps its sequence/status while receiving non-regressing last-accepted metadata; later pause uses the accepted snapshot. A suppressed/inactive current event immediately receives a coherent greater-sequence CANCEL so an ambiguously accepted invitation cannot remain orphaned.
- Active coherent unknown/failed rows may retry at a greater sequence. Suppressed/inactive unknown rows expose only mark-delivered and terminal mark-not-delivered; the latter creates no impossible retry. API `allowed_actions` and `can_retry` are derived server-side and strictly validated by the browser before rendering controls.
- Safe API/UI status exposes only opaque outbox/taxon/method/sequence/state/attempt/time/reason fields. It never returns payload/MIME, locations, SMTP configuration, addresses, certificate data, or claim tokens. Native confirmations guard mark-delivered and mark-not-delivered/retry operations.
- Ninety-day cleanup moves terminal identity/hash state into the minimal dedupe ledger, removes payload/attempt history, and retains unresolved unknown rows until reconciliation.
- App startup, GETs, watch changes, and tests never invoke the sender. Sending exists only in the explicit `scripts/deliver_bird_alerts.py` command. Verification exists only in the explicit verification command and has a durable one-attempt-per-kind ledger.

## Fake transport, state, API, and regression verification

```text
uv run --no-sync pytest --no-cov -q \
  tests/test_bird_alert_delivery.py tests/test_bird_alert_outbox.py \
  tests/test_settings.py tests/test_audit_app_bundle.py tests/test_api.py
64 passed

uv run --no-sync pytest -q --record-mode=none --block-network
408 passed; 3 snapshots passed; coverage 86.26%

uv run --no-sync mypy packages/
Success: no issues found in 89 source files

task app:check
125 browser tests passed; TypeScript and Vite build passed
bundle audit passed: 12 server-only names and 10 configured values absent
```

Focused tests cover loopback/STARTTLS/public-certificate/organizer validation, redacted repr, exact CA loading, SMTP command ordering, missing-STARTTLS permanent zero-retry failure, explicit acceptance, 1/5/15 retry timing, immediate permanent failure, ambiguous post-send state, no automatic unknown resend, canonical/report tamper rollback, concurrent/replayed reconciliation, unknown sequence 0 followed by pending sequence 1 and pause, send-started suppression followed by delivered reconciliation/cancellation, inactive terminal no-retry resolution, exact server/browser actions, new-sequence retry, already-advanced event release, 90-day cleanup, safe read-only GET, confirmation, UI operations, and bundle rejection of SMTP names/values.

## Final automatic-acceptance repair

Automatic SMTP acceptance and manual mark-delivered now call one shared non-regressing accepted-REQUEST propagation path. It validates and persists the canonical accepted snapshot, advances last-accepted sequence/horizon/time only when newer, retains all source-report/watch/activation/public-location facts in the accepted snapshot, and changes current event status only when accepting that exact current pending sequence. A current greater sequence and its status/payload remain untouched.

An end-to-end regression starts sequence 0 sending, enqueues a different-location pending sequence 1, records automatic acceptance for sequence 0, replays that acceptance idempotently, then deletes/pauses the watch. The resulting sequence 2 CANCEL uses sequence 0's accepted public destination and stable UID while sequence 1 was never regressed. Separate automatic-acceptance tests prove concurrent single effect, canonical tamper rollback, newer accepted snapshot precedence, and replay of older acceptance cannot overwrite the newer snapshot.

Ruff, Ruff format, MyPy, secret scan, hooks, and `git diff --check` passed. No cassette or source snapshot was recorded.

## Explicit live Bridge verification

The preflight was run first and passed numeric-loopback, exact-public-certificate TLS hostname validation, STARTTLS, and Bridge-generated authentication without sending a message. No configuration value was printed or persisted.

The user's already-authorized bounded live checks were then invoked exactly once each:

```text
test_email: accepted by local SMTP Bridge
test_invitation: accepted by local SMTP Bridge
```

The durable verification ledger contains exactly those two kinds, each in accepted state with the safe reason `smtp_bridge_accepted`; it contains no SMTP value, address, port, certificate path/content, credential, or message body. These observations prove local Bridge acceptance only. They do not prove recipient inbox delivery or calendar rendering, and neither check will be resent by the verification command.

## What this supports

The ticket's server-only configuration, exact-CA STARTTLS transport, atomic claims, explicit acceptance, bounded retry, permanent/unknown classification, manual operations, retention, redaction, no-implicit-send, fake transport, complete regression, and bounded live-acceptance criteria have executable evidence.

## Limits

- SMTP acceptance is not proof of inbox receipt or calendar rendering.
- Proton Bridge must already be running with current local credentials/certificate for future explicit delivery commands.
- Final independent adversarial review passed and is recorded at `.10x/reviews/2026-07-11-proton-bridge-alert-delivery-and-operations-review.md`.
