Status: active
Created: 2026-07-13
Updated: 2026-07-13

# Curated iNaturalist representative bird photos

## Purpose and scope

This specification governs representative bird-photo discovery, validation, persistence, migration, API contracts, and display for Arizona Birds catalog/profile, Field Map species thumbnails, new Trip Planner recommendations, and saved Trip Planner recommendations.

It supersedes `.10x/specs/superseded/curated-representative-bird-photos.md`. Call media, catalog and recommendation facts, encounter eligibility, personal data, calendar/outbox, source refresh, browser discovery prohibition, and no-binary-storage behavior remain unchanged.

## Source and exact identity

Rufous MUST use only the ordered curated iNaturalist `taxon_photos` shortlist. It MUST NOT query or activate Wikimedia/Wikidata, direct iNaturalist observations, GBIF occurrence photos, parent taxa, common names, report-as taxa, subspecies, synonyms, fuzzy matches, computer vision, model output, arbitrary web search, or proprietary media sources.

The input scientific name MUST conservatively normalize to exactly one binomial. Hybrids, non-binomial identities, and unresolved taxonomy drift MUST return typed unavailable without provider requests.

Identity resolution MUST use iNaturalist API v2 and accept exactly one result whose scientific name equals the normalized binomial, `rank=species`, `is_active=true`, and stable taxon ID is a positive integer. It MUST reject ambiguous exact taxa, descendants, and subspecies.

After v2 establishes identity, Rufous MUST use v1 `GET /v1/taxa/{id}` only for the curated shortlist. The v1 result MUST repeat the same taxon ID, exact scientific name, active state, and species rank. Any transport, schema, or identity mismatch MUST return typed unavailable.

## Curated shortlist selection

Rufous MUST inspect `taxon_photos` in provider order and choose the first eligible candidate. A candidate is eligible only when:

- photo ID is a positive integer;
- original dimensions are integral with long edge >=1,000 and short edge >=750, regardless of orientation;
- license is an allowed sane version of CC0, CC BY, CC BY-SA, CC BY-NC, or CC BY-NC-SA;
- creator attribution is present, sanitized to bounded plain text, and free of provider HTML;
- display URL is the provider-generated `large` variant on the approved iNaturalist open-data host and is exactly bound to the photo ID and supported image extension;
- canonical source URL is HTTPS on the approved iNaturalist host and exactly bound to the photo ID;
- URLs contain no credentials, explicit port, query, fragment, traversal, mismatched identity, or unapproved host/path.

Null/all-rights-reserved/ND/unknown licenses, missing attribution, static.inaturalist.org, unsafe URLs, malformed dimensions, and unsupported formats MUST be skipped. If no candidate is eligible, Rufous MUST return typed unavailable.

Rufous MUST use a descriptive user agent, ten-second bounded timeout, one-MiB response cap, bounded candidates, disabled or same-origin-governed redirects, sequential requests, <=60 requests/minute target, <10,000 requests/day, and resumable checkpoints. Image bytes MUST NOT be downloaded.

## Persistence and typed contracts

Persist metadata and bounded provider URLs only. Available results MUST use provider/source `inaturalist` and persist exact scientific identity, taxon ID, photo ID, curated position, dimensions, creator, canonical license code/text/URL, display URL, source URL, selection reason, lookup timestamp, and safe attempted-source/outcome metadata.

Typed unavailable results MUST contain no active image/source/license URL and MUST retain only bounded identity, reason/failure class, lookup timestamp, and attempted source metadata allowed by the API contract. An unavailable result is valid data, not a malformed response.

Catalog media remains keyed by exact eBird species code plus current scientific-name identity hash. Planner photo evidence remains linked to exact recommendation identity and MUST be a validated singleton. GBIF remains separately typed occurrence context and MUST never activate as a representative photo.

Catalog/profile/Field Map/Trip Planner GETs MUST be network-free and read-only. Browser validation MUST accept only strict iNaturalist available results or typed unavailable results. One unavailable row MUST render the Rufous placeholder and MUST NOT invalidate the containing catalog, profile, map, or plan. Provider attribution, source, and license links MUST remain visible if browser image loading later fails.

Field Map MUST reuse the exact current catalog photo object and MUST NOT create a separate media store or provider request.

## Explicit serialized migration

After implementation and deterministic gates pass, an explicit catalog photo-only migration MUST re-evaluate all 706 current identities in stable order under this specification. A separate saved-plan photo-only migration MUST re-evaluate every persisted recommendation. The two writers MUST NOT overlap.

Each recommendation/species MUST checkpoint lookup plus atomic persistence so interruption resumes without repeating completed work or duplicating active rows. Completed current-identity results MUST be full-contract validated before being skipped. Inspect/dry-run MUST perform no writes or provider calls.

Migration MUST NOT call a model, regenerate recommendations, alter plan/catalog facts, refresh calls, send email, run source/AVONET refresh, change personal observations/Watches, calendar/outbox, credentials, warehouse/SQLMesh state, or store image/audio binaries. Protected fingerprints MUST be captured before and after.

## Failure and observability

Provider timeout, HTTP/throttle failure, malformed or oversized response, ambiguity, cross-version mismatch, unsafe metadata, no eligible candidate, or database-busy state MUST fail closed with bounded sanitized diagnostics. Do not store secrets, raw provider payloads, arbitrary URLs, coordinates, or personal data in diagnostics.

Run records MUST expose safe counts by status/failure class, checkpoint, duration, and request count. Automatic retries MUST be tightly bounded; reruns remain operator-driven.

## Acceptance scenarios

1. Given an exact active species and curated shortlist whose first two photos are ineligible and third meets all constraints, the third is selected and persisted.
2. Given ambiguous, inactive, subspecies, cross-version-mismatched, hybrid, or non-binomial identity, selection is unavailable without unsafe fallback.
3. Given 900x900 or 1200x700 dimensions, the photo is rejected; 1000x750 portrait or landscape is dimension-eligible.
4. Given unsupported license, missing creator, unsafe host/path/ID, explicit port, query, fragment, credentials, traversal, or mismatched source identity, browser and server fail closed.
5. Given no eligible curated photo, catalog/profile/map/planner render the Rufous placeholder; a single unavailable row does not fail the whole response.
6. Given browser image-load failure, metadata, provider attribution, source, license, and restrained status announcement remain.
7. Given catalog migration interruption, completed identities retain one valid result and rerun resumes without repeated completed requests.
8. Given saved-plan migration, only recommendation-photo evidence changes; plan facts, calls, timestamps, calendar/outbox, model-call count, and personal state remain unchanged.
9. GET routes perform zero discovery requests/writes and reject malformed or extra fields before partial rendering.
10. Field Map uses the same validated photo object as catalog/profile for an exact species.

## Explicit exclusions

No Wikimedia/Wikidata, direct occurrence-photo or GBIF representative fallback, Macaulay/proprietary source, fuzzy/synonym/parent matching, model or computer-vision selection, human moderation UI, binary proxy/cache/crop/storage, browser discovery, scheduled media refresh, map-only media store, call-media changes, or guarantee that every identity has an available photo.
