Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-12-warehouse-repository-cleanup.md
Depends-On: None

# Reconcile bird-alert delivery action contract

## Context

Aggregate warehouse-cleanup verification found a reproducible failure in the
unchanged committed Rufous delivery surface:

`tests/test_bird_alert_delivery.py::test_safe_operator_api_is_read_only_on_get_and_confirms_actions`

The API returns `mark_not_delivered` while this assertion expects
`mark_not_delivered_and_retry`. Other assertions in the same test module expect
`mark_not_delivered` for terminal/inactive delivery state. The warehouse cleanup
diff does not touch the API or test.

## Scope

Reconcile the intended operator action for the exact delivery state exercised by
the failing test against active bird-alert delivery specifications/decisions,
then make the smallest authorized implementation or test correction and rerun
the full suite.

## Acceptance criteria

- Identify the exact delivery state and governing semantic authority.
- Resolve whether the allowed action is `mark_not_delivered`,
  `mark_not_delivered_and_retry`, or state-dependent without guessing.
- Preserve explicit-confirmation, retry, idempotency, SMTP, and privacy safety
  behavior.
- Focused delivery tests and the full Python suite pass.
- Record evidence and independent correctness/privacy review before closure.

## Explicit exclusions

- Any warehouse-cleanup widening
- Live email delivery, provider calls, refresh, or warehouse mutation

## Progress and notes

- 2026-07-12: Opened from reproducible aggregate verification failure. Full
  suite: 914 passed, one failed at 87.47% coverage; focused rerun reproduces the
  same mismatch. No cleanup file changes this surface.
- 2026-07-12: Reconciliation found runtime behavior matches the active state-dependent specification. The test's fixed `NOW` event horizon expired relative to API `datetime.now(UTC)` as wall-clock time advanced. Authorized repair is test-only time freezing around the existing active/inactive assertions.
- 2026-07-12: Added only `@pytest.mark.time_machine(NOW.isoformat())` to the existing API test; active/inactive assertions and all runtime code remain unchanged. Focused delivery tests passed 14/14. Full recording-disabled/network-blocked telemetry-disabled suite passed 915 tests, seven snapshots, and 87.75% coverage. Ruff, format, secret, diff, staging, and protected hashes passed. Evidence: `.10x/evidence/2026-07-12-bird-alert-delivery-action-contract-reconciliation.md`.
- 2026-07-12: Independent correctness/privacy review `.10x/reviews/2026-07-12-bird-alert-delivery-action-contract-review.md` passed every criterion. Retrospective: time-sensitive state tests must freeze wall clock at the asserted lifecycle boundary; production state derivation remains authoritative. Ticket closed.

## Blockers

None.

## References

- `.10x/evidence/2026-07-12-warehouse-repository-cleanup-aggregate-verification.md`
- `.10x/tickets/done/2026-07-12-verify-warehouse-repository-cleanup.md`
