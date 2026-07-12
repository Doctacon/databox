Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Arizona bird wheel catalog

## Purpose

Replace the repeated paginated card grid with a compact, discoverable single-column name wheel while preserving all catalog identities, filters, sorts, media safety, and profile navigation.

## Wheel behavior

The filtered/sorted result set MUST render as one vertical single-select name wheel with one centered active taxon. CSS scroll snapping establishes the resting center. Nearby names use a subtle, deterministic scale, opacity, and horizontal-indent curve; no strong 3D rotation is used. The active taxon is visually distinct and announced without moving page focus.

The wheel MUST support mouse wheel, trackpad, touch scrolling, click/tap, Arrow Up/Down, Page Up/Down, Home, and End. Keyboard selection follows the active option and keeps it centered. Search/filter/sort/reset changes stop audio, reset the active taxon to the first matching result, and preserve existing AND/filter/order semantics. Empty/loading/error/count states remain explicit. Pagination is removed.

Use a standards-based single-select listbox relationship or an equivalently tested native semantic pattern. The wheel and every option require visible focus and names. Reduced-motion mode removes animated settling and curve transitions while retaining selection and a clear active row. The implementation MUST remain usable at 320px, with zoomed text and long names.

## Active preview

Exactly one preview adjacent to/below the wheel shows the centered taxon's existing validated photo/placeholder, common/scientific identity, category, family, modeled trait availability, recent public observation count, one explicit Play/Stop call, concise attribution, and a profile link/action. Centering MUST NOT autoplay audio or navigate. Only explicit Play starts audio, and the existing one-active-catalog-call rule remains. Changing the active taxon stops playback and resets media failure state.

The full 706-row response remains read-only and bounded. Wheel rendering MUST avoid eagerly loading image/audio bytes for inactive taxa; only the active preview loads photo lazily and audio remains `preload="none"`. No new UI dependency is required.

## Acceptance scenarios

- Default Name A–Z centers the first taxon and shows one matching preview.
- Wheel/trackpad/touch and keyboard interactions deterministically change the active taxon and centered row.
- Search, sort, family, habitat, category, and mass controls compose exactly as before and reset center.
- Active photo/call/profile identity always matches the centered species code.
- Inactive taxa do not create image/audio elements.
- Reduced motion, keyboard-only, screen-reader semantics, 320px, long names, empty result, and 706-row performance pass.

## Supersession and exclusions

This specification supersedes the 24-row pagination and repeated catalog-card grid clauses in `.10x/specs/arizona-bird-catalog-and-profile.md` and the page-reset clause in `.10x/specs/arizona-catalog-discovery-controls.md`. Profiles and their routes remain unchanged. No autoplay, infinite fetch, horizontal carousel, strong 3D cylinder, drag-only control, new media source, or catalog mutation is introduced.
