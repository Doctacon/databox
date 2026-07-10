Status: open
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

## Blockers

None.
