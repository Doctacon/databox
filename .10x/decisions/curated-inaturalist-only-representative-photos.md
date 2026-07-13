Status: active
Created: 2026-07-13
Updated: 2026-07-13

# Curated iNaturalist-only representative photos

## Context

Rufous implemented a Wikimedia-P225/P18-primary and curated-iNaturalist-fallback design under `.10x/decisions/superseded/globally-curated-catalog-bird-photos.md`. Deterministic tests and source-boundary repairs passed, but two bounded production-path confirmations failed because Wikidata Query Service exact-P225 discovery was unavailable. The fail-closed contract correctly prevented fallback and database mutation, but it also made Wikimedia an operational dependency for every photo selection and blocked complete migration.

The current persisted state remains coherent and useful: 621 catalog species and all eight saved Trip Planner recommendations have validated curated iNaturalist photos; 85 catalog identities have typed placeholders. The app screenshot supplied by the user also exposed `invalid unavailable photo`, showing that unavailable-row presentation must remain a first-class validated state rather than causing whole-catalog failure.

On 2026-07-13 the user explicitly rejected Wikimedia as a viable dependency and ratified curated iNaturalist-only representative photos.

## Decision

Rufous representative photos for Arizona Birds catalog/profile, Field Map, and new/saved Trip Planner recommendations will use exactly one discovery source: the ordered curated iNaturalist `taxon_photos` shortlist for one exact active species-rank taxon.

Identity resolution will use iNaturalist API v2, followed by v1 `GET /v1/taxa/{id}` only for the curated shortlist, as governed by `.10x/decisions/inaturalist-curated-photo-api-split.md`. That decision remains active for endpoint and cross-version identity semantics; references there to “fallback” no longer define source order.

Wikidata Query Service, Wikidata P225/P18, and Wikimedia Commons will not participate in representative-photo discovery, activation, persistence, browser validation, migration, or operational readiness. Existing Wikimedia-specific code and tests should be deleted rather than retained as a dormant second implementation.

The existing exact-binomial, active species-rank, curated-order, Creative Commons, attribution, 1,000×750 dimension floor, provider-generated bounded URL, metadata-only persistence, no-browser-discovery, no-GBIF/direct-observation fallback, placeholder, serialization, and protected-state requirements remain.

A typed unavailable result is valid presentation data. One unavailable photo MUST render the Rufous placeholder and MUST NOT invalidate the entire catalog, profile, map, or plan response.

This decision supersedes `.10x/decisions/superseded/globally-curated-catalog-bird-photos.md` and the Wikimedia source-order portions of `.10x/specs/superseded/curated-representative-bird-photos.md`.

## Alternatives considered

### Keep retrying WDQS

Rejected. Two bounded attempts failed, the dependency blocks all downstream selection under the required stop-on-transport-failure rule, and the user observed that the resulting app was not usable enough.

### Retain dormant Wikimedia support

Rejected. Dormant source logic would preserve the largest complexity, security, validation, and regression surface without serving the approved product behavior.

### Use arbitrary iNaturalist observations or GBIF photos

Rejected. These are occurrence photos rather than the manually ordered curated taxon shortlist and reintroduce the representative-quality problem.

### Use proprietary or unclear-license media sources

Rejected by the project's open-source-first principle and the existing explicit licensing contract.

## Consequences

- Rufous loses Wikimedia/P18 coverage and ranking but removes WDQS/Commons availability and source-integrity dependencies.
- Available results have provider `inaturalist`; typed unavailable results use the curated-photo unavailable family without an active URL.
- Current catalog and saved-plan rows require one explicit serialized iNaturalist-only re-evaluation so persisted provenance, attempted-source metadata, placeholders, and run observability match the new contract.
- GET paths remain local, network-free, and read-only.
- iNaturalist rate and daily budgets remain operational constraints; migration stays sequential/resumable and below the documented limits.
- Existing Wikimedia-first tickets/evidence remain historical; they do not govern new behavior.
