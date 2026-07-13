Status: done
Created: 2026-07-11
Updated: 2026-07-11

# Representative bird-photo source quality

## Question

Which open/public photo source and selection strategy should Rufous use when the current GBIF occurrence-photo selector can show the wrong subject or a poor-quality image?

## Current implementation inspected

- `packages/databox/databox/agent_tools/recommendation_media.py`
- `packages/databox/databox/catalog_media.py`
- `.10x/specs/arizona-catalog-media.md`
- `.10x/decisions/request-time-recommendation-media-enrichment.md`
- `.10x/research/2026-07-09-recommendation-card-media-enrichment.md`
- Runtime table `birding_catalog_media.results` in `data/databox.duckdb`, opened read-only.

The current selector asks GBIF for up to 50 exact-scientific-name Arizona `StillImage` occurrences. It rejects malformed identity, geography, format, attribution, license, and URL metadata, but ranks an eligible image principally by attribution completeness and GBIF occurrence ID. It does not use subject framing, resolution, community identification confidence, image popularity, or a curated representative-image signal.

The current runtime catalog contains 524 available photos and 182 unavailable photos. The persisted original URLs show that 515 of the 524 available photos come through the iNaturalist open-data image host via GBIF. Therefore changing only the transport from GBIF to iNaturalist occurrence search would not solve the underlying selection problem.

## Sources and methods

Official sources consulted on 2026-07-11:

- iNaturalist API v2 documentation: https://api.inaturalist.org/v2/docs/
- iNaturalist taxon-photo guidance: https://help.inaturalist.org/en/support/solutions/articles/151000184018-what-guidelines-should-i-follow-when-choosing-taxon-photos-
- iNaturalist wrong-taxon-photo correction: https://help.inaturalist.org/en/support/solutions/articles/151000170377-the-taxon-photo-is-wrong-how-does-this-get-fixed-
- Wikimedia Commons machine-readable metadata: https://commons.wikimedia.org/wiki/Commons:Machine-readable_data
- Wikimedia Commons licensing: https://commons.wikimedia.org/wiki/Commons:Licensing
- Wikidata image property P18: https://www.wikidata.org/wiki/Property:P18
- eBird API terms: https://www.birds.cornell.edu/home/ebird-api-terms-of-use/
- Cornell media licensing agreement: https://support.ebird.org/en/support/solutions/articles/48000952192-cornell-media-licensing-agreement
- GBIF occurrence API: https://techdocs.gbif.org/en/openapi/v1/occurrence
- GBIF image API: https://techdocs.gbif.org/en/openapi/images

Read-only live probes were made against iNaturalist API v2, Wikidata Query Service, and the Wikimedia Commons Action API. No provider refresh, catalog enrichment, media persistence, or product mutation was performed.

### Bounded Wikidata coverage audit

The 624 exact scientific names whose Rufous catalog category is `species` were queried in batches through Wikidata. A candidate counted only when a Wikidata item had an exact `P225` taxon-name value and at least one `P18` image.

Results:

- Catalog species: 624
- Species with exact-name P18 image: 616
- Exact-name coverage: 98.7%
- P18 candidates across those species: 987
- Exact-name misses: 8

The eight misses were `Astur atricapillus`, `Astur cooperii`, `Botaurus exilis`, `Crinifer concolor`, `Hesperoburhinus bistriatus`, `Saucerottia beryllina`, `Selasphorus heloisa`, and `Vireo swainsoni`. Several appear to be taxonomy-name drift and must remain unmatched unless an explicit exact crosswalk is governed.

A ten-species sample produced P18 coverage for all ten. Commons `imageinfo` metadata showed machine-readable dimensions, creator, license, and assessment data. Sample dimensions ranged from 480×480 to 6726×5399; licenses included CC BY, CC BY-SA, and public domain. Some files carried `quality`, `featured`, `valued`, or `picture of the day` assessments. This demonstrates both useful ranking signals and the need for minimum-dimension and metadata checks rather than blindly taking the first P18 value.

### Bounded iNaturalist curated-photo audit

Ten Arizona catalog species were resolved to exact, active, species-rank iNaturalist taxa. Each taxon exposed a manually curated `taxon_photos` shortlist. Official iNaturalist guidance says these photos should prioritize identification value, diagnostic features, common forms, clarity, and small-size legibility.

For all ten sampled taxa, the curated shortlist contained at least one supported Creative Commons photo at least 1000×750. The first eligible photo appeared between positions 1 and 4. `Trogon elegans`, currently unavailable in Rufous, had an eligible 2048×1652 CC BY-NC curated photo.

The default first iNaturalist taxon photo is not always reusable. For example, the default Rufous Hummingbird photo was all-rights-reserved on `static.inaturalist.org`; the third curated photo was a 2000×1492 CC BY-NC image on the iNaturalist open-data host. Selection must therefore inspect the curated shortlist and per-photo license rather than trusting `default_photo`.

## Findings

### Wikimedia Commons through exact Wikidata taxon identity

Strengths:

- The image is attached to an exact taxon item rather than selected from an arbitrary occurrence record.
- Exact `P225` identity plus `P18` gives 98.7% coverage of the current species catalog.
- Commons accepts free content rather than noncommercial-only media, improving future reuse flexibility.
- The Action API provides dimensions, creator, license, source URL, and assessment signals.
- Commons thumbnail URLs support bounded display sizes without storing image binaries.
- Multiple P18 values can be ranked by preferred statement rank, Commons assessments, dimensions, and metadata completeness.

Limits:

- P18 values are curated but not guaranteed to be field-guide-perfect; some show only one sex or life stage.
- Some candidates are low resolution or have awkward machine-readable author text.
- Exact scientific-name drift causes misses. Fuzzy or synonym matching would violate the current fail-closed identity contract unless a governed crosswalk is added.
- Attribution parsing must sanitize HTML-bearing `extmetadata` and preserve the canonical file page and license.

### iNaturalist curated taxon photos

Strengths:

- The shortlist is explicitly curated for identification usefulness and small-size legibility.
- Exact active species-rank taxon identity is available.
- Per-photo license, attribution, dimensions, stable photo ID, and bounded image variants are exposed.
- It is a much stronger representative-image signal than an arbitrary iNaturalist observation reached through GBIF.

Limits:

- Curated photos may be all-rights-reserved. Only supported Creative Commons photos on the open-data host may be used.
- iNaturalist asks clients to stay near or below 60 requests/minute and under 10,000 requests/day. A 624-species explicit enrichment is feasible but must be throttled and resumable.
- Taxonomy can differ from eBird; exact unresolved names must remain unavailable.
- Most eligible sampled photos were CC BY-NC, preserving the current local noncommercial constraint but reducing future commercial flexibility.

### Direct iNaturalist observation search

Research-grade status, exact observation taxon, agreement/disagreement counts, identifications, votes, favorites, photo dimensions, license, and moderation flags can improve occurrence-photo ranking. However, a research-grade observation still does not guarantee representative framing or field-guide quality. This is a useful fallback, not the best primary source.

### GBIF occurrence media

GBIF remains valuable provenance and biodiversity evidence, but occurrence media are not curated representative plates. Better GBIF filters can reject more bad candidates, but GBIF lacks the strong taxon-photo curation signal available from Wikimedia and iNaturalist. It should be a last fallback for catalog presentation rather than the primary representative-photo selector.

### Macaulay Library / eBird media

Macaulay offers excellent bird-specific media, but the public eBird API terms and Cornell media agreement impose source-specific access and reuse conditions, API keys, and noncommercial or permission boundaries. There is no comparably simple public representative-photo API contract suitable for this open-source, self-contained integration. Do not adopt Macaulay without explicit Cornell permission and a separately approved licensing design.

## Conclusion

The best solution is a curated, multi-source selector rather than a blind provider swap:

1. **Primary: Wikimedia Commons P18 on an exact Wikidata P225 taxon item.** Require supported free license/public domain, creator or valid public-domain attribution handling, minimum dimensions, safe thumbnail/file URLs, and exact identity. Rank preferred statements first, then Commons quality/featured/valued assessments, dimensions, and deterministic file identity.
2. **Fallback: first eligible iNaturalist curated `taxon_photos` entry** for an exact active species-rank taxon. Reject all-rights-reserved/static-host photos and require supported license, attribution, dimensions, and open-data host.
3. **Optional final fallback: direct iNaturalist research-grade observation photo** ranked by exact observation taxon, community agreement, moderation/quality flags, dimensions, engagement, license, and deterministic ID.
4. **Retire arbitrary GBIF occurrence ordering as the representative-photo path.** GBIF may remain an evidence source or final compatibility fallback, but occurrence ID must not stand in for visual quality.
5. **Do not use Macaulay** without explicit licensing/API permission.

The Arizona-photo requirement should be removed from representative catalog media. Arizona catalog membership already proves Arizona relevance; forcing the photograph itself to have been taken in Arizona sharply reduces quality without improving taxon identity. Geographic provenance can remain useful for encounter/map imagery, where the photo represents a specific Arizona observation rather than the taxon generally.

## Ratification

On 2026-07-11, the user selected the recommended global curated blend: exact-taxon Wikimedia Commons primary with curated iNaturalist taxon-photo fallback. This is recorded in `.10x/decisions/superseded/globally-curated-catalog-bird-photos.md`.

The current active specification still requires Arizona GBIF provenance and must be superseded or revised before implementation. Quality thresholds, deterministic ranking, and migration behavior remain to be specified.

## Limits

- The 98.7% Wikimedia result measures exact taxon-item image presence, not final post-license/post-resolution acceptance for all 616 taxa.
- Only a ten-species iNaturalist curated-photo sample was inspected.
- No full visual review, duplicate-subject detection, computer-vision classifier, or human approval workflow was evaluated.
- Provider terms and API schemas can change and must be revalidated before implementation.
