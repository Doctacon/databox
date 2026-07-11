Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Catalog media and Watch-only collection

This decision supersedes only the wishlist portions of `.10x/decisions/personal-collection-and-target-planning-lifecycle.md`; its observation, retention, and target-planning decisions remain active.

## Context

Arizona Birds currently exposes modeled names and facts but not representative photos or playable calls. Existing photo/call enrichment is scoped to Trip Planner recommendations. The user also finds Wishlist and Watch semantically duplicative. Current live personal state has zero wishlist rows and zero watches.

## Decision

- Arizona Birds cards and profiles will expose at most one validated representative GBIF photo and one validated Xeno-canto call per exact catalog taxon.
- Media acquisition will run only through an explicit resumable server-side batch command/job. Browser/catalog GET requests remain network-free and read-only.
- Rufous stores only bounded metadata, source identity, safe derived URL, attribution, license, selection reason, status, caveats, and timestamps. It never stores/proxies/caches/transcodes image or audio bytes.
- Exact species identity is mandatory. Hybrids and taxonomy-drift taxa MUST NOT borrow parent, historical, or common-name media. Unavailable media uses an intentional Rufous placeholder and explicit status.
- Catalog cards use lazy images and one accessible compact Play/Stop call control at a time with `preload="none"`; profiles show larger media plus full attribution/source/license.
- Wishlist is removed from storage, API, combined state, profiles, navigation, and My Birds. Watch becomes the sole prospective-interest state. Observation/life-list state remains independent.
- Because the live wishlist is empty, removal requires no personal-data conversion. Migration MUST still be explicit, idempotent, and tested; it removes any stale wishlist table/rows rather than silently mapping them to watches, since watches require center/radius semantics.

## Alternatives considered

- Lazy request-time media lookup was rejected because it would make GETs network-dependent and slow.
- Current warehouse-only media was rejected because it cannot satisfy useful catalog coverage.
- Parent-species media fallback was rejected as identity fabrication.
- Keeping Wishlist as a lightweight watch was rejected because it duplicates the intended user workflow.

## Consequences

A runtime catalog-media schema and batch lifecycle are required. Existing media validators/selectors should be reused rather than duplicated. Catalog APIs and browser validators gain bounded media objects. Personal collection contracts and clients shrink; watch creation still requires an Arizona center and radius.
