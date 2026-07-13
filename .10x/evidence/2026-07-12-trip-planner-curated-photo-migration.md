Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: `.10x/tickets/done/2026-07-11-migrate-trip-planner-curated-photos.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`

# Trip Planner curated-photo implementation and migration evidence

## What was observed

Trip Planner now uses the shared curated selector for production recommendation photos while retaining Xeno-canto calls and separate GBIF occurrence-context evidence. The explicit saved-plan migration replaced all eight legacy recommendation-photo rows with eight valid iNaturalist curated rows. It inserted no calls and left no missing or duplicate photo rows.

## Procedure and results

### Focused implementation gates

- `pytest --no-cov -q tests/test_recommendation_media.py tests/test_recommendation_media_backfill.py tests/test_birding_trip_planner.py tests/test_curated_photo.py`: 86 passed.
- `cd app && npm run typecheck && npm test -- --run src/App.test.tsx src/tripPlanValidation.test.ts`: typecheck passed; 88 tests passed.
- Coverage includes production curated-selector conversion, saved-photo-only replacement, call/GBIF-context preservation, per-recommendation checkpoint behavior, idempotent no-op behavior, strict provider URL/identity/license/dimension validation, and curated frontend attribution.

### Live preflight

- No Quack, SQLMesh, source-refresh, Uvicorn, or competing recommendation-media backfill writer held the DuckDB.
- Read-only curated inspection found one plan, eight recommendations, eight targets, zero missing photos, zero missing calls, and zero duplicates.
- Before state: seven available GBIF photo rows and one unavailable GBIF photo row; eight Xeno-canto calls.
- Captured stable multiset fingerprints for 87 tables, a separate 109-row non-photo-evidence fingerprint, and SHA-256 hashes for 19 external data files. Personal row values were not copied into this record.

### Exact authorized live command

Run exactly once:

```text
.venv/bin/python -m databox.agent_tools.recommendation_media_backfill --database-path data/databox.duckdb --curated-photos
```

Result:

```text
mode=apply plan_count=1 recommendation_count=8 target_recommendation_count=8 replaced_photo_count=8 inserted_photo_count=8 inserted_available_count=8 inserted_unavailable_count=0 inserted_call_count=0 lookup_count=8 duplicate_media_count=0 remaining_missing_photo_count=0 remaining_missing_call_count=0
```

No rerun of the live command occurred.

### Post-state and protected-state comparison

- After state: eight available iNaturalist photo rows, zero legacy GBIF representative-photo rows, zero unavailable photo rows, zero duplicates.
- Every row had exact recommendation scientific identity, provider/source agreement, HTTPS provider-specific URLs, creator, matching license label/code, qualifying dimensions, and Wikimedia-first attempted-source provenance.
- All eight Xeno-canto call rows remained present and unchanged through the separate non-photo evidence fingerprint.
- All 86 protected non-evidence-table fingerprints were unchanged; all table counts were unchanged; all 109 non-photo evidence rows were unchanged; all 19 external file hashes were unchanged.
- This covers plans, recommendation IDs/order/confidence/rationale/text/timestamps, location/weather, non-photo evidence including GBIF occurrence context, calls, calendar/outbox, personal collection/Watches, source-refresh state, warehouse/SQLMesh-related tables, and unrelated state.
- A post-migration read-only curated inspection reported zero targets and zero lookups, demonstrating idempotent/resumable completion without a second live run.

### Final gates

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest`: 769 passed, three snapshots passed, 86.44% coverage.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/mypy packages/`: passed; MyPy checked 99 source files.
- `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py`: 273 tests passed; TypeScript and production build passed; 12 configured names and 10 configured values absent from the bundle. Vite emitted only its existing large MapLibre chunk advisory.
- `cd transforms/main && ../../.venv/bin/sqlmesh test`: 13 passed.
- `git diff --check` passed and `git diff --name-only --cached` was empty.
- The protected-state comparison was repeated after all gates and remained unchanged.

## What this supports

This supports every acceptance criterion in the owning ticket: curated new-plan enrichment; strict API/browser validation; complete saved-photo-only replacement; resumability/idempotence; preservation of calls, occurrence context, personal and unrelated state; and absence of model, email, catalog, source-refresh, call lookup, or binary-media behavior from the migration path.

## Limits

The live provider result reflects the public metadata returned on 2026-07-12. Network packet capture was not used; absence of prohibited side effects is supported by the dedicated command path, injected failure/forbidden-call tests, exact result (`inserted_call_count=0`), process preflight, and protected-state fingerprints. Image availability can change after validation because Rufous stores URLs and metadata rather than binaries.
