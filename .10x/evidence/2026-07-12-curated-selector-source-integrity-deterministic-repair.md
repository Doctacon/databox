Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: `.10x/tickets/cancelled/2026-07-12-repair-curated-selector-source-integrity.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`

# Curated selector source-integrity deterministic repair

## What was observed

The deterministic, non-live phase repaired four reviewed selector/source-integrity gaps without provider calls or project DuckDB migration:

- Commons metadata now requests the provider's 800-pixel width tier rather than the request that Commons rounded to a 1280-pixel derivative. The activated URL still passes the exact file/hash/path validator and its encoded width remains at most 1024 pixels.
- Exact P225 discovery now sends the bounded `SELECT DISTINCT ... LIMIT 2` equality query directly to the Wikidata Query Service instead of translating it to relevance-limited `wbsearchentities`; two exact entities remain ambiguous and fail closed.
- Metadata HTTP uses a no-redirect opener and verifies the final HTTPS scheme, host, path, credentials, port, and fragment against the governed endpoint before reading a response.
- Catalog photo run records now persist bounded provider outcome/failure-class counters in `provider_outcomes_json`, including safe schema upgrade/backfill for existing run tables. Counters contain fixed class keys only, not provider bodies, arbitrary URLs, or secrets.

## Procedure and results

- `.venv/bin/ruff format packages/databox/databox/curated_photo.py packages/databox/databox/catalog_media.py tests/test_curated_photo.py tests/test_catalog_media.py` — passed; four files already formatted on the final run.
- `.venv/bin/ruff check packages/databox/databox/curated_photo.py packages/databox/databox/catalog_media.py tests/test_curated_photo.py tests/test_catalog_media.py` — passed.
- `.venv/bin/pytest --no-cov -q tests/test_curated_photo.py tests/test_catalog_media.py` — 55 passed in 3.45 seconds.
- `git diff --check` — passed.
- Empty cached-diff assertion — passed; no staged files.

Deterministic tests cover the provider width request/1280-rounding regression, Wikimedia stopping before iNaturalist, complete SPARQL exact-identity resolution rather than search relevance, changed-origin targets including HTTP, loopback, link-local, private, credential-bearing, unapproved, and explicit-port URLs, bounded outcome classes, interrupted/resumed outcome counts, and legacy `photo_runs` schema upgrade.

## What this supports

This supports the code-only selector-source repair criteria and demonstrates that the repaired paths remain fail closed under deterministic provider fixtures. It also restores and preserves all pre-existing catalog-media tests after an intermediate editing failure temporarily truncated `tests/test_catalog_media.py`.

## Limits

No live provider request was made, so current Commons 800-tier behavior and Wikidata Query Service operational behavior remain to be confirmed during the separately serialized authorized live phase. No project DuckDB was opened or mutated. Existing catalog/planner rows were not re-evaluated. Full-suite, frontend, build, and live migration gates are intentionally deferred to aggregate execution after the other repair tickets complete. Remote-provider availability and visual subject quality remain outside deterministic evidence.
