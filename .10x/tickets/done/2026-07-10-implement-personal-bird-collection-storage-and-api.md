Status: done
Created: 2026-07-10
Updated: 2026-07-10
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/done/2026-07-09-build-arizona-bird-catalog-and-profile.md

# Implement personal bird collection storage and API

## Scope

Implement the runtime DuckDB schema, transactional service, and typed FastAPI endpoints governed by `.10x/specs/personal-bird-collection.md` for observations, derived life list, wishlist, watches, and per-species collection state.

Validate exact current catalog identity, Arizona watch centers, 1–300-mile radius, bounded text/date inputs, stale catalog references, mutation serialization, atomic edits/hard deletes, independent state, activation/resume boundaries, and safe busy/conflict/not-found errors. Reads remain network-free; mutations cause no matching, weather, model, calendar, or SMTP side effect.

## Acceptance criteria

- Physical runtime tables, constraints/indexes, timestamps, and transactions implement the active data model without SQLMesh ownership.
- Observation create/edit/hard-delete derives correct life-list counts and first/latest dates; IDs/created timestamps remain stable.
- Wishlist and watch mutations are idempotent and independent from observed state.
- Watch create/replace/pause/resume/delete preserves per-watch center/radius and activation boundaries without triggering alerts.
- Typed APIs reject extra/invalid data, stale/missing identities render safely, concurrent/busy failures are safe, and no private/credential value leaks.
- Focused unit/API tests cover rollback, idempotency, invalid catalog/date/location/radius, hybrid, stale identity, hard-delete confirmation contract, and zero external calls.

## Explicit exclusions

No React UI, target planning, match evaluation, report generation, calendar intent, SMTP, life-list import, attachments, or remote sync.

## Evidence expectations

Record schema shape, transaction/rollback behavior, derived-state cases, API response contracts, mutation independence, no-network/no-side-effect checks, privacy/secret scans, and focused/full regression results.

## Progress and notes

- 2026-07-10: Ticket derived from user-ratified edit/hard-delete, explicit-retention, independent-state, and per-watch activation contracts.
- 2026-07-10: Implemented runtime-owned observations/wishlist/watches schema, transactional services, and typed FastAPI endpoints with exact catalog validation, stale identity reads, derived life list, idempotent independent state, Arizona watch centers, 1–300-mile radius, pause/resume activation boundaries, confirmed hard deletion, and safe busy/error behavior.
- 2026-07-10: Review repair rejects stale resume while allowing stale pause/delete, makes identical replacement idempotent, and transactionally persists deduplicated non-private pause/delete cancellation-request tombstones for conditional downstream consumption. These are not event/outbox/SMTP intents and cause no side effect.
- 2026-07-10: Final repair replaced timestamp activation identity with private stable watch IDs and opaque activation generations, guarantees strictly advancing UTC `updated_at` under equal/regressing clocks, and adds crash-resumable transactional legacy migration without changing API shape. The migration now preserves distinct older/orphan activation transitions, maps only the newest legacy request to the current semantic tuple and deterministic request ID, dedupes an identical subsequent request, handles primary-key conflicts transactionally, and resumes after rollback. Seventeen focused tests plus catalog/planner API regression passed 44/44; complete network-disabled Python suite passed 324/324 with three snapshots and 86.30% coverage; Ruff, formatting, MyPy (82 files), secret scan, hooks, and diff checks passed. Evidence: `.10x/evidence/2026-07-10-personal-bird-collection-storage-and-api.md`.
- 2026-07-10: Remaining acceptance repair introduced a narrow internal storage-migration error for intentional legacy identity conflicts and catches only that error at observation, observation-delete, wishlist, and watch mutation entry points. Current-watch and orphan conflict tests prove exact bounded `database_unavailable` responses, no internal values, transactional rollback, and repeat behavior without swallowing validation/programmer exceptions.
- 2026-07-10: Final independent review passed after verifying the complete repaired lifecycle. Review: `.10x/reviews/2026-07-10-personal-bird-collection-storage-and-api-review.md`.
- 2026-07-10: Retrospective preserved activation-generation, monotonic mutation timestamp, and side-effect-free cancellation-handoff invariants directly in the active specification and adversarial migration tests; no additional skill record is needed.

## Blockers

None.
