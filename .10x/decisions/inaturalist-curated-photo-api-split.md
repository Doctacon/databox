Status: active
Created: 2026-07-12
Updated: 2026-07-12

# iNaturalist curated-photo API split

## Context

The active curated-photo specification requires exact active species-rank iNaturalist resolution and the ordered curated `taxon_photos` shortlist. Bounded metadata-only probes recorded in `.10x/evidence/2026-07-12-inaturalist-v2-taxon-photo-gap.md` found that public API v2 resolves exact taxa but does not expose `taxon_photos`; candidate v2 shortlist routes return 404. The public v1 taxon detail representation exposes the required ordered shortlist.

## Decision

Rufous will use iNaturalist API v2 only to resolve and validate exactly one active species-rank taxon with exact scientific-name equality and a numeric stable taxon ID. After that identity is established, Rufous will request `GET /v1/taxa/{id}` only to retrieve the ordered curated `taxon_photos` shortlist and its metadata.

The v1 response MUST repeat the same numeric taxon ID, exact scientific name, active state, and species rank. Any mismatch, ambiguity, malformed response, transport failure, or missing shortlist fails the lookup unavailable. The existing bounded timeout, response cap, user agent, rate limit, candidate limit, URL/license/attribution/dimension validation, no-binary rule, and curated-order semantics apply across both calls.

The user ratified this narrow endpoint split on 2026-07-12. No other source order, fallback, identity, quality, licensing, persistence, or stopping behavior changes.

## Alternatives considered

### Keep v2-only and block fallback

Rejected because the observed public v2 surface cannot supply the ratified curated shortlist.

### Use v1 for both identity and shortlist

Rejected because v2 remains the stronger explicit-field exact-resolution boundary; v1 is used only for the missing curated metadata.

### Use `default_photo`

Rejected because it is not the ordered curated shortlist and can be unlicensed or hosted on the prohibited static host.

## Consequences

The selector performs at most two iNaturalist metadata requests for an eligible fallback attempt: v2 exact resolution, then v1 taxon detail. Both count against the existing rate budget. Tests must prove cross-version identity consistency and fail closed on mismatch. This decision supersedes only the v2-only endpoint clause in `.10x/specs/superseded/curated-representative-bird-photos.md`.
