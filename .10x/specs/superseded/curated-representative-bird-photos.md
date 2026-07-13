Status: superseded
Created: 2026-07-11
Updated: 2026-07-13

# Curated representative bird photos

## Purpose and scope

This specification governs representative bird-photo discovery, validation, ranking, persistence, migration, and display for:

- Arizona Birds wheel/cards and profiles;
- Field Map species thumbnails, which reuse catalog photo identity;
- new Trip Planner recommendation cards;
- already-persisted Trip Planner recommendations migrated by an explicit backfill.

It supersedes only the photo-source, photo-geography, photo-ranking, photo-URL, and photo-migration clauses of:

- `.10x/specs/arizona-catalog-media.md`;
- `.10x/specs/recommendation-media-enrichment.md`;
- `.10x/specs/field-map-encounter-photo-preview.md`.

Call media, catalog identity, encounter eligibility, planner recommendation facts/rank, browser discovery prohibition, local persistence, and no-binary-storage rules remain unchanged.

## Source order and stopping rule

For each exact species identity, the selector MUST evaluate sources in this order:

1. Wikimedia Commons images attached by P18 to an exact Wikidata taxon item whose P225 scientific name equals the normalized catalog/recommendation binomial.
2. The ordered `taxon_photos` shortlist of one exact, active, species-rank iNaturalist taxon whose scientific name equals the normalized binomial.

The selector MUST choose the highest-ranked eligible Wikimedia candidate when one exists. It MUST query iNaturalist only when no eligible Wikimedia candidate exists. If neither source has an eligible candidate, it MUST return a typed unavailable result and the UI MUST show the Rufous placeholder.

The selector MUST NOT fall back to direct iNaturalist observations, GBIF occurrence photos, parent taxa, common names, report-as taxa, subspecies, synonyms, fuzzy names, computer-vision guesses, model output, or arbitrary web search.

Representative photos MAY have been taken outside Arizona. Arizona catalog and encounter relevance remains governed by eBird identity/evidence, independently of photo geography.

## Shared exact-identity contract

An input scientific name MUST normalize to exactly one binomial using the existing conservative normalization. Hybrids and non-binomial or taxonomy-drift rows MUST be unavailable.

### Wikidata

A Wikimedia candidate is identity-eligible only when:

- the Wikidata entity has an exact case-sensitive P225 scientific-name value equal to the normalized input;
- the candidate is an image value from that entity's P18 statements;
- the entity resolution is unambiguous under the bounded query; multiple exact-name entities that cannot be deterministically disambiguated MUST fail closed;
- no synonym, common-name, parent, or description-text match is used.

### iNaturalist

An iNaturalist candidate is identity-eligible only when exactly one returned taxon has:

- exact scientific-name equality with the normalized input;
- `rank=species`;
- `is_active=true`;
- a numeric stable taxon ID.

Subspecies and descendants returned because of broad taxon search MUST be rejected. Ambiguous exact taxa MUST fail closed.

## Shared quality floor

An image is quality-eligible only when its machine-readable original dimensions have:

- long edge at least 1,000 pixels; and
- short edge at least 750 pixels.

Orientation does not matter. Missing, non-integral, zero, contradictory, or smaller dimensions MUST be rejected. Rufous MUST NOT download image bytes to infer dimensions.

## License and attribution

Eligible licenses are the existing explicit sane-version allowlist: CC0, CC BY, CC BY-SA, CC BY-NC, and CC BY-NC-SA. ND variants, all-rights-reserved media, unknown slugs, missing licenses, malformed URLs, invented versions, and inconsistent metadata MUST fail closed.

Every available result MUST persist and expose bounded plain-text creator/artist attribution, canonical license code and HTTPS license URL, canonical source page, source record identity, selected provider, original dimensions, selection reason, and lookup timestamp. HTML from provider metadata MUST be sanitized to bounded plain text before persistence. Missing creator/artist attribution MUST fail closed, including public-domain candidates.

Provider attribution, source, and license remain visible when browser image loading later fails.

## Wikimedia discovery, validation, and ranking

Discovery MUST use public Wikidata and Wikimedia Commons APIs with a descriptive user agent, explicit timeout, response-byte cap, candidate cap, and tightly bounded concurrency. It MUST NOT scrape rendered pages.

For each exact Wikidata entity, inspect a bounded set of P18 statements. Resolve candidate metadata through Commons `imageinfo`, including canonical file/description URL, bounded thumbnail URL, dimensions, artist, license, and assessments.

Only HTTPS URLs on exact approved Wikimedia hosts and provider-generated path grammars may activate. Query strings, fragments, credentials, traversal, non-image formats, SVG for this photographic surface, and mismatched file identities MUST fail closed. The active display URL MUST be a bounded Wikimedia thumbnail no larger than 1,024 pixels on its long edge; original bytes MUST NOT be activated, proxied, or stored.

Eligible Wikimedia candidates MUST be ranked totally and independently of API return order by:

1. preferred P18 statement rank before normal rank; deprecated statements are ineligible;
2. Commons assessment tier: featured/picture-of-the-day first, then quality, then valued, then no recognized assessment;
3. larger original pixel area;
4. normalized canonical Commons file title;
5. stable Wikidata entity ID and remaining exact persisted fields.

When multiple recognized assessments exist, the strongest tier controls. Unknown assessment strings confer no preference.

## iNaturalist discovery, validation, and ranking

Fallback identity resolution MUST use iNaturalist API v2 with a descriptive user agent and explicit requested fields. After v2 establishes exactly one active species-rank taxon with exact scientific-name equality and a numeric stable taxon ID, shortlist discovery MUST use `GET /v1/taxa/{id}` only to retrieve the ordered curated `taxon_photos` metadata. The v1 taxon representation MUST repeat the same numeric taxon ID, exact scientific name, active state, and species rank; any mismatch or malformed/missing identity fails unavailable. Rufous MUST honor the documented maximum of 100 requests/minute across both calls, target no more than 60 requests/minute, remain under 10,000 requests/day, and use explicit timeout, response-byte cap, candidate cap, sequential or tightly bounded concurrency, and resumable checkpoints. This narrow endpoint split is governed by `.10x/decisions/inaturalist-curated-photo-api-split.md`.

Inspect the curated `taxon_photos` order only. An eligible photo MUST:

- have a positive numeric photo ID;
- have a supported per-photo license and bounded plain-text attribution;
- satisfy the shared dimensions floor;
- use the iNaturalist open-data host associated with reusable licensed photos;
- provide provider-generated bounded display and canonical source identities that pass exact host/path/ID/extension validation.

Photos on `static.inaturalist.org`, photos with a null license, and all-rights-reserved photos MUST be rejected. The selector MUST choose the first eligible photo in curated shortlist order. Curated position is authoritative; API array order is therefore intentionally semantic for this source. Stable photo ID and exact persisted fields MUST still be validated and recorded.

The active display URL MUST use the provider's `large` variant, whose documented maximum is 1,024 pixels. Rufous MUST NOT synthesize another host, extension, or photo ID.

## Persistence and typed APIs

Persist metadata only; image bytes MUST NOT be downloaded, cached, proxied, transformed, or stored.

Photo provider values MUST be exactly `wikimedia_commons` or `inaturalist` for available curated results. Unavailable results MUST identify the attempted curated-photo family without activating a URL. GBIF remains a separate occurrence-evidence source and MUST NOT be relabeled.

Runtime catalog media remains keyed by exact eBird species code plus current scientific-name identity hash. Planner media remains linked to exact recommendation identity. Every surface MUST validate source-specific URL, attribution, license, dimensions, and identity before returning an available photo.

Catalog, profile, Field Map, and Trip Planner GET endpoints MUST remain network-free and read-only. Browser code MUST perform no discovery and MUST accept only the two curated photo providers for representative photos. Field Map MUST continue to deduplicate the current catalog photo object by exact encounter species; it therefore inherits the curated catalog result without a separate map media store.

## Explicit catalog migration

An explicit resumable photo-only refresh MUST process the complete current 706-row catalog in stable order while Quack/SQLMesh and other writers are inactive.

- All 624 species MUST be reevaluated through the curated selector, including currently available and unavailable GBIF rows.
- Hybrids and unresolved identities MUST be persisted unavailable without provider lookup.
- Each completed species result MUST be published atomically; interruption may temporarily leave a documented mix of old and new providers, and rerun MUST resume without repeating completed current-identity results.
- A newly unavailable curated result MUST replace the prior GBIF representative photo; legacy GBIF is not a fallback.
- Calls and unrelated catalog/runtime rows MUST remain byte-for-byte or value-equivalent unchanged.
- Inspect/dry-run MUST make no network calls or writes. Explicit apply/refresh is the only mutation path.

## Explicit saved-plan migration

An explicit resumable photo-only backfill MUST reevaluate every persisted Trip Planner recommendation photo, including available GBIF and unavailable rows.

- It MUST NOT call the model or alter plan/recommendation text, IDs, rank, confidence, rationale, location, weather, evidence unrelated to recommendation photos, calls, creation timestamps, calendar state, outbox state, or personal state.
- It MUST replace the prior recommendation-photo evidence atomically per recommendation with one curated available/unavailable result and preserve referential integrity.
- Interruption MUST resume without duplicate active evidence or repeated completed lookups.
- New plans MUST use the same curated selector before completed-plan persistence.

Catalog migration and saved-plan migration MUST NOT write concurrently.

## Failure and observability

Provider timeout, HTTP failure, throttling, malformed JSON, oversized response, ambiguous identity, unsafe metadata, no eligible candidate, or database-busy state MUST produce bounded sanitized diagnostics without secrets, raw provider payloads, personal data, coordinates, or arbitrary URLs.

A source failure MAY allow progression from Wikimedia to iNaturalist only when the Wikimedia attempt completed safely as unavailable. Transport failure or malformed Wikimedia response MUST fail that lookup unavailable rather than silently changing provider semantics. Automatic retries are limited to an explicitly bounded transient-HTTP policy; reruns remain operator-driven.

Lookup traces and batch run records MUST expose safe counts by provider/status, checkpoints, duration, and failure class. They MUST NOT expose credentials or raw response bodies.

## Acceptance scenarios

1. Given an exact species with multiple eligible P18 images, selection is deterministic under response reordering and follows statement rank, assessment tier, pixel area, and stable file identity.
2. Given a 900×900 image, it is unavailable because its long edge is below 1,000; given a 1,200×700 image, it is unavailable because its short edge is below 750; given a 1,000×750 portrait or landscape image, it is dimension-eligible.
3. Given an eligible Wikimedia candidate, iNaturalist is not called.
4. Given no eligible Wikimedia candidate and a curated iNaturalist list whose first two photos are all-rights-reserved and whose third is licensed and large enough, the third photo is selected.
5. Given neither curated source has an eligible exact-species photo, Rufous persists unavailable and shows the placeholder without GBIF/direct-observation fallback.
6. Given a hybrid or taxonomy-drift name, neither source is queried and no parent photo is inherited.
7. Given catalog migration is interrupted, completed identities retain one curated result, untouched identities retain their prior row, and rerun resumes safely.
8. Given saved-plan migration, all recommendation photos change only within photo evidence/presentation; plan facts, calls, timestamps, calendar/outbox, model-call count, and personal state remain unchanged.
9. Catalog/profile/map/planner GETs perform zero discovery requests and reject mismatched provider URLs, unsafe attribution, extra fields, or invalid licenses/dimensions.
10. Field Map uses the same curated photo object as the catalog for an exact species and creates no separate provider request beyond browser loading of the validated bounded image URL.

## Explicit exclusions

No direct occurrence-photo fallback, GBIF representative-photo fallback, Macaulay integration, proprietary source, fuzzy/synonym/parent matching, computer vision, model-assisted selection, human moderation UI, binary storage/proxy/cache/crop, browser discovery, automatic scheduled media refresh, map-only photo store, call-media changes, or guarantee that every taxon has an available image.
