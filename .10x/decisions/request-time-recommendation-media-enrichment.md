Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Request-time recommendation media enrichment

## Context

The Birding Trip Copilot currently loads durable GBIF occurrence and Xeno-canto recording metadata through dlt/Quack into the single `data/databox.duckdb` warehouse. Recommendation cards do not have photos, and the separate Call and Media Examples section can show calls only for species represented in the truncated scheduled Xeno-canto slice.

The latest Queen Valley plan contains eight species. The current 1,000-row Xeno-canto table covers 42 species and has matching calls for only two of those eight. The full Arizona Xeno-canto query covers six of eight; exact global fallback covers all eight. Exact GBIF Arizona `StillImage` searches returned licensed image records for all eight, but the current GBIF source discards `media[]`.

The user wants every recommendation card to contain one photo and one call, with no separate media section. The user also reaffirmed that DuckDB remains the single system of record and approved bounded request-time lookups whose exact metadata and attribution are persisted before display.

Research and observed coverage are recorded in `.10x/research/2026-07-09-recommendation-card-media-enrichment.md`.

## Decision

1. Recommendation ranking remains powered by the existing local eBird/GBIF/Xeno-canto/SQLMesh evidence in `data/databox.duckdb`.
2. After the bounded recommendation set is fixed, the local Python planner performs exact-species media enrichment for only those recommendations.
3. GBIF supplies one licensed Arizona still-image candidate per recommendation.
4. Xeno-canto supplies one exact-species Arizona recording per recommendation, with a global exact-species fallback only when no valid Arizona recording exists.
5. Selected photo/call metadata, source identifiers, geographic scope, creator/recordist, license, URLs, unavailable status, and trace evidence are persisted in `data/databox.duckdb` before the completed plan is returned.
6. The browser receives only typed, validated recommendation-centric media metadata through the local API. It streams image/audio bytes remotely and never calls discovery APIs directly.
7. Databox does not download, proxy, cache, transcode, or persist image/audio bytes.
8. Media failure does not fail or alter the factual recommendation. Each failed lookup persists an unavailable state and the card shows an explicit placeholder.
9. Recognized Creative Commons licenses, including noncommercial variants, are permitted for this local noncommercial product. Attribution is mandatory. No-derivatives media must remain unmodified; unsupported or ambiguous license/URL combinations fail closed.
10. One explicit idempotent backfill enriches existing persisted recommendations. Result GET requests remain read-only and never trigger enrichment.

## Alternatives considered

### Scheduled warehouse media only

Rejected for the card requirement. It is fast and offline after refresh but currently covers only two of eight Queen Valley recommendations. Even the complete Arizona Xeno-canto corpus has no local recording for two targets.

### Browser-side GBIF/Xeno-canto lookup

Rejected. It would bypass the local API, produce transient unpersisted results, complicate attribution/security, and weaken DuckDB's system-of-record role.

### Store media binaries locally

Rejected. The product needs linked examples, not an offline media library. Binary storage creates licensing, retention, capacity, and refresh obligations without a ratified use case.

### Wikimedia Commons as the first photo source

Deferred. Commons is open and viable, but exact species mapping plus consistently machine-readable attribution is more complex. Existing approved GBIF integration and complete observed Queen Valley sample coverage make GBIF the smaller first path.

### Fail the plan when media is unavailable

Rejected by the user. Media is useful presentation context, not authority for the recommendation itself.

## Consequences

- Plan creation gains bounded public-network latency after recommendation selection.
- GBIF/Xeno-canto availability can reduce media coverage without reducing recommendation correctness.
- The planner/API need explicit media timeouts, concurrency bounds, typed error normalization, license/URL allowlists, deterministic candidate selection, and durable unavailable rows.
- React recommendation cards become the only primary media surface.
- Existing scheduled GBIF/Xeno-canto pipelines remain authoritative durable source slices and independently runnable Dagster jobs; request-time enrichment supplements rather than replaces them.
- Image and recording attribution must remain visible even when playback/rendering fails later.
- Future commercial deployment requires a new decision and license review because noncommercial media is intentionally allowed here.
