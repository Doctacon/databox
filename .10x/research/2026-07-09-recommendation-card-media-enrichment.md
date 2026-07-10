Status: done
Created: 2026-07-09
Updated: 2026-07-09

# Recommendation card media enrichment

## Question

How can every bird recommendation card show one representative photo and one call while preserving the single DuckDB system of record, open/public data dependencies, attribution, and local-only binary-storage policy?

## Sources and methods

- Inspected the latest persisted Queen Valley plan and recommendation/media rows in `data/databox.duckdb` read-only.
- Inspected:
  - `packages/databox-sources/databox_sources/gbif/source.py`
  - `packages/databox-sources/databox_sources/xeno_canto/source.py`
  - `transforms/main/models/birding_agent/planner/xeno_canto_media_evidence.sql`
  - `app/src/App.tsx`
- Queried Xeno-canto API v3 metadata for the configured Arizona query and the eight exact Queen Valley scientific names. The API key was loaded server-side and never printed.
- Queried GBIF occurrence search for exact scientific names, Arizona, United States, and `StillImage` media for all eight Queen Valley recommendations.
- Read official GBIF occurrence and image-cache documentation and Wikimedia Commons API/machine-readable attribution documentation.

Official sources:

- GBIF occurrence API: https://techdocs.gbif.org/en/openapi/v1/occurrence
- GBIF occurrence image API: https://techdocs.gbif.org/en/openapi/images
- Wikimedia Commons MediaWiki API: https://commons.wikimedia.org/wiki/Commons:API/MediaWiki
- Wikimedia Commons machine-readable data: https://commons.wikimedia.org/wiki/Commons:Machine-readable_data
- Xeno-canto API used by the existing source: https://xeno-canto.org/explore/api

## Findings

### Current Queen Valley plan

The latest plan has eight recommendations:

1. Ross's Goose (`Anser rossii`)
2. American White Pelican (`Pelecanus erythrorhynchos`)
3. Ring-necked Duck (`Aythya collaris`)
4. Bushtit (`Psaltriparus minimus`)
5. Yellow-headed Blackbird (`Xanthocephalus xanthocephalus`)
6. Northern Mockingbird (`Mimus polyglottos`)
7. American Coot (`Fulica americana`)
8. Mallard (`Anas platyrhynchos`)

The current local Xeno-canto table contains 1,000 recordings across only 42 species. Only Ring-necked Duck and Mallard have local media matches for this plan. Consequently, moving existing media rows into recommendation cards alone would leave six of eight Queen Valley cards without calls.

The full current Xeno-canto Arizona query reports 11,709 recordings across 368 species. Exact-name probes found Arizona/global recording counts:

| Species | Arizona | Global |
|---|---:|---:|
| Ross's Goose | 0 | 35 |
| American White Pelican | 0 | 6 |
| Ring-necked Duck | 8 | 81 |
| Bushtit | 15 | 263 |
| Yellow-headed Blackbird | 16 | 132 |
| Northern Mockingbird | 98 | 615 |
| American Coot | 46 | 270 |
| Mallard | 12 | 1,559 |

Arizona-first/global-fallback therefore provides a call source for all eight current recommendations; Arizona-only cannot.

### Photos

The existing GBIF dlt source intentionally flattens occurrence fields but discards `media[]`. It cannot currently power bird photos.

Exact GBIF Arizona `StillImage` occurrence searches returned image-bearing results for all eight Queen Valley species. Example media metadata includes:

- HTTPS image identifier,
- occurrence and media references,
- creator and rights holder,
- publisher,
- image format,
- per-media Creative Commons license.

Observed results commonly use CC BY-NC 4.0 and originate from iNaturalist open-data observations represented through GBIF. GBIF warns that occurrence images may have more restrictive licenses than occurrence data, so per-media license and attribution MUST be preserved.

GBIF offers a crop/resize cache URL derived from occurrence key plus the MD5 of the original media identifier. It supports bounded display sizes but may load slowly or fail when a publisher image is unavailable. The browser can stream a resized image from the exact GBIF API host without storing image bytes locally.

Wikimedia Commons is a viable alternative, but species matching and consistent machine-readable attribution are more complex. The existing approved GBIF source, complete Queen Valley sample coverage, and GBIF cache make GBIF the smaller first implementation.

### Existing plans

The warehouse currently contains two persisted plans, 16 recommendations, and 16 distinct recommendation species. A one-time bounded metadata backfill is feasible; mutating GET requests are unnecessary.

## User-ratified direction

The user selected:

- exact request-time media lookup for selected recommendation species,
- persistence of metadata and attribution in the single DuckDB system of record,
- remote streaming of binary image/audio media only,
- Arizona-first then global Xeno-canto fallback,
- one representative photo plus one native call player per bird card,
- removal of the separate Call and Media Examples section,
- page order: Field Plan; Weather and Elevation; High-likelihood Species; Uncommon but Plausible Targets; Evidence and Provenance.

## Recommended architecture

After deterministic recommendations are selected:

1. Perform bounded concurrent exact-species media lookups server-side.
2. GBIF: request one Arizona `StillImage` occurrence per scientific name, require recognized license/creator/source metadata, derive an allowlisted bounded GBIF cache URL, and retain the original media identifier only as provenance.
3. Xeno-canto: request one exact-species Arizona recording; if absent, request one global recording. Prefer call-like recording types, then quality A through E, then a stable recording-ID tie-break.
4. Persist the exact selected photo/call metadata, geographic scope, license, creator/recordist, source references, and lookup trace in `data/databox.duckdb` before returning the completed plan.
5. Return recommendation-centric typed media objects. React uses lazy images and native `<audio controls preload="none">`; no binary media is downloaded, proxied, cached, or stored by Databox.
6. Render media attribution and safe source/license links inside each species card. Remove the separate media section.
7. Keep image/audio URL validation independent and fail closed on host, path, identifier, or license inconsistency.

## Unratified execution semantics

Implementation must not guess these remaining choices:

- whether a media lookup failure preserves the recommendation card with an explicit placeholder or fails the entire plan,
- whether noncommercial Creative Commons variants such as CC BY-NC and CC BY-NC-SA are permitted (they dominate observed GBIF/Xeno coverage and are compatible with the current local noncommercial product, but constrain future commercial use),
- whether the two existing plans should receive one explicit bounded metadata backfill or remain unchanged until regenerated.

## Limits

- The sample proves current Queen Valley coverage, not perpetual coverage for every future taxon.
- A photo or recording can disappear upstream after persistence; the card needs an attribution-preserving unavailable state.
- GBIF images are occurrence evidence, not curated field-guide plates; species identification and framing quality vary by publisher.
- Request-time enrichment adds bounded network latency and external availability dependencies. It must not weaken the factual recommendation or model contract when media is unavailable.
