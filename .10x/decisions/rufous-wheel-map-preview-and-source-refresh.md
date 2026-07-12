Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Rufous wheel catalog, map preview, and source refresh

## Context

The user found the repeated three-card Arizona catalog inefficient, wants bird thumbnails and spatial preview in the semantic Field Map list, and wants a local header action equivalent in outcome to refreshing all routine Dagster-backed source data. Active records previously required 24-card pagination, excluded media from Field Map, prohibited every external Field Map runtime request, and kept AVONET/media enrichment outside routine refresh.

## Decision

1. Field Map encounter rows will reuse exact validated catalog-photo metadata. Map geometry, style, fonts, sprites, and telemetry remain local; this decision narrowly supersedes the prior prohibition only to allow validated GBIF catalog image URLs already governed by `.10x/specs/arizona-catalog-media.md`. No discovery occurs on GET or in the browser.
2. Hover or keyboard focus on an encounter row shows a transient unclustered point highlight without panning, zooming, or changing persistent selection. Pointer exit or focus exit restores the selected-only map state.
3. Arizona Birds replaces paginated cards with a single-select, scroll-snapped vertical name wheel. A subtle scale/opacity/indent curve surrounds one centered active taxon; its separate preview shows existing photo, facts, call control, and profile action. It never autoplays.
4. The header refresh action runs only the existing routine `full-refresh` contract: eBird, GBIF, Xeno-canto, NOAA, USGS, and USGS Earthquakes through one Quack owner, followed by SQLMesh only after all succeed. AVONET and catalog-media enrichment remain explicit separate lifecycles.
5. Refresh runs after explicit confirmation in a background subprocess, one at a time, with durable redacted status/log files under `.logs/`. The shell remains responsive, but warehouse-backed requests may return the existing database-busy state until completion. No automatic retry or cancellation is added.

## Alternatives considered

- Local placeholders: rejected because they are not bird-specific pictures.
- Strong 3D cylinder or flat list: rejected in favor of a restrained curve with reduced-motion fallback.
- Literal Dagster materialize-all: rejected because current safe orchestration requires one shared Quack lifecycle and post-success SQLMesh.
- Include AVONET/media: rejected because both have ratified explicit manual lifecycle boundaries.
- Fully usable staged refresh: rejected as unnecessary complexity involving runtime-state merge and atomic database replacement.

## Consequences

Field Map may request only validated GBIF image bytes in addition to local API calls. The map snapshot gains bounded deduplicated photo metadata. Catalog pagination contracts are superseded by wheel selection contracts. Refresh is a high-impact local mutation with confirmation, same-origin protection, one-run locking, persistent failure state, personal/runtime-state preservation, and no implicit retries.
