Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-reconcile-bird-alert-delivery-action-contract.md, .10x/specs/bird-alert-calendar-and-smtp-delivery.md, .10x/decisions/bird-alert-retry-and-event-lifecycle.md

# Bird-alert delivery action contract reconciliation

## What was observed

The failing API test used a fixed `NOW` of 2026-07-10 to construct an event whose
horizon ended five days later, but the API intentionally derives allowed actions
from the real current UTC time. When the wall clock advanced beyond that horizon,
the same fixture became inactive and correctly returned
`mark_not_delivered` rather than `mark_not_delivered_and_retry`.

The active specification requires state-dependent behavior:

- active coherent `delivery_unknown` → `mark_delivered` plus
  `mark_not_delivered_and_retry`, with `can_retry=true`;
- inactive/expired `delivery_unknown` → `mark_delivered` plus
  `mark_not_delivered`, with `can_retry=false`.

Runtime implementation in `delivery_allowed_actions` already matched that
contract. The failure was test-time drift, not a product defect.

## Repair

Added only `@pytest.mark.time_machine(NOW.isoformat())` to
`test_safe_operator_api_is_read_only_on_get_and_confirms_actions`. This uses the
existing pytest time-machine mechanism and freezes API wall-clock reads at the
fixture's established time. Existing active and inactive assertions remain
unchanged. No API, outbox, state, action, retry, SMTP, privacy, or persistence
code changed.

## Procedure and results

- `.venv/bin/pytest --no-cov -q tests/test_bird_alert_delivery.py` — **14 passed**.
- Full telemetry-disabled suite with replay tokens, `--record-mode=none`, and
  `--block-network` — **915 passed**, 28 warnings, seven snapshots, **87.75%
  coverage** against the 70% gate.
- Targeted Ruff check and format check — passed; one file already formatted.
- `.venv/bin/python scripts/check_secrets.py .` — passed.
- `git diff --check` — passed.
- `git diff --cached --name-only` — empty.
- Diff inspection — exactly one test decorator added.
- Shared warehouse SHA-256 remained
  `3f7ad93d93682d5012496599cdcab94b07526aa2b70e8d1ec7982f6ff55f25e4`.
- AVONET manifest SHA-256 remained
  `2995f2e8a37caa7ca2014bdc1acbd75d2b8a7a7067c89a380a8c910a3ad3bf97`.

## What this supports

This supports the ticket's intended semantic reconciliation, smallest test-only
repair, preservation of state-dependent retry/terminal actions, full-suite
behavior, privacy/secret safety, protected state, and empty staging.

## Limits

Tests use fake/in-memory/temporary delivery surfaces; no email was sent. No
provider request, source refresh, SQLMesh operation, shared warehouse access,
model call, application action, commit, or push occurred. Independent
correctness/privacy review and closure remain parent-owned.
