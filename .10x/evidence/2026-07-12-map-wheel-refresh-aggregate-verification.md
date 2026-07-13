Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md, .10x/tickets/done/2026-07-11-upgrade-map-catalog-and-refresh-controls.md

# Map, wheel, and refresh aggregate verification

## Observation

All final-state non-review gates passed after `.10x/tickets/done/2026-07-12-require-empty-group-on-normal-exit.md`. Tests used fakes, bounded temporary local process groups, isolated copied SQLMesh state, or read-only live inspection. No routine/provider refresh, model call, email, AVONET/media refresh, Quack server, SQLMesh apply against project state, or media/image download ran.

## Full gates

- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, and `.venv/bin/mypy packages/` passed.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest` — 716 passed, three snapshots passed, 86.80% coverage.
- `.venv/bin/python scripts/check_secrets.py .`, `scripts/generate_staging.py --check`, and `scripts/generate_platform_health.py --check` passed.
- `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — TypeScript passed; 18 files/270 tests passed; production build passed; 12 configured names and 10 configured values were absent. Vite emitted only its existing large MapLibre chunk advisory.
- `cd transforms/main && ../../.venv/bin/sqlmesh test` — 13 passed.
- `.venv/bin/python scripts/generate_docs.py --check && .venv/bin/mkdocs build --strict` — 20 dictionary files current; strict build passed with upstream/non-nav notices only.
- `.venv/bin/pre-commit run --all-files` — all 11 hooks passed.
- CI-equivalent static Soda parsing validated all 25 contracts and required `dataset`/`columns` keys.
- `git diff --check` passed; `git diff --cached --name-only` was empty.

## Soda verification under preservation boundary

Direct `scripts/verify_dev.py` against the protected project warehouse passed its first contract, then stopped because the pre-existing `dev` environment lacks `birding_agent__dev`. This was a stale environment-materialization gap, not a contract assertion failure. Applying a dev plan to project state would violate the preservation criterion.

The safe equivalent copied the 62-MiB warehouse, 3-MiB SQLMesh state, and SQLMesh project to `/tmp/rufous-sqlmesh-verify`, repointed only the copied config, then ran:

- `sqlmesh plan dev --auto-apply --no-prompts --include-unmodified` — 13 SQLMesh tests passed and the current copied dev virtual layer materialized.
- all contracts through `scripts.verify_dev.rewrite_for_dev` against the isolated current dev database — 25/25 Soda contracts passed.

Exact project-state hashes below remained unchanged.

## Exact fake refresh

`PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='--no-cov' .venv/bin/pytest -q -p no:cacheprovider tests/test_source_refresh_api.py tests/test_source_refresh_runner.py tests/test_parallel_refresh.py` — 16 passed.

These tests prove exact canonical order `ebird`, `gbif`, `xeno_canto`, `noaa`, `usgs`, `usgs_earthquakes` at both subprocess boundaries; one Quack lifecycle; cleanup/dedupe/inspection after source completion; SQLMesh only after all six succeed; and source-attributed failure suppressing SQLMesh. All processes/providers are fakes.

## Live read-only cardinality and identity

A local `TestClient(create_app(database_path=...))` read only `/api/map-snapshot` and `/api/birds`:

- 706 catalog rows and unique species codes;
- 1,575 eligible encounters covering 152 exact species;
- 152 deduplicated photo identities, exactly equal to the encounter-species key set;
- 139 available photos and 13 unavailable placeholders;
- every map photo object exactly equaled its catalog photo object;
- every available photo scientific identity equaled its catalog scientific name;
- warehouse SHA-256 was unchanged before/after the GETs.

No image/media URL was loaded.

## Protected pre/post state

Exact pre/post SHA-256 values matched:

- `data/databox.duckdb`: `ca7ad49d4edc7c34b96f83944e7f3f5b748b84203b844205a666e309ca87a159`;
- `data/sqlmesh_state.duckdb`: `c4995254709053ebffabcc16fbfe235e1d47b93208a7a1b1a81bb77b75852a93`;
- `.env`: `37d7aa746dc98317e521698210187070ca5e10fce6ba9e8bab7e1064e132ea54`.

Exact pre/post row counts also matched: personal observations 2, watches 0, cancellation requests 0; plans 1, recommendations 8, evidence 117, tool traces 25; Xeno-canto media evidence 1,000; calendar accepted snapshots 1, event intents 1, outbox 1, attempts 2, dedupe 0; alert runtime settings 1 and SMTP verification 2; catalog media results 1,412 and runs 2. Whole-file equality proves all unrelated raw/modeled warehouse content remained unchanged.

## Acceptance mapping

- Field Map thumbnails/transient preview/selected authority: full suites and focused regressions passed; live exact identity/cardinality passed.
- Accessible wheel/one matching preview/no pagination/no autoplay/reduced motion: full 26-test BirdPages suite passed.
- Exact confirmed six-source durable refresh/one Quack/SQLMesh/safe progress and failure: focused 16-test fake lifecycle and full suites passed.
- Privacy, source ownership, licensing, state preservation, SQLMesh, Soda, docs, static, secret, bundle, and hooks: gates and hashes above passed.

## Final-state rerun after lifecycle hardening

A complete rerun on 2026-07-12 after `.10x/tickets/done/2026-07-12-harden-refresh-lifecycle-and-recovery.md` produced these results:

- Ruff, Ruff format, MyPy, full Python, secret/static generators passed. Python: 723 passed, three snapshots passed, 86.61% coverage.
- TypeScript passed, but the full frontend suite did not: 17 files passed and one failed; 271 tests passed and one failed. `app/src/MyBirds.test.tsx:192` used an unqualified unnamed `role=status` query which became ambiguous because the header's bounded initial refresh-status retry also rendered an unnamed `role=status`. This is a final-state regression and blocks the aggregate frontend gate.
- Because the command stopped at the frontend test failure, production build and bundle audit were not rerun in that chained invocation; their prior pre-hardening pass is not claimed as final-state evidence.
- SQLMesh: 13 passed. Docs dictionary check, strict MkDocs build, and all 11 pre-commit hooks passed.
- Exact connected refresh lifecycle: 23 passed. Static Soda structure: 25 contracts valid.
- Isolated copied-state SQLMesh plan ran 13 tests and materialized the current dev virtual layer; all 25 Soda contracts passed against the isolated copy.
- Live read-only results remained 706 catalog rows, 1,575 encounters, 152 exact species/photo identities, 139 available photos, and 13 placeholders, with exact catalog/map photo equality and unchanged warehouse hash.
- Protected pre/post SHA-256 values and all recorded personal/planner/calendar/outbox/media/catalog row counts remained exactly unchanged from the values above.
- `git diff --check` passed and no staged files existed.

No implementation repair was made during this verification-only rerun. The frontend failure requires a bounded repair and then another final-state frontend/build/bundle rerun before independent reviews can close the ticket.

## Definitive final-state aggregate rerun

A complete final rerun on 2026-07-12 after `.10x/tickets/done/2026-07-12-require-empty-group-on-normal-exit.md` passed every non-review acceptance gate:

- Ruff and Ruff format passed all 160 Python files; MyPy passed 98 source files with one existing unchecked-body informational note.
- Full Python passed 734 tests and three snapshots at 86.37% coverage.
- Focused refresh/API/runner/orchestration passed 34 tests, including the bounded real leader-gone/SIGTERM-ignoring-descendant case. No stale proof process remained.
- TypeScript passed; the full frontend passed 18 files/273 tests; production build and bundle audit passed with 12 configured names and 10 configured values absent. Vite emitted only its existing large MapLibre chunk advisory.
- SQLMesh unit tests passed 13/13. Static Soda parsing validated all 25 contracts.
- An isolated copy at `/tmp/rufous-sqlmesh-final` ran `sqlmesh plan dev --auto-apply --no-prompts --include-unmodified`, passed 13 SQLMesh tests, materialized the copied dev layer, and passed all 25/25 rewritten Soda contracts. Project warehouse and SQLMesh state were not applied or mutated.
- Secret scan, staging generator check, platform-health generator check, 20-file docs dictionary check, strict MkDocs build, all 11 pre-commit hooks, `git diff --check`, and no-staged-file check passed.
- Final read-only API inspection returned 706 unique catalog identities, 1,575 eligible encounters, 152 exact encounter/photo species identities, 139 available photos, and 13 placeholders. Every map photo object equaled its catalog photo object and every available scientific identity matched.
- Exact hashes remained unchanged: warehouse `ca7ad49d4edc7c34b96f83944e7f3f5b748b84203b844205a666e309ca87a159`; SQLMesh state `c4995254709053ebffabcc16fbfe235e1d47b93208a7a1b1a81bb77b75852a93`; `.env` `37d7aa746dc98317e521698210187070ca5e10fce6ba9e8bab7e1064e132ea54`.
- Protected counts remained: personal observations 2, Watches 0, cancellation requests 0; plans 1, recommendations 8, evidence 117, tool traces 25; Xeno-canto media evidence 1,000; calendar accepted snapshots 1, event intents 1, outbox 1, attempts 2, dedupe 0; alert runtime settings 1, SMTP verification 2; catalog-media results 1,412 and runs 2.

This final section supersedes earlier intermediate rerun counts and the earlier frontend failure, which was repaired and subsequently passed.

## Post-unexpected-exception definitive rerun

A complete verification-only rerun on 2026-07-12 after the unexpected post-launch exception cleanup fix passed every non-review acceptance gate:

- Full Python: 737 passed, three snapshots passed, 86.37% coverage.
- Focused refresh/API/runner/orchestration: 37 passed, including unexpected `ValueError`, `KeyboardInterrupt`, and `SystemExit` cleanup invariants from `.10x/evidence/2026-07-12-normal-exit-process-group-proof.md`.
- Ruff and format passed all 160 Python files; MyPy passed 98 source files with one existing unchecked-body informational note.
- TypeScript passed; frontend passed 18 files/273 tests; production build and bundle audit passed with 12 configured names and 10 values absent. Vite emitted only the existing large MapLibre chunk advisory.
- SQLMesh unit tests passed 13/13. Static Soda parsing validated all 25 contracts.
- A fresh isolated copy at `/tmp/rufous-sqlmesh-final-unexpected` passed 13 SQLMesh tests, materialized its copied `dev` layer, and passed all 25/25 rewritten Soda contracts. No project warehouse or SQLMesh state was applied.
- Secret scan, staging/platform-health generators, 20-file docs check, strict MkDocs build, all 11 pre-commit hooks, `git diff --check`, and no-staged-file check passed.
- Final read-only API inspection returned 706 unique catalog identities, 1,575 encounters, 152 exact encounter/photo identities, 139 available photos, and 13 placeholders. Every map photo equaled its catalog photo and every available scientific identity matched.
- Exact protected hashes remained warehouse `ca7ad49d4edc7c34b96f83944e7f3f5b748b84203b844205a666e309ca87a159`, SQLMesh state `c4995254709053ebffabcc16fbfe235e1d47b93208a7a1b1a81bb77b75852a93`, and `.env` `37d7aa746dc98317e521698210187070ca5e10fce6ba9e8bab7e1064e132ea54`.
- Protected counts remained personal observations 2, Watches 0, cancellation requests 0; plans 1, recommendations 8, evidence 117, tool traces 25; Xeno-canto media evidence 1,000; calendar accepted snapshots 1, event intents 1, outbox 1, attempts 2, dedupe 0; alert runtime settings 1, SMTP verification 2; catalog-media results 1,412 and runs 2.

This section supersedes all earlier aggregate test counts. No implementation file was edited during this verification-only rerun.

## Limits

No physical browser, MapLibre paint inspection, touch, 320-pixel viewport, zoomed text, forced colors, screen reader, or other assistive technology was used. JSDOM/source tests do not prove visual polish or announcement quality. No live refresh or provider-backed process-kill integration ran; process-group verification used bounded temporary non-provider processes only.

## Post-review status

Final correctness, privacy/security/source, and UX/accessibility reviews passed. Architecture found no implementation defect and requested only current-state record reconciliation; the parent and verification records were reconciled before the final architecture rerun. This note supersedes earlier statements that four reviews remained.
