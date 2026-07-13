Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-11-implement-curated-photo-selector.md, .10x/specs/superseded/curated-representative-bird-photos.md, .10x/research/2026-07-11-bird-photo-source-quality.md

# iNaturalist v2 curated taxon-photo gap

## What was observed

A bounded live metadata-only schema probe on 2026-07-12 found that the public iNaturalist API v2 taxon routes do not expose the ordered curated `taxon_photos` shortlist required by the active specification.

- `GET https://api.inaturalist.org/v2/taxa` with an exact `Trogon elegans` query and explicit `id,name,rank,is_active,taxon_photos` fields returned the exact active species taxon but no `taxon_photos` field.
- Adding `default_photo` returned only a bounded default-photo identity.
- Requesting `fields=all` returned `default_photo` metadata but still no ordered `taxon_photos` shortlist.
- Candidate v2 routes `/v2/taxon_photos?taxon_id=20781`, `/v2/taxa/20781/taxon_photos`, and `/v2/photos?taxon_id=20781` each returned HTTP 404.
- The iNaturalist v2 docs page contained no `taxon_photos` route/field string in the retrieved bounded document.

The known public v1 taxon representation exposes ordered `taxon_photos`, but using v1 has not been ratified and would contradict `.10x/specs/superseded/curated-representative-bird-photos.md`, which explicitly requires fallback discovery through iNaturalist API v2.

## Procedure

The probes used Python standard-library `urllib.request` with a descriptive Rufous metadata-schema user agent, a ten-second timeout, and bounded response reads. They requested JSON metadata only. No image URL was fetched, no image bytes were downloaded, and no project/runtime/database state was written.

## What this supports or challenges

This challenges the execution feasibility of the active spec's combined requirements to use iNaturalist API v2 and inspect ordered curated `taxon_photos`. The selector ticket cannot implement both requirements from the observed public v2 surface without inventing an undocumented endpoint or silently using v1.

A narrow candidate supersession is: use v2 for exact active species-rank taxon resolution, then v1 `GET /v1/taxa/{id}` only for the ordered curated shortlist and photo metadata. That candidate is not active authority until explicitly ratified and recorded.

## Limits

This is a point-in-time public API observation, not proof that no private, undocumented, or future v2 field exists. Undocumented/private behavior is not an acceptable implementation dependency. Only one exact taxon response was inspected in depth; route/field availability, not taxon coverage, is the finding.
