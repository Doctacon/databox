Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-11-implement-curated-photo-selector.md, .10x/specs/superseded/curated-representative-bird-photos.md, .10x/decisions/inaturalist-curated-photo-api-split.md

# Curated representative-photo selector implementation

## What was observed

`packages/databox/databox/curated_photo.py` now implements one shared metadata-only selector with these boundaries:

- exact case-sensitive Wikidata P225 entity resolution is separated from bounded P18 statement discovery, so multiple exact-name entities fail closed and a statement cap cannot hide identity ambiguity;
- Commons `imageinfo` metadata is sanitized to bounded plain text and validated for exact file/source/thumbnail identity, Wikimedia MD5 path buckets, HTTPS hosts, supported raster formats, explicit Creative Commons licensing, creator attribution, and the 1,000×750 original-dimension floor;
- Wikimedia ranking is total: preferred statement, recognized assessment tier, original pixel area, normalized title, entity ID, then every exact persisted output field;
- successful Wikimedia no-eligible results proceed to iNaturalist; Wikimedia transport, malformed metadata, or ambiguous identity stops unavailable without changing providers;
- iNaturalist fallback resolves exactly one active species-rank exact-name taxon through v2, then retrieves only that ID's ordered curated shortlist through v1, requiring repeated cross-version ID/name/rank/active identity;
- iNaturalist selection preserves curated order, rejects null/all-rights-reserved and static-host photos, requires supported licenses/attribution/dimensions, and activates only the same-ID/same-extension open-data `large` variant plus canonical photo page;
- available and unavailable results are typed and can be revalidated offline with strict provider-specific URL, identity, attribution, license, dimension, source-record, attempt-order, and lookup-time checks;
- default JSON transport allows only four governed endpoint families, uses a descriptive user agent, ten-second timeout, one-MiB response cap, JSON-object requirement, and no media-byte endpoint;
- a process-local sequential limiter targets one request/second across both iNaturalist calls and caps the UTC-day count at 9,999.

Existing GBIF occurrence-photo and Xeno-canto call code was not modified.

## Tests and adversarial cases

`tests/test_curated_photo.py` adds 26 deterministic tests covering:

- Wikimedia ranking invariance under statement/page response reordering;
- statement rank before assessment, assessment before area, and exact 1,000×750 portrait/landscape boundaries;
- no iNaturalist call after eligible Wikimedia selection;
- v2 then v1 request order, cross-version identity mismatches, inactive/subspecies/ambiguous taxa, and two limiter invocations;
- curated-list skipping of null-license and `static.inaturalist.org` rows before selecting the third eligible photo;
- stop-on-Wikimedia transport/malformed response and ambiguous Wikidata identity;
- typed placeholder after both curated sources are exhausted and zero calls for non-binomial input;
- adversarial Wikimedia/iNaturalist hosts, schemes, widths, paths, file/photo IDs, formats, query strings, and source identities;
- process-local iNaturalist daily request cap.

Focused regressions also reran the unchanged recommendation-media and catalog-media suites.

## Commands and results

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='--no-cov' .venv/bin/pytest -q -p no:cacheprovider tests/test_curated_photo.py tests/test_recommendation_media.py tests/test_catalog_media.py` — 70 passed.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/ruff format --check .` — 162 files formatted.
- `.venv/bin/mypy packages/` — 99 source files passed; one existing unchecked-body informational note in a test conftest.
- `scripts/check_secrets.py`, `scripts/generate_staging.py --check`, and `scripts/generate_platform_health.py --check` — passed.
- `git diff --check` — passed; staged-file list empty.

## Side-effect and preservation limits

No catalog/planner migration, live enrichment, image/audio request, model call, email, DuckDB write, SQLMesh apply, AVONET refresh, browser change, map change, or call-media change occurred. Protected hashes remained:

- warehouse: `ca7ad49d4edc7c34b96f83944e7f3f5b748b84203b844205a666e309ca87a159`;
- SQLMesh state: `c4995254709053ebffabcc16fbfe235e1d47b93208a7a1b1a81bb77b75852a93`;
- `.env`: `37d7aa746dc98317e521698210187070ca5e10fce6ba9e8bab7e1064e132ea54`.

## Limits

Provider schemas were exercised through injected deterministic fixtures after ratification; no post-ratification live provider smoke was run. The process-local rate/day limiter assumes the planned serialized single-process enrichment owner; migrations must retain their separately specified resumable checkpoint and non-concurrent-writer boundaries. Visual subject quality remains provider-curation metadata, not a computer-vision or human-review guarantee.
