Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-remove-wishlist-and-consolidate-watches.md, .10x/specs/personal-bird-collection.md

# Wishlist removal and watch consolidation

## What was observed

Wishlist is absent from active runtime behavior. The personal schema initializes observations, watches, and watch-cancellation requests only. No wishlist service, typed response, route registration, collection-state field, browser client/type, My Birds tab, profile mutation, or active user-facing documentation remains.

The three former HTTP paths are unregistered and return 404. Observation/life-list and watch state remain independent, including stale identity, hybrid, transaction, mutation-lock, pause/resume, cancellation-handoff, and profile behavior.

An explicit migration provides aggregate-only inspection and transactional apply. It records whether the table existed, the retired-row count, and observation/watch counts before and after. Apply drops only `birding_personal.wishlist`, checks neighboring counts, commits atomically, and never creates or changes a watch. An injected failure rolls the drop and forbidden neighboring mutation back.

## Test repair

Two initial My Birds failures were stale fixture assumptions rather than product defects:

- The safe POST-error test matched its generic GET `/api/observations` fixture before the POST branch. Ordering the exact POST fixture first restores the intended privacy/error assertion.
- Cross-route mutation serialization formerly began with a wishlist mutation. It now begins with a profile observation mutation. The navigated form correctly labels its globally busy submit button `Saving…`; the test supplies the otherwise-required date, proves the second action remains disabled and causes no second request, then reopens the form after successful refresh and proves the lock is released.

This preserves and strengthens the original safe-error and cross-component global serialization guarantees.

## Live migration procedure

Preflight was read-only:

```text
uv run --no-sync python scripts/remove_wishlist_storage.py --inspect
{"observation_rows_after": 0, "observation_rows_before": 0, "table_existed": true, "watch_rows_after": 0, "watch_rows_before": 0, "wishlist_rows_removed": 0}
```

Explicit apply, read-only inspection, and idempotent rerun:

```text
uv run --no-sync python scripts/remove_wishlist_storage.py --apply
{"observation_rows_after": 0, "observation_rows_before": 0, "table_existed": true, "watch_rows_after": 0, "watch_rows_before": 0, "wishlist_rows_removed": 0}

uv run --no-sync python scripts/remove_wishlist_storage.py --inspect
{"observation_rows_after": 0, "observation_rows_before": 0, "table_existed": false, "watch_rows_after": 0, "watch_rows_before": 0, "wishlist_rows_removed": 0}

uv run --no-sync python scripts/remove_wishlist_storage.py --apply
{"observation_rows_after": 0, "observation_rows_before": 0, "table_existed": false, "watch_rows_after": 0, "watch_rows_before": 0, "wishlist_rows_removed": 0}
```

Post-apply read-only reconciliation found exactly these `birding_personal` tables:

```text
observations
watch_cancellation_requests
watches
observations_rows=0
watches_rows=0
```

No row was available to convert, no watch was created, and the second apply was a no-op.

## Automated validation

```text
cd app && npm test -- --run src/MyBirds.test.tsx
16 passed

uv run --no-sync pytest --no-cov -q \
  tests/test_remove_wishlist.py tests/test_personal_collection_api.py \
  tests/test_bird_catalog_api.py tests/test_api.py
47 passed

task app:check
199 tests passed
TypeScript passed
Vite production build passed
bundle audit passed: 12 names and 10 configured values absent

uv run --no-sync pytest -q --record-mode=none --block-network
417 passed; 3 snapshots passed; coverage 86.43%

uv run --no-sync mypy packages/
Success: 91 source files

uv run --no-sync python scripts/check_secrets.py .
passed

.venv/bin/pre-commit run --all-files
all hooks passed

uv run --no-sync python scripts/check_source_layout.py
7/7 sources passed

uv run --no-sync python scripts/generate_docs.py --check
20 dictionary files in sync

uv run --no-sync mkdocs build --strict
passed

git diff --check
passed
```

A bounded absence scan finds the retired term only in the explicit migration implementation/script, migration tests, and API 404 regression assertions. It is absent from active package runtime collection modules, browser source, active user-facing docs, and README.

## What this supports

- Wishlist is fully removed rather than hidden.
- Watch is the only prospective-interest state.
- No implicit wishlist-to-watch conversion occurred.
- Live zero-row removal, idempotency, rollback, neighboring-state preservation, route absence, UI/API absence, privacy, accessibility regression, and complete offline suites have executable evidence.

## Limits

Independent adversarial review passed and is recorded at `.10x/reviews/2026-07-11-wishlist-removal-and-watch-consolidation-review.md`.
