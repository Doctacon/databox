Status: superseded
Created: 2026-07-11
Updated: 2026-07-13

# Globally curated catalog bird photos

## Context

Rufous currently selects catalog and profile photos from exact-species Arizona GBIF occurrence records. The selector validates identity, geography, attribution, license, and URL safety, but an occurrence photo is not necessarily a representative field-guide image. Users have observed wrong subjects and poor image quality.

Research in `.10x/research/2026-07-11-bird-photo-source-quality.md` found that 515 of 524 current available catalog photos already originate from iNaturalist through GBIF, so changing transport alone would not fix selection quality. An exact-name Wikidata audit found P18 images for 616 of 624 catalog species (98.7%). iNaturalist also exposes manually curated taxon-photo shortlists with explicit identification-quality guidance.

The user ratified the globally curated blend on 2026-07-11.

## Decision

Representative catalog, profile, Field Map, and Trip Planner photos will prioritize exact taxon identity, curation, licensing, attribution, and visual quality over the location where the photograph was taken.

The intended source order is:

1. Wikimedia Commons image attached by P18 to a Wikidata taxon item whose P225 scientific name exactly matches the catalog species.
2. An eligible photo from the curated iNaturalist taxon-photo shortlist for an exact active species-rank taxon.

Globally sourced photos are permitted for this representative taxon-media purpose. Arizona catalog membership remains established by the governed eBird catalog, not by photo geography.

Field Map currently reuses species-keyed catalog photo objects rather than observation-specific media. It will inherit the curated catalog result without a separate map-only media store. Encounter evidence, coordinates, and eligibility remain unchanged.

Only validated metadata and bounded provider image URLs may be persisted or exposed. Unknown identity, unsupported licensing, incomplete required attribution, unsafe URLs, or insufficient quality must fail closed. Exact taxonomy drift must remain unavailable unless a separately governed crosswalk is approved.

This decision supersedes only the following photo-specific portions of `.10x/decisions/request-time-recommendation-media-enrichment.md` and `.10x/decisions/catalog-media-and-watch-only-collection.md`:

- GBIF as the first representative catalog-photo source;
- Arizona occurrence provenance as a requirement for representative catalog/profile photos.

Those decisions remain active authority for unrelated media, persistence, DuckDB, call-recording, and browser-boundary behavior.

## Alternatives considered

### Keep Arizona-only occurrence photos

Rejected. It preserves geographic provenance but does not solve representative-image quality and unnecessarily narrows the candidate pool. Arizona relevance is already established independently by catalog membership.

### Wikimedia Commons only

Rejected as the complete architecture. Exact-name P18 coverage is high but not complete, and individual candidates still need resolution and metadata checks. A curated iNaturalist fallback improves coverage without returning to arbitrary occurrence ordering.

### Direct iNaturalist occurrence photos as primary

Rejected. Research-grade and agreement signals improve confidence, but occurrence photos still lack the curated representative-image contract of taxon photos.

### Macaulay Library

Rejected absent explicit Cornell permission and a separately approved licensing/API design. Its access and reuse terms are less suitable for the current open-source local integration.

## Consequences

- The active catalog-media specification must be superseded or revised before implementation because it currently mandates Arizona GBIF photo provenance.
- Enrichment remains explicit and networked; ordinary catalog/profile GETs remain local, read-only, and network-free.
- Wikimedia metadata parsing and safe thumbnail validation become required implementation surfaces.
- iNaturalist enrichment must honor its documented throttling and daily-use guidance.
- The user subsequently ratified a 1,000×750 orientation-independent quality floor, placeholder after curated-source exhaustion, no fallback after Wikimedia transport/malformed-response failure, complete catalog re-enrichment, saved-plan photo migration, and Field Map inheritance. These behaviors are governed by `.10x/specs/superseded/curated-representative-bird-photos.md`.
