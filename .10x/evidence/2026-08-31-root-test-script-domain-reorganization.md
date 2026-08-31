Status: recorded
Created: 2026-08-31
Updated: 2026-08-31
Relates-To: .10x/tickets/2026-08-31-organize-root-tests-and-scripts-by-domain.md

# Root test and script domain reorganization evidence

## What was observed

The behavior-preserving reorganization moved all 70 tracked Python modules that were directly under root `tests/`, all 39 tracked files directly under root `scripts/`, and five owned template files. The resulting root directories contain zero directly nested regular files.

Final domain inventory:

| Root | Domain | Files counted |
| --- | --- | ---: |
| tests | analytics | 5 test modules |
| tests | birding | 21 test modules |
| tests | cloudflare | 3 test modules |
| tests | evals | 1 test module |
| tests | platform | 7 test modules, including the new layout guard |
| tests | rufous_media | 22 test modules |
| tests | sources | 13 test modules |
| scripts | analytics | 4 files including the staging template |
| scripts | birding | 6 files |
| scripts | cloudflare | 1 file |
| scripts | operations | 3 files |
| scripts | platform | 5 files |
| scripts | rufous_media | 16 files |
| scripts | sources | 9 files including four source templates |

Every Taskfile, workflow, hook, scaffold, active documentation, code-string contract, runtime filesystem lookup, test import, and relevant active path reference found by the bounded scan was updated to its new canonical path. Repository-root calculations based on `__file__` were adjusted for the extra directory level. The staging and source templates moved beside their owning domain scripts.

`tests/platform/test_repository_layout.py` now rejects test modules directly under `tests/`, rejects Python/shell/SQL scripts directly under `scripts/`, and rejects unratified top-level domain directories. It also verifies the two template ownership seams.

## Complete move map

### Root tests

- `tests/test_analytics_contract_inventory.py` → `tests/analytics/test_analytics_contract_inventory.py`
- `tests/test_avonet_catalog_models.py` → `tests/sources/test_avonet_catalog_models.py`
- `tests/test_avonet_orchestration.py` → `tests/sources/test_avonet_orchestration.py`
- `tests/test_fact_bird_observation.py` → `tests/analytics/test_fact_bird_observation.py`
- `tests/test_metrics.py` → `tests/analytics/test_metrics.py`
- `tests/test_openlineage_sensor.py` → `tests/analytics/test_openlineage_sensor.py`
- `tests/test_staging_codegen.py` → `tests/analytics/test_staging_codegen.py`
- `tests/test_api.py` → `tests/birding/test_api.py`
- `tests/test_arizona_boundary_artifact.py` → `tests/birding/test_arizona_boundary_artifact.py`
- `tests/test_arizona_boundary.py` → `tests/birding/test_arizona_boundary.py`
- `tests/test_bird_alert_delivery.py` → `tests/birding/test_bird_alert_delivery.py`
- `tests/test_bird_alert_outbox.py` → `tests/birding/test_bird_alert_outbox.py`
- `tests/test_bird_catalog_api.py` → `tests/birding/test_bird_catalog_api.py`
- `tests/test_birding_trip_planner.py` → `tests/birding/test_birding_trip_planner.py`
- `tests/test_catalog_media.py` → `tests/birding/test_catalog_media.py`
- `tests/test_curated_photo.py` → `tests/birding/test_curated_photo.py`
- `tests/test_map_snapshot_api.py` → `tests/birding/test_map_snapshot_api.py`
- `tests/test_open_meteo_geocoding.py` → `tests/birding/test_open_meteo_geocoding.py`
- `tests/test_open_meteo_tool.py` → `tests/birding/test_open_meteo_tool.py`
- `tests/test_personal_collection_api.py` → `tests/birding/test_personal_collection_api.py`
- `tests/test_place_suggestions.py` → `tests/birding/test_place_suggestions.py`
- `tests/test_recommendation_media_backfill.py` → `tests/birding/test_recommendation_media_backfill.py`
- `tests/test_recommendation_media.py` → `tests/birding/test_recommendation_media.py`
- `tests/test_remove_wishlist.py` → `tests/birding/test_remove_wishlist.py`
- `tests/test_target_planning.py` → `tests/birding/test_target_planning.py`
- `tests/test_trip_plan_calendar.py` → `tests/birding/test_trip_plan_calendar.py`
- `tests/test_trip_plan_privacy_remediation.py` → `tests/birding/test_trip_plan_privacy_remediation.py`
- `tests/test_watched_bird_evaluator.py` → `tests/birding/test_watched_bird_evaluator.py`
- `tests/test_cloudflare_workers_ai.py` → `tests/cloudflare/test_cloudflare_workers_ai.py`
- `tests/test_rufous_ai_workflow.py` → `tests/cloudflare/test_rufous_ai_workflow.py`
- `tests/test_smoke_cloudflare_ai.py` → `tests/cloudflare/test_smoke_cloudflare_ai.py`
- `tests/test_bootstrap.py` → `tests/platform/test_bootstrap.py`
- `tests/test_check_secrets.py` → `tests/platform/test_check_secrets.py`
- `tests/test_docs_navigation.py` → `tests/platform/test_docs_navigation.py`
- `tests/test_schema_gate.py` → `tests/platform/test_schema_gate.py`
- `tests/test_settings.py` → `tests/platform/test_settings.py`
- `tests/test_verify_dev.py` → `tests/platform/test_verify_dev.py`
- `tests/test_check_source_layout.py` → `tests/sources/test_check_source_layout.py`
- `tests/test_ebird_models.py` → `tests/sources/test_ebird_models.py`
- `tests/test_new_source.py` → `tests/sources/test_new_source.py`
- `tests/test_parallel_refresh.py` → `tests/sources/test_parallel_refresh.py`
- `tests/test_quack_destinations.py` → `tests/sources/test_quack_destinations.py`
- `tests/test_source_builders.py` → `tests/sources/test_source_builders.py`
- `tests/test_source_ci.py` → `tests/sources/test_source_ci.py`
- `tests/test_source_modeling_contract.py` → `tests/sources/test_source_modeling_contract.py`
- `tests/test_source_refresh_api.py` → `tests/sources/test_source_refresh_api.py`
- `tests/test_source_refresh_runner.py` → `tests/sources/test_source_refresh_runner.py`
- `tests/test_source_registry.py` → `tests/sources/test_source_registry.py`
- `tests/test_audit_app_bundle.py` → `tests/rufous_media/test_audit_app_bundle.py`
- `tests/test_public_audio_export.py` → `tests/rufous_media/test_public_audio_export.py`
- `tests/test_public_audio_release.py` → `tests/rufous_media/test_public_audio_release.py`
- `tests/test_public_audio_selection.py` → `tests/rufous_media/test_public_audio_selection.py`
- `tests/test_public_avonet_model.py` → `tests/rufous_media/test_public_avonet_model.py`
- `tests/test_public_export_audit.py` → `tests/rufous_media/test_public_export_audit.py`
- `tests/test_public_export.py` → `tests/rufous_media/test_public_export.py`
- `tests/test_public_inaturalist_media_ingest.py` → `tests/rufous_media/test_public_inaturalist_media_ingest.py`
- `tests/test_public_media_approval.py` → `tests/rufous_media/test_public_media_approval.py`
- `tests/test_public_media_delta.py` → `tests/rufous_media/test_public_media_delta.py`
- `tests/test_public_media_ingest.py` → `tests/rufous_media/test_public_media_ingest.py`
- `tests/test_public_media_pin.py` → `tests/rufous_media/test_public_media_pin.py`
- `tests/test_public_media_release.py` → `tests/rufous_media/test_public_media_release.py`
- `tests/test_public_media_review.py` → `tests/rufous_media/test_public_media_review.py`
- `tests/test_public_media.py` → `tests/rufous_media/test_public_media.py`
- `tests/test_public_release_hydrate.py` → `tests/rufous_media/test_public_release_hydrate.py`
- `tests/test_public_release.py` → `tests/rufous_media/test_public_release.py`
- `tests/test_public_wikimedia_media_ingest.py` → `tests/rufous_media/test_public_wikimedia_media_ingest.py`
- `tests/test_rufous_pinned_public_media.py` → `tests/rufous_media/test_rufous_pinned_public_media.py`
- `tests/test_rufous_public_workflow.py` → `tests/rufous_media/test_rufous_public_workflow.py`
- `tests/test_rufous_theme.py` → `tests/rufous_media/test_rufous_theme.py`
- `tests/test_rufous_wikimedia_public_media.py` → `tests/rufous_media/test_rufous_wikimedia_public_media.py`

### Root scripts and templates

- `scripts/generate_platform_health.py` → `scripts/analytics/generate_platform_health.py`
- `scripts/generate_staging.py` → `scripts/analytics/generate_staging.py`
- `scripts/sqlmesh_plan_prod.sh` → `scripts/analytics/sqlmesh_plan_prod.sh`
- `scripts/catalog_media.py` → `scripts/birding/catalog_media.py`
- `scripts/deliver_bird_alerts.py` → `scripts/birding/deliver_bird_alerts.py`
- `scripts/remediate_trip_planner_ebird_privacy.py` → `scripts/birding/remediate_trip_planner_ebird_privacy.py`
- `scripts/remove_wishlist_storage.py` → `scripts/birding/remove_wishlist_storage.py`
- `scripts/run_local_app.py` → `scripts/birding/run_local_app.py`
- `scripts/verify_bird_alert_smtp.py` → `scripts/birding/verify_bird_alert_smtp.py`
- `scripts/smoke_cloudflare_ai.py` → `scripts/cloudflare/smoke_cloudflare_ai.py`
- `scripts/run-logged.sh` → `scripts/operations/run-logged.sh`
- `scripts/setup_db_roles.sql` → `scripts/operations/setup_db_roles.sql`
- `scripts/setup_pre_commit.sh` → `scripts/operations/setup_pre_commit.sh`
- `scripts/bootstrap.py` → `scripts/platform/bootstrap.py`
- `scripts/check_secrets.py` → `scripts/platform/check_secrets.py`
- `scripts/generate_docs.py` → `scripts/platform/generate_docs.py`
- `scripts/schema_gate.py` → `scripts/platform/schema_gate.py`
- `scripts/verify_dev.py` → `scripts/platform/verify_dev.py`
- `scripts/apply_rufous_media_delta.py` → `scripts/rufous_media/apply_rufous_media_delta.py`
- `scripts/audit_app_bundle.py` → `scripts/rufous_media/audit_app_bundle.py`
- `scripts/audit_rufous_public.py` → `scripts/rufous_media/audit_rufous_public.py`
- `scripts/build_rufous_media_review.py` → `scripts/rufous_media/build_rufous_media_review.py`
- `scripts/compose_rufous_media_pin.py` → `scripts/rufous_media/compose_rufous_media_pin.py`
- `scripts/export_rufous_public.py` → `scripts/rufous_media/export_rufous_public.py`
- `scripts/hydrate_rufous_public.py` → `scripts/rufous_media/hydrate_rufous_public.py`
- `scripts/load_rufous_usfws_media.py` → `scripts/rufous_media/load_rufous_usfws_media.py`
- `scripts/load_rufous_wikimedia_media.py` → `scripts/rufous_media/load_rufous_wikimedia_media.py`
- `scripts/prepare_rufous_media.py` → `scripts/rufous_media/prepare_rufous_media.py`
- `scripts/publish_rufous_media.py` → `scripts/rufous_media/publish_rufous_media.py`
- `scripts/publish_rufous_public.py` → `scripts/rufous_media/publish_rufous_public.py`
- `scripts/sqlmesh_plan_rufous_inaturalist_media.sh` → `scripts/rufous_media/sqlmesh_plan_rufous_inaturalist_media.sh`
- `scripts/sqlmesh_plan_rufous_media.sh` → `scripts/rufous_media/sqlmesh_plan_rufous_media.sh`
- `scripts/sqlmesh_plan_rufous_public.sh` → `scripts/rufous_media/sqlmesh_plan_rufous_public.sh`
- `scripts/verify_rufous_media_approvals.py` → `scripts/rufous_media/verify_rufous_media_approvals.py`
- `scripts/check_source_layout.py` → `scripts/sources/check_source_layout.py`
- `scripts/check_source_modeling.py` → `scripts/sources/check_source_modeling.py`
- `scripts/load_dlt_quack.py` → `scripts/sources/load_dlt_quack.py`
- `scripts/new_source.py` → `scripts/sources/new_source.py`
- `scripts/source_ci.py` → `scripts/sources/source_ci.py`
- `scripts/templates/staging.sql.j2` → `scripts/analytics/templates/staging.sql.j2`
- `scripts/templates/source/common/__init__.py.j2` → `scripts/sources/templates/source/common/__init__.py.j2`
- `scripts/templates/source/common/domain.py.j2` → `scripts/sources/templates/source/common/domain.py.j2`
- `scripts/templates/source/file/source.py.j2` → `scripts/sources/templates/source/file/source.py.j2`
- `scripts/templates/source/rest/source.py.j2` → `scripts/sources/templates/source/rest/source.py.j2`

## Procedure and results

### Structural and reference checks

- A generated check over the 114-entry move map reported `missing_new=0` and `remaining_old=0`.
- `find tests -maxdepth 1 -type f` and `find scripts -maxdepth 1 -type f` both returned no paths.
- The exact old-path scan covered tracked and non-ignored untracked text files while excluding terminal tickets/evidence/reviews/research, superseded decisions/specs, and generated `site/`. It found no active stale implementation reference. One deliberate historical citation of `HEAD:scripts/check_source_layout.py` exists in the separately opened baseline-drift ticket.
- A hidden-file scan found no stale root Rufous script wildcard, root public/Rufous test wildcard, or root public-audio test command.
- The only remaining `scripts/templates/source/...` strings are four intentional retired-authority paths and their executable regression assertions; those paths did not exist before this move and remain prohibited by the canonical-source checker.
- `uv run pytest --collect-only -q --no-cov` collected 1,492 pre-guard tests before the two-test repository layout guard was added. Collection completed without import errors.
- `git diff --check` passed.
- Final cleanup removed every `__pycache__` under `tests/` and `scripts/`; the final count was zero.
- `git reset` left all changes intentionally unstaged. `git diff --cached --name-only` returned zero paths.
- Because clean-break moves are untracked after unstaging, the final secret verification ran both `scripts/platform/check_secrets.py .` over 938 currently tracked existing files and an explicit scan over 119 untracked paths (114 eligible); both passed.

### Focused path-sensitive verification

`uv run pytest --no-cov` over the layout guard and path-sensitive platform, source contract/scaffold/CI/modeling, staging, bundle-audit, Rufous-workflow, and Cloudflare smoke test modules passed **198/198**.

This covered:

- direct-directory and domain membership;
- moved scripts loaded through `runpy`/`importlib`;
- source checker/scaffold sibling imports and templates;
- CI/Task/workflow command strings and path routing;
- staging template lookup;
- bundle audit root discovery;
- Rufous workflow path allowlists and command ordering;
- offline Cloudflare smoke harness loading.

### Static, docs, generation, and safety gates

Passed:

- `uv run ruff check .`
- `uv run ruff format --check .` — 247 files already formatted
- `uv run mypy packages/` — success for 140 source files
- `uv run python scripts/sources/check_source_modeling.py` — 8 registered sources complete
- `uv run python scripts/analytics/generate_staging.py --check`
- `uv run python scripts/analytics/generate_platform_health.py --check`
- `uv run python scripts/platform/generate_docs.py --check` — 24 dictionary files in sync
- `uv run mkdocs build --strict`
- `uv run python scripts/platform/check_secrets.py .` — 1,047 eligible files checked
- `git diff --check`

`mkdocs build --strict` generated only ignored `site/` output and emitted the existing Material for MkDocs future-version warning plus the existing generated-dictionary navigation notices.

### Complete default Python suite

`uv run pytest --block-network` completed with **1,491 passed, 3 failed, 7 snapshots passed, 84.89% coverage** in 112.81 seconds. The three deterministic failures were:

1. `tests/birding/test_birding_trip_planner.py::test_ebird_and_gbif_lookups_enforce_inside_boundary_and_outside_radius` — returned no rows.
2. `tests/rufous_media/test_public_wikimedia_media_ingest.py::test_loader_can_validate_against_hydrated_active_public_catalog` — fixture species `gbif-2476855` has an unsupported taxonomic category.
3. `tests/rufous_media/test_public_wikimedia_media_ingest.py::test_hydrated_public_catalog_mismatch_fails_before_table_replacement` — same category failure.

All three reproduce in a focused run. Both affected files are pure renames relative to `HEAD`; no body or relative-path logic in those tests changed in this ticket. The failures are recorded in `.10x/tickets/done/2026-08-31-repair-preexisting-default-python-test-failures.md` rather than widened into this layout change.

### Pre-existing source contract failure

Both the moved checker and the pre-change `HEAD:scripts/check_source_layout.py` fail identically for the registered explicit-target-only USFWS domain: the checker requires an unconfigured Dagster asset/job that the domain deliberately omits. Consequently:

- `uv run python scripts/sources/check_source_layout.py` fails with four USFWS asset/job requirements.
- `uv run python scripts/sources/source_ci.py matrix --pretty` fails on the same requirements.

The byte-for-byte pre-change checker was executed from `/tmp` with only its `PROJECT_ROOT` assignment adapted to the current working directory; it produced the same four failures and exit 1. This proves the failure predates the reorganization. `.10x/tickets/2026-08-31-reconcile-usfws-source-contract-checker.md` records the necessary separate contract decision.

## What this supports or challenges

This supports acceptance criteria 1–4 and 7 of the related ticket: all root files are grouped, discovery and path consumers work, no wrappers or duplicate implementations were added, and generated/runtime artifacts are not part of the change. Focused verification, static gates, docs, generators, and 1,491 passing network-blocked tests strongly support behavior preservation.

Acceptance criterion 5 is not fully supported because three pre-existing deterministic test failures remain. Acceptance criterion 6 is not fully supported because the pre-existing USFWS source-layout/matrix contract drift remains. Acceptance criterion 8 remains pending independent review. The ticket therefore remains active rather than being closed.

## Limits

- No live provider, `task full-refresh`, `task verify`, SQLMesh production plan, data migration, publication, SMTP action, browser deployment, or production-mutating workflow was run.
- Full Python verification does not prove browser runtime behavior; path-sensitive frontend command/audit contracts passed, but the frontend build/test suite was not rerun because no frontend source changed.
- The three Python failures and USFWS checker failure are proven to be outside the changed behavioral seams, but the default suite and source contract remain red until their dedicated tickets are resolved.
- Independent reviewer confirmation is not part of this implementation evidence and remains required before closure.

## Review repair supplement — 2026-08-31

The independent review found two ticket-scoped defects after the initial evidence above was recorded:

1. All four moved SQLMesh shell scripts still resolved the repository as one level above their new domain directory, producing `scripts/` rather than the repository root.
2. `test_metrics.py` was initially allocated to `analytics/` even though the user-ratified taxonomy explicitly places metrics in `platform/`.

Both findings were repaired without touching the separately ticketed baseline failures.

### Final allocation correction

The original move-map row remains above as evidence of the initial implementation. Its final allocation is superseded by:

- `tests/test_metrics.py` → `tests/platform/test_metrics.py`

This supersedes the initial inventory counts for those two domains: the final root-test allocation is 4 modules under `tests/analytics/` and 8 under `tests/platform/` (including the layout guard). The total remains 72 test modules across root domain directories.

`docs/metrics.md` now points to the final canonical path for both maintenance and focused execution. An active-reference scan found no remaining `tests/test_metrics.py` or `tests/analytics/test_metrics.py` reference outside terminal/historical evidence.

### SQLMesh root-resolution repair

These scripts now resolve two levels above their domain directories with `$(dirname "${BASH_SOURCE[0]}")/../..`:

- `scripts/analytics/sqlmesh_plan_prod.sh`
- `scripts/rufous_media/sqlmesh_plan_rufous_inaturalist_media.sh`
- `scripts/rufous_media/sqlmesh_plan_rufous_media.sh`
- `scripts/rufous_media/sqlmesh_plan_rufous_public.sh`

`tests/platform/test_repository_layout.py` gained a non-mutating parameterized regression. Each script is copied into an isolated temporary repository containing fake `.venv/bin/python` and `.venv/bin/sqlmesh` executables. The test executes the copied script and proves that every plan runs from `<temporary-repository>/transforms/main` through the fake SQLMesh binary. The production planner's fake Python exits 1 so it exercises only the new-production branch and never opens a state database. No real SQLMesh plan, warehouse, provider, or production path is invoked.

### Review-repair verification

Passed:

- `uv run pytest --no-cov tests/platform/test_repository_layout.py tests/platform/test_metrics.py` — 10/10 tests.
- `uv run ruff check tests/platform/test_repository_layout.py tests/platform/test_metrics.py`.
- `uv run ruff format --check tests/platform/test_repository_layout.py tests/platform/test_metrics.py`.
- `bash -n` over all four repaired SQLMesh shell scripts.
- Active-reference scan for both superseded metrics-test paths.
- `git diff --check`.
- `uv run pytest --collect-only -q --no-cov` — 1,498 tests collected without import or duplicate-module errors.
- Repository-wide `uv run ruff check .` and `uv run ruff format --check .` — passed; 247 files formatted.
- `uv run mkdocs build --strict` — passed with the previously recorded Material future-version warning and generated-dictionary nav notices.
- `scripts/platform/check_secrets.py` — passed over 938 tracked existing files plus 114 eligible untracked moved/record files.

The previously recorded three default-suite failures and USFWS source-contract failure were not changed or rerun as part of this bounded review repair. Their dedicated tickets remain the accurate residual-risk records.
