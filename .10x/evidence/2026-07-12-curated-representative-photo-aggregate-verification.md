Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`

# Curated representative-photo aggregate verification

## What was observed

All final-state non-review gates passed for the shared curated selector, catalog/profile/Field Map integration, new Trip Planner enrichment, and the completed catalog and saved-plan photo migrations. Verification used deterministic injected provider fixtures, read-only DuckDB inspection, and existing test/static/build gates. It made no live provider request, database mutation, model call, email, routine source or AVONET refresh, call enrichment, or image/audio binary request.

Read-only validation reconstructed every persisted curated result through `CuratedPhotoResult` and applied `curated_photo_result_is_safe` against its exact current scientific name:

- catalog: 706 photo rows; 621 available `inaturalist`; 85 unavailable `curated_photo` placeholders; zero invalid results;
- saved planner: eight photo rows; eight available `inaturalist`; zero invalid results; zero recommendations with other than exactly one photo result;
- separate Field Map photo/media tables: zero, consistent with exact catalog-object reuse.

## Active-spec scenario mapping

1. **Deterministic Wikimedia ranking.** `tests/test_curated_photo.py::test_wikimedia_ranking_is_total_and_invariant_under_response_reordering` and `::test_wikimedia_assessment_area_and_title_rank_after_statement_rank` cover response reordering, statement rank, assessment, area, and stable title identity. Selector evidence and its passing review independently inspected the total tie-break chain.
2. **1,000×750 quality floor.** `tests/test_curated_photo.py::test_shared_dimension_floor` covers 900×900 and 1,200×700 rejection plus exact portrait/landscape acceptance. Offline persisted-result validation found zero catalog or planner dimension-contract violations.
3. **Wikimedia stops fallback.** `tests/test_curated_photo.py::test_eligible_wikimedia_stops_before_inaturalist` proves no iNaturalist call after an eligible Wikimedia result.
4. **Curated iNaturalist order.** `tests/test_curated_photo.py::test_no_eligible_wikimedia_uses_v2_identity_then_v1_curated_order` rejects the null/all-rights-reserved and prohibited-static-host leading candidates and selects the third eligible shortlist photo. Cross-version mismatch and active species-rank rejection tests cover the v2/v1 identity boundary.
5. **Curated-source exhaustion gives placeholder.** `tests/test_curated_photo.py::test_neither_source_eligible_returns_typed_placeholder_result` proves typed unavailability without GBIF/direct-observation fallback. Current catalog inspection found 85 valid curated placeholders and no legacy representative-photo provider.
6. **Hybrid/taxonomy drift is network-free unavailable.** `tests/test_curated_photo.py::test_non_binomial_never_queries_providers`, plus inactive/subspecies/ambiguous-taxon tests, prove fail-closed identity behavior without parent inheritance.
7. **Catalog interruption/resume.** `tests/test_catalog_media.py::test_photo_only_refresh_resumes_and_preserves_calls` and `::test_completed_photo_refresh_rerun_is_database_and_network_no_op` cover atomic checkpoints, missing-only resume, preserved calls, and completed no-op behavior. `.10x/evidence/2026-07-12-catalog-photo-final-live-resume-and-verification.md` records 706/706 unique current results, preservation of all 456 preflight-complete identities, and a lookup delta of exactly 250 for exactly 250 missing identities.
8. **Saved-plan photo-only migration.** `tests/test_recommendation_media_backfill.py::test_curated_photo_only_replaces_legacy_photos_preserves_calls_and_is_idempotent` and `::test_curated_photo_only_commits_each_completed_recommendation` cover bounded replacement, per-recommendation checkpoints, calls, and no-op completion. `.10x/evidence/2026-07-12-trip-planner-curated-photo-migration.md` records exactly eight replacements, eight inserted photos, zero inserted calls, zero missing, and zero duplicates.
9. **Network-free GETs and strict contracts.** Backend API/catalog tests and `app/src/BirdPages.test.tsx`, `app/src/App.test.tsx`, and `app/src/tripPlanValidation.test.ts` reject provider/URL/identity/license/dimension/extra-field mismatches and preserve placeholders. Provider discovery is injected in selector/media tests; normal GET and browser paths have no discovery owner.
10. **Field Map catalog reuse.** `app/src/FieldMap.test.tsx` and `tests/test_map_snapshot_api.py` cover exact species-keyed catalog-photo presentation, attribution retention, and validated map payload behavior. Read-only schema inspection found no separate map photo/media table, and the completed catalog child evidence records exact catalog-object reuse without a separate provider request.

## Aggregate commands and exact results

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest` — 769 passed, three snapshots passed, 86.37% coverage.
- `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — strict TypeScript passed; 18 files/273 tests passed; production Vite build passed; bundle audit found all 12 configured names and 10 configured values absent. Vite emitted only the existing large MapLibre chunk advisory.
- `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy packages/` — passed; 162 files formatted and 99 source files typed, with only the existing unchecked-body informational note in a test conftest.
- `.venv/bin/python scripts/check_secrets.py && .venv/bin/python scripts/generate_staging.py --check && .venv/bin/python scripts/generate_platform_health.py --check` — repository-native secret scan and both generated-state checks passed.
- `cd transforms/main && ../../.venv/bin/sqlmesh test` — 13 passed against DuckDB without applying a plan.
- `.venv/bin/python scripts/generate_docs.py --check && .venv/bin/mkdocs build --strict` — 20 dictionary files current; strict documentation build passed with upstream/non-navigation notices only.
- `.venv/bin/python scripts/check_source_layout.py` — seven sources passed.
- `.venv/bin/pre-commit run --all-files` — all 11 hooks passed.
- `git diff --check` and the empty cached-diff assertion — passed; no staged files.
- A read-only DuckDB Python inspection validated all 706 catalog and eight planner results through the shared offline validator and reported zero invalid catalog results, zero invalid planner results, zero non-singleton recommendation-photo groups, and zero separate map media tables.

## Migration preservation and side-effect boundary

The aggregate inspection did not rerun either live migration. Preservation is supported by the completed child evidence and reviews:

- Catalog migration evidence records all 86 protected table/subset fingerprints and all 19 external-state hashes unchanged before and after the final missing-only resume and again after full gates. This includes catalog facts, calls, observations, personal collection, Watches, calendar/outbox, refresh state, planner/model state, raw sources, AVONET, SQLMesh-related state, and unrelated warehouse data.
- Saved-plan migration evidence records all 86 protected non-evidence-table fingerprints, all 109 non-photo evidence rows, and all 19 external files unchanged. Plan/recommendation identity, ordering, text, confidence, rationale, timestamps, location/weather, GBIF occurrence context, eight Xeno-canto calls, personal state, calendar/outbox, refresh state, and unrelated data remained unchanged.
- The catalog command path and saved-plan command path are metadata-only and contain no model, email, routine refresh, AVONET refresh, call lookup, or binary download behavior. Exact live results recorded by the children were 706/706 catalog completion and eight saved-photo replacements with `inserted_call_count=0`.

## What this supports

This supports all non-review acceptance criteria in the aggregate verification ticket: every active-spec scenario has concrete test or migration evidence; all required full gates pass; current catalog and saved planner state contains only strictly validated curated providers or placeholders; Field Map has no separate media persistence; and recorded migration fingerprints preserve protected personal, planner, call, calendar/outbox, catalog, refresh, warehouse, SQLMesh, and external state within explicit limits.

## Limits

No physical-browser visual review, responsive-device run, screen-reader session, keyboard audit outside automated tests, or live image-load verification was performed. Automated DOM/accessibility assertions prove semantic labels, lazy loading, placeholders, safe links, and attribution retention but not visual composition or assistive-technology perfection. No network packet capture was taken; absence of live provider traffic in this aggregate run is established by the commands used and deterministic injected transports, while child no-side-effect claims rely on command-path inspection, exact result counters, and protected fingerprints. Provider-hosted images may later disappear or change availability because Rufous intentionally persists metadata and bounded URLs rather than binaries. Independent architecture, correctness, privacy/security/source, and UX/accessibility reviews remain the ticket's next gate.
