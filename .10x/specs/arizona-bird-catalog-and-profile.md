Status: active
Created: 2026-07-09
Updated: 2026-07-10

# Arizona bird catalog and modeled species profile

## Purpose and scope

This specification governs the local Arizona Birds page, selectable species/hybrid detail pages, modeled warehouse interface, and read-only API. It uses only facts already ingested and transformed into `data/databox.duckdb`.

## Catalog membership and identity

- The catalog MUST contain every latest eBird `US-AZ` regional-list taxon: current baseline 706 rows comprising 624 species and 82 hybrids.
- Stable browser/API identity MUST use the eBird species code; conformed species surrogate/natural keys remain internal linkage fields.
- Common name, scientific name, category, family, and taxonomic order MUST come from eBird-first conformance.
- Species and hybrids MUST remain visibly distinguishable and filterable. Hybrids MUST NOT inherit parent-species traits.
- Default order MUST be persisted taxonomic order with species code as a total tie-break.

## Modeled catalog interface

Create `birding_agent.arizona_species_catalog` at exactly one row per current regional taxon. It MUST expose:

- stable identity and taxonomy fields,
- `traits_status` and the exact AVONET trait/provenance fields governed by `.10x/specs/avonet-bird-traits-source.md`,
- recent valid/reviewed/non-private eBird observation count, latest observation timestamp, public-location count, and notable count,
- modeled GBIF occurrence count/latest event date where present,
- modeled Xeno-canto recording count and safe representative recording metadata where present,
- source/model freshness timestamps.

No missing evidence family may remove a catalog row. Counts MUST be zero and unavailable facts MUST remain null/explicit rather than inferred.

A detail query/view MAY aggregate top public eBird locations, but MUST exclude private locations and MUST return at most ten locations ordered by independent observation count, newest observation, location name, and stable location ID.

## Read-only API

The local FastAPI app SHOULD expose:

- `GET /api/birds` — all catalog summaries in stable taxonomic order,
- `GET /api/birds/{species_code}` — one complete modeled profile or stable not-found error.

The list response MUST be bounded to the 706-row regional catalog; browser pagination/filtering does not trigger warehouse or network writes. Both endpoints MUST be read-only and network-free, use typed bounded responses, suppress private locations and raw arbitrary payloads, and return user-friendly database-busy/unavailable errors.

## Browser navigation and list

- The app MUST add native local navigation between Trip Planner and Arizona Birds without adding a routing dependency when browser History APIs suffice.
- `/birds` MUST support browser back/forward and direct local reload.
- The catalog MUST provide case-insensitive search over common name, scientific name, and species code plus category filtering for all/species/hybrids.
- Browser pagination MUST show 24 taxa by default with bounded Previous/Next, accurate range/total, and reset to the first page when search/filter changes.
- Selecting a catalog card MUST navigate to `/birds/{species_code}`. Cards MUST show common/scientific names, category, family when available, modeled-traits availability, and recent-observation availability without inventing missing content.

## Species profile

A profile MUST display only modeled facts and clearly separate:

1. **Identity and taxonomy** — names, category, family/order, species code.
2. **Physical traits** — available AVONET measurements with source units, measurement sample/provenance, and inferred-trait disclosure.
3. **Ecology** — modeled habitat, habitat-density label, migration label, trophic level/niche, and primary lifestyle. Global range metrics are outside the governed AVONET source fields and MUST be disclosed as unavailable rather than inferred or presented as Arizona-specific.
4. **Arizona activity** — bounded recent public observation summary and public locations with dates/counts/notable labels.
5. **Occurrence and sound context** — modeled GBIF/Xeno facts and safely validated media/links only where already available in the warehouse.
6. **Evidence and provenance** — eBird/AVONET/GBIF/Xeno source status, timestamps, dataset DOI/version/license, and caveats.

Source codebook values MAY be rendered into concise deterministic sentences. GLM MUST NOT add plumage, field marks, conservation claims, behavior, seasonality, measurements, or locations absent from modeled facts.

Trait-unavailable profiles MUST remain useful through taxonomy and current Arizona evidence and MUST explain that AVONET has no exact match. Empty observation/occurrence/recording states MUST be visible and nonfatal.

## Accessibility and safety

- Navigation, search, category filter, pager, cards/links, headings, tables/definition lists, and disclosures MUST use native accessible semantics.
- Status and empty states MUST not rely on color alone.
- Existing exact media identity/license/URL/runtime guards remain mandatory for any displayed photo or call.
- Browser code MUST receive no database, eBird, GBIF, Xeno, Cloudflare, SMTP, Proton, or turbopuffer credential/configuration.

## Acceptance scenarios

### Complete exact-match profile

Given an Arizona species with AVONET and recent modeled evidence, when selected, then the profile displays exact source-backed taxonomy, traits/ecology, public Arizona activity, available occurrence/sound context, and provenance without any network call.

### Hybrid profile

Given an Arizona hybrid, when selected, then it is visibly labeled Hybrid, remains in catalog order/search, and shows trait-unavailable unless an exact modeled hybrid trait exists; it is never collapsed to a parent.

### Taxonomy-drift profile

Given one of the measured 24 current species absent from AVONET v7, when selected, then taxonomy/current evidence render and the profile explicitly reports no exact AVONET match.

### Privacy

Given public and private eBird observations for a taxon, when list/detail APIs and UI render, then private rows do not affect exposed location lists and no private location fields reach the response.

## Explicit exclusions

- No Wikipedia, turbo-search bird corpus, EOL, unmodeled narrative profile, request-time bird-fact discovery, map, image recognition, field-mark inference, or browser database access.
- No life-list/wishlist/watch mutation in this specification; those actions are governed by a subsequent focused personal-collection specification.
- No catalog-wide media backfill or promise of photo/call coverage for every taxon.
