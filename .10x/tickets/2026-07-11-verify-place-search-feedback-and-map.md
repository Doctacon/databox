Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-upgrade-place-search-feedback-and-map.md
Depends-On: .10x/tickets/done/2026-07-11-add-observation-location-combobox.md, .10x/tickets/2026-07-11-auto-dismiss-rufous-success-messages.md, .10x/tickets/2026-07-11-repair-field-map-interaction-and-layout.md

# Verify place search, feedback, and Field Map repairs

## Scope

Aggregate verification for local place suggestions, structured observations, transient success feedback, and map interaction/layout.

## Acceptance criteria

- Full network-blocked Python/frontend/SQLMesh/Soda/type/build/bundle/docs/static/hooks pass with personal state/hash coherently preserved.
- Live Watson/local ranking, structured/free-text observation migration, all success timers, and map race/filter/selection/layout reconcile exactly.
- No personal leak, remote map request, new dataset/provider, background geocoding, or delivery/model side effect.
- Independent architecture, correctness, privacy/security, and UX/accessibility reviews pass; records/retrospectives cohere.

## Exclusions

No new feature, Overture/OSM ingestion, source refresh, live delivery/model/provider call, or unrelated repair.

## Evidence expectations

One aggregate evidence record plus independent reviews.

## Blockers

Depends on all implementation children.
