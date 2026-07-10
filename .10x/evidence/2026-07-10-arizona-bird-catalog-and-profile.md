Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Relates-To: .10x/tickets/done/2026-07-09-build-arizona-bird-catalog-and-profile.md, .10x/specs/arizona-bird-catalog-and-profile.md

# Arizona bird catalog and modeled profile implementation

## What was observed

The local FastAPI/React app now provides a read-only Arizona catalog and modeled profiles while preserving the Trip Planner.

- `GET /api/birds` returns the live 706-row catalog in modeled taxonomic order: 624 species, 82 hybrids, and 600 exact AVONET trait matches.
- `GET /api/birds/{species_code}` returns a bounded typed profile containing only explicit response fields for taxonomy, AVONET traits/ecology/provenance, modeled public Arizona activity, GBIF/Xeno-canto context, and freshness.
- Browser `/birds` and `/birds/{species_code}` routes support direct local fallback plus History API navigation without a router dependency.
- Catalog search, species/hybrid filtering, reset, and exact 24-card client paging render from one bounded API snapshot.
- Profiles render explicit trait/evidence absence, exact measurement units, sample and mass-reference details, three-state inference disclosure, deterministic per-source status, AVONET DOI/version/license/file identity, and source freshness. They explicitly state that global range metrics are unavailable because they are outside the user-ratified governed AVONET source fields rather than inventing them.
- Public modeled locations whose names contain `(private)` remain visible because eBird `is_location_private` is the governed observation-privacy authority. The UI marks those names as possible access restrictions and tells the user to verify access before visiting.
- API and browser response validators reject extra fields. Structural tests confirm raw/private flags and internal model fields are not exposed.

## Procedure and results

### Focused API and planner regression

```text
uv run --no-sync pytest --no-cov -q tests/test_bird_catalog_api.py tests/test_api.py
27 passed
```

The API tests create a 706-row DuckDB fixture and cover stable ordering/cardinality, exact 624/82 category counts, rejection of undersized, duplicate-code, arbitrary/null-category, and 625/81 snapshots, read-only/no-network GET behavior, exact response shape, public `(private)`-named location handling, sparse/hybrid/taxonomy-drift states, deterministic responsive CSS breakpoints, static direct-route fallback, invalid/not-found/database-busy errors, malformed modeled location JSON, and safe error messages.

### Complete browser gate

```text
task app:check
72 Vitest tests passed
TypeScript typecheck passed
Vite production build passed
bundle configuration audit passed: 3 names and 3 configured values absent
```

The fourteen bird browser tests cover navigation/direct/popstate titles and page-heading focus; exact 706-row unique-code and 624/82 category enforcement; paging, search, category filtering, and reset; exact modeled sections and wording; units, unavailable global-range disclosure, three-state inference and attribution links; deterministic source statuses; `(private)` access warning; hybrid/drift/sparse/empty states; strict API error handling; and rejection of malformed responses. The 55 existing planner tests and three weather tests also passed.

### Live warehouse read-only probe

A TestClient probe against `data/databox.duckdb` disabled socket connections, fetched the list and representative public-location/species/hybrid profiles, checked direct static routes, scanned response structure for prohibited internal fields, and compared the database SHA-256 before/after:

```json
{"catalog": 706, "species": 624, "hybrids": 82, "traits_available": 600, "network_calls": 0, "database_hash_unchanged": true, "direct_routes": 2, "profiles_checked": ["greyel", "trokin", "sxrgoo1"]}
```

The two live modeled names that prompted privacy review (`Odell Lake (private)` and `Green Valley Country Club Estates (private)`) have source/model privacy flags of false. Other source rows with the same naming convention have true flags and are excluded by the reviewed model. The suffix therefore cannot replace the explicit privacy flag; it is treated only as an access warning in presentation.

### Repository gates

```text
ruff check .: passed
ruff format --check .: passed after formatting the new API test
mypy packages/: passed (80 source files)
pytest: 300 passed, 1 failed; coverage 85.84%
check_secrets.py .: passed
generate_staging.py --check: passed
generate_platform_health.py --check: passed
git diff --check: passed
```

The sole full-suite failure is the pre-existing order-dependent AVONET schema artifact mismatch already owned by `.10x/tickets/done/2026-07-10-repair-source-vcr-and-schema-snapshot-suite.md`: `test_avonet_schema_artifacts_match_normalized_resource_and_annotations` observed `normalized_scientific_name` where the isolated test expects `avibase_id`. All catalog/API/browser tests passed and the failure is outside this ticket's files.

Two initial live-probe invocations failed due to harness arguments (a string instead of `Path` for `static_dir`, then a guessed nonexistent hybrid code); the corrected probe above passed. Neither invocation wrote to the warehouse.

## Post-review repair verification

```text
uv run --no-sync pytest --no-cov -q tests/test_bird_catalog_api.py tests/test_api.py
27 passed

cd app && npm test -- --run
72 passed

uv run --no-sync ruff check packages/databox/databox/api.py tests/test_bird_catalog_api.py
uv run --no-sync ruff format --check packages/databox/databox/api.py tests/test_bird_catalog_api.py
uv run --no-sync mypy packages/
npm run typecheck
npm run build
task app:audit-bundle
.venv/bin/pre-commit run --files <catalog ticket files>
git diff --check
all passed
```

These repairs enforce exactly 706 unique catalog species codes and exactly 624 species plus 82 hybrids at both trust boundaries, suppress malformed or unexpected non-2xx payloads behind the generic local-catalog error, render inference `true`/`false`/`null` distinctly, expose source status only from modeled counts/timestamps/match state, set useful route titles, move focus once to newly rendered page headings (including async profiles), and verify the desktop/tablet/mobile catalog CSS declarations. The prior full-suite result was not rerun or reclassified as green; its separately owned failure remains.

## What this supports

- The ticket's API, browser navigation, catalog cardinality/pagination, modeled-profile, missing-state, privacy, credential, bundle, accessibility-semantics, and Trip Planner preservation criteria have executable evidence.
- GET endpoints are read-only and network-free under both fixture and live-warehouse validation.
- The implementation follows the active modeled privacy contract without interpreting display-name text as an observation privacy flag.

## Limits

- Final independent adversarial review passed and is recorded at `.10x/reviews/2026-07-10-arizona-bird-catalog-and-profile-review.md`.
- The separately owned schema/VCR isolation defect was subsequently repaired; the complete network-disabled Python suite passed 307/307 without cassette changes, as recorded in `.10x/evidence/2026-07-10-source-vcr-schema-suite-isolation.md`.
- Automated DOM tests cover native semantics and responsive CSS declarations, but no separate visual-browser screenshot audit was performed.
