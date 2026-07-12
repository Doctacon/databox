Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-upgrade-map-catalog-and-refresh-controls.md
Depends-On: .10x/tickets/2026-07-11-build-local-refresh-runtime-api.md

# Add header source refresh control

## Scope

Add the confirmed background refresh button/status near `Local DuckDB · evidence-backed`, backed only by the typed refresh API.

## Acceptance criteria

- Accessible confirmation names external calls and warehouse mutation; cancel starts nothing.
- Confirm launches once, disables while active, polls bounded status, and shows phase/source progress.
- Temporary database-busy behavior is explained while the shell remains responsive.
- Success notice expires at exactly 3,000 ms while neutral last-refresh time may remain.
- Failure and safe log pointer persist; Retry requires a fresh confirmation and is never automatic.
- Direct/reload/restart, keyboard/focus, narrow layout, reduced motion, malformed responses, and cross-origin/error cases pass.

## Evidence expectations

Strict API validator tests, fake-timer lifecycle tests, DOM/accessibility/responsive tests, full frontend suite, TypeScript/build/bundle audit.

## Exclusions

No pipeline logic, arbitrary options, cancellation, automatic retry, live refresh, or secret/raw log rendering.

## Blockers

Depends on the refresh runtime/API child.

## Progress and notes

- 2026-07-11: Header placement and confirmed background lifecycle ratified by the user.
