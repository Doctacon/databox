Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Field Map encounter photos and transient preview

## Purpose

Enhance the existing accessible encounter list with exact bird thumbnails and pointer/keyboard-equivalent spatial preview without changing public-evidence eligibility or persistent selection.

## API and media

`GET /api/map-snapshot` MUST remain read-only and network-free. It MUST add a bounded, species-keyed collection of at most 706 exact current catalog photo objects, deduplicated across encounters. Each object MUST use the existing catalog-media identity, URL, attribution, license, stale-identity, unavailable, and fail-closed validation rules. Every photo key MUST belong to an encounter species; every encounter species MUST resolve to exactly one available or unavailable object. No call metadata is needed.

The browser MAY request an available validated GBIF image URL. No map tile/style/font/sprite/geometry/telemetry/provider request is permitted. Hybrids and unmatched taxa MUST retain the Rufous unavailable placeholder and MUST NOT inherit media.

## Encounter list

Each row MUST show a small lazy thumbnail or Rufous unavailable placeholder, bird name, existing encounter facts, and concise visible attribution/license when a photo is available. Load failure MUST preserve the row and attribution and switch to a visible unavailable state. Image alt text names the bird; decorative placeholder artwork remains hidden from assistive technology.

## Transient map preview

Pointer hover and keyboard focus on a row MUST show an unclustered transient marker at that encounter's exact public coordinates, even when the underlying encounter is clustered. Preview MUST NOT pan, zoom, set `aria-pressed`, change the selected card, or replace persistent selection. Pointer leave, focus leaving the row, filtering the row out, and unmount MUST clear preview. Activating the row retains existing persistent select/zoom behavior. If preview and selection identify the same row, the selected style remains authoritative.

Preview changes MUST be visually perceivable and announced only through the focused row; they MUST NOT create noisy live-region announcements. Touch has no hover requirement and uses activation. Reduced motion disables preview animation.

## Acceptance scenarios

- An exact available species shows its licensed thumbnail and attribution; an unavailable/hybrid species shows the Rufous placeholder.
- Hover and focus expose the same unclustered location without moving the map; leave/blur restores prior selection.
- Click/Enter still selects and zooms.
- Filters clear invalid preview and selection coherently.
- Snapshot exact-key/cardinality/identity/privacy validators reject malformed or unrelated media.
- Field Map performs no media discovery and no remote map-resource request.

## Exclusions

No call playback in encounter rows, media discovery, binary caching, parent fallback, hover pan, hover selection, range inference, or external basemap.
