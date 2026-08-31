Status: recorded
Created: 2026-08-31
Updated: 2026-08-31
Relates-To: .10x/tickets/done/2026-08-31-reconcile-usfws-source-contract-checker.md, .10x/specs/canonical-dlt-source-registry.md, .10x/specs/registry-derived-source-verification.md

# USFWS explicit-target source contract verification

## What was observed

The canonical registry now represents source orchestration separately from verification profile through `Source.orchestration_mode`. The supported modes are `default` and `explicit_targets`; USFWS declares `explicit_targets`, remains unscheduled, and remains excluded from shared parallel refresh.

The source-layout checker now validates both modes explicitly. For an `explicit_targets` source it requires:

- exactly one callable `_build_source`;
- no `<name>_dlt_assets` binding and no definition/asset-time `_build_source` call;
- `assets = []`;
- `dlt_asset_keys = []`;
- `ingest_job = None`;
- normal list-shaped `asset_checks` and `sqlmesh_asset_keys` exports;
- no schedule and no shared parallel-refresh eligibility.

It does not invent an implicit USFWS target set or add a default Dagster job. The existing `packages/databox/databox/orchestration/domains/usfws.py` safety behavior is unchanged.

Active source specifications and `docs/source-layout.md` now state the two orchestration modes, current eight-source inventory, and explicit-target safety constraints. The registry-derived verification specification now includes the current USFWS HTTP profile and eight-source matrix.

## Procedure and results

### Focused offline contract and USFWS suite

Command:

```text
uv run pytest --no-cov --block-network tests/sources/test_check_source_layout.py tests/sources/test_source_registry.py tests/sources/test_source_ci.py tests/sources/test_source_builders.py packages/databox-sources/tests/usfws
```

Result: **145 passed** in 7.14 seconds. No live provider request was allowed. New adversarial checker cases prove a valid explicit-target module passes and reject an unconfigured dlt asset, non-empty asset list, non-empty dlt key list, or Dagster ingest job. Registry tests reject invalid modes and explicit-target entries that are scheduled or parallel-refresh eligible.

### Live repository contract and deterministic matrix

Commands:

```text
uv run python scripts/sources/check_source_layout.py
uv run python scripts/sources/source_ci.py matrix --pretty
```

Results:

- checker: **8 ok, 0 incomplete, 0 failing, 0 registry errors**;
- matrix: deterministic eight entries (`avonet`, `ebird`, `gbif`, `noaa`, `usfws`, `usgs`, `usgs_earthquakes`, `xeno_canto`) with USFWS retaining the HTTP verification profile.

### Aggregate network-blocked Python verification

Command:

```text
uv run pytest --block-network
```

Result: **1,504 passed**, **7 snapshots passed**, **85.00% total coverage**, 0 failures in 107.45 seconds. This includes the USFWS profile suite, source checker/matrix tests, domain loading, and all default repository Python tests. The command confirms the earlier three fixture-drift failures were repaired by the preceding ticket.

### Static, documentation, and repository gates

Passed:

```text
uv run ruff check packages/databox/databox/config/sources.py scripts/sources/check_source_layout.py tests/sources/test_check_source_layout.py tests/sources/test_source_registry.py
uv run ruff format --check packages/databox/databox/config/sources.py scripts/sources/check_source_layout.py tests/sources/test_check_source_layout.py tests/sources/test_source_registry.py
uv run mypy packages/
uv run mkdocs build --strict
git diff --check
git diff --cached --quiet
```

Results: Ruff passed; all four focused Python files are formatted; MyPy passed 140 source files; strict documentation build passed with the existing Material 2.0 warning and generated-dictionary navigation notices; diff check passed; no files are staged. No `__pycache__` directory was found under the reorganized root `scripts/` or `tests/` trees.

## What this supports

This supports every acceptance criterion in `.10x/tickets/done/2026-08-31-reconcile-usfws-source-contract-checker.md`:

1. Registry, active specification, documentation, checker, and tests agree on the explicit-target orchestration mode.
2. The required source-layout and matrix commands pass for all eight registered sources.
3. Existing USFWS target ownership, offline source profile, and no-default-job behavior remain intact and are protected by positive and adversarial tests.
4. Complete network-blocked Python and relevant static/documentation gates pass.

## Limits

- No live provider request, source refresh, warehouse/database mutation, SQLMesh production plan, Dagster source job, media publication, deployment, or other production-changing command ran.
- Strict MkDocs emitted pre-existing warnings noted above; the build exited successfully.
- The repository contains the broader root test/script reorganization and preceding fixture repair in the same unstaged working tree. This evidence isolates the files and commands owned by this ticket but does not claim those broader diffs were authored here.

## Follow-up active-spec wording verification

A follow-up review identified two stale acceptance-scenario counts left after USFWS became the eighth active registry entry. The canonical existing-source scenario now says "eight active registry entries," and the registry-derived new-source scenario now says "future ninth source." No behavior, registry code, checker code, test code, or other specification wording changed in this follow-up.

Focused checks passed:

```text
rg -n "seven active registry entries|future eighth source" .10x/specs/canonical-dlt-source-registry.md .10x/specs/registry-derived-source-verification.md
uv run python - <<'PY'
from pathlib import Path
canonical = Path('.10x/specs/canonical-dlt-source-registry.md').read_text()
verification = Path('.10x/specs/registry-derived-source-verification.md').read_text()
assert 'exactly the eight current sources' in canonical
assert 'any of the eight active registry entries' in canonical
assert 'At eight sources' in verification
assert 'future ninth source' in verification
assert 'all eight active sources' in verification
PY
git diff --check
git diff --cached --quiet
```

The stale-reference scan returned no matches; the semantic assertions, diff check, and no-staged-files check all exited successfully.
