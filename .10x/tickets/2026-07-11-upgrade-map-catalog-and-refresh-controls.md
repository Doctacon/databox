Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: None
Depends-On: None

# Upgrade Field Map, catalog browsing, and refresh controls

## Outcome

Deliver three independent Rufous improvements: photo-backed encounter previews, a subtle accessible bird wheel, and a confirmed background routine source refresh.

## Governing records

- `.10x/decisions/rufous-wheel-map-preview-and-source-refresh.md`
- `.10x/specs/field-map-encounter-photo-preview.md`
- `.10x/specs/arizona-bird-wheel-catalog.md`
- `.10x/specs/local-source-refresh-control.md`

## Child plan

1. `.10x/tickets/2026-07-11-add-field-map-encounter-photo-preview.md`
2. `.10x/tickets/2026-07-11-build-arizona-bird-wheel-catalog.md`
3. `.10x/tickets/2026-07-11-build-local-refresh-runtime-api.md`
4. `.10x/tickets/2026-07-11-add-header-source-refresh-control.md` (depends on 3)
5. `.10x/tickets/2026-07-11-verify-map-wheel-and-refresh-controls.md` (depends on 1–4)

Children 1, 2, and 3 are parallelizable. Child 4 follows the refresh API. Aggregate verification follows all implementation children.

## Aggregate acceptance

- Encounter rows show validated thumbnails and hover/focus-only unclustered map highlights.
- Arizona Birds uses one accessible subtle centered wheel and one identity-matched preview without pagination or autoplay.
- Header launches exactly the routine six-source Quack/SQLMesh refresh after confirmation, one at a time, with durable safe status and temporary-busy disclosure.
- Privacy, identity, licensing, source ownership, personal/runtime-state preservation, accessibility, and full backend/frontend/data/static gates pass with independent reviews.

## Exclusions

No AVONET/media refresh, external map resources, strong 3D wheel, autoplay, staged warehouse swap, automatic retry, or live source refresh during ordinary tests.

## Progress and notes

- 2026-07-11: User ratified highlight-only map preview, subtle wheel, routine six-source refresh, confirmed background execution, temporary warehouse-busy behavior, and validated GBIF thumbnail requests with map resources remaining local.

## Blockers

None. Parent is a plan, not executable.
