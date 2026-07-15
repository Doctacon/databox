Status: recorded
Created: 2026-07-14
Updated: 2026-07-14
Relates-To: .10x/tickets/done/2026-07-12-derive-source-ci-from-registry.md, .10x/specs/registry-derived-source-verification.md

# Registry-derived source CI evidence

## What was observed

GitHub Actions source verification now derives from the canonical Python `SOURCES` registry rather than three hand-maintained source filters/jobs.

`python scripts/source_ci.py matrix` validates registry/package/domain/profile/test-artifact coherence and emits this deterministic source order:

1. AVONET — `file_snapshot`
2. eBird — `http`
3. GBIF — `http`
4. NOAA — `http`
5. USGS — `http`
6. USGS Earthquakes — `http`
7. Xeno-canto — `http`

The workflow's `source-matrix` job runs root-level shared source-harness tests offline, passes the validated JSON through a job output, and the `tests-sources` job consumes it with `fromJSON(...)`. Source jobs use independent runners, `fail-fast: false`, recording disabled, and provider network blocked.

The old `src_ebird`/`src_noaa`/`src_usgs` filters and `tests-ebird`/`tests-noaa`/`tests-usgs` jobs are absent. One broad `source_related` filter covers every source package/test path plus canonical registry, destinations, orchestration, scripts, top-level tests, workflow files, and dependency/task configuration. A source-related change therefore runs the complete registry matrix.

The aggregate coverage job retains one core coverage process, then invokes `python scripts/source_ci.py coverage`. That command revalidates the contract, runs root-level shared source-harness tests once, and launches every registered source suite as a separate sequential `coverage run --append` process with recording disabled and provider network blocked.

## Procedure and results

### Matrix and contract

Commands:

- `.venv/bin/python scripts/source_ci.py matrix --pretty`
- `.venv/bin/python scripts/check_source_layout.py`

Results:

- deterministic seven-entry matrix with the profiles listed above;
- source contract: 7 ok, 0 skipped, 0 failing.

### Focused tests

Command:

`.venv/bin/pytest --no-cov -q tests/test_source_ci.py tests/test_check_source_layout.py tests/test_source_registry.py`

Result: **44 passed**.

Coverage includes:

- exact matrix contents and reverse-order determinism;
- automatic inclusion of a future registry entry;
- invalid-profile rejection;
- missing-profile-artifact rejection by both checker and matrix validation;
- unregistered source rejection;
- one isolated shared-harness coverage command plus one per registered source;
- AVONET, GBIF, USGS Earthquakes, and Xeno-canto path regression cases;
- shared registry/domain/destination/scaffold/workflow/dependency path cases;
- workflow `fromJSON` consumption and absence of manual source jobs;
- all workflow action uses remain pinned to 40-character commit SHAs.

### Isolated source coverage execution

Command:

`COVERAGE_FILE=/tmp/databox-source-ci-coverage .venv/bin/python scripts/source_ci.py coverage`

Result: root-level shared source-harness tests and every registry source ran in separate deterministic processes, with all **58 source tests passing**:

- shared VCR sanitization: 2
- AVONET: 27
- eBird: 4
- GBIF: 6
- NOAA: 4
- USGS: 4
- USGS Earthquakes: 4
- Xeno-canto: 7

No provider request occurred; every command included `--record-mode=none --block-network`.

### Static and workflow checks

- Ruff format/check: passed for source CI/checker/tests.
- MyPy with workspace package roots: success for 4 files.
- Workflow YAML parsed successfully: 12 jobs.
- Workflow action pin inspection: all 24 `uses` entries are commit pinned.
- The matrix-generation job explicitly runs root-level `test_*.py` source-harness tests offline before emitting the matrix.
- `git diff --check`: passed.
- `git diff --cached --name-only`: empty.

## What this supports

This supports registry-derived matrix determinism, complete all-source routing for source-related changes, profile-contract failure semantics, independent source VCR processes, registry-derived aggregate source coverage, and preservation of workflow action pinning.

## Limits

- Local checks parse workflow YAML and inspect expressions/pins but do not execute GitHub-hosted event expressions, `dorny/paths-filter` diff calculation, runner provisioning, or job-output transport. The actual GitHub Actions run remains the integration proof.
- The isolated coverage execution intentionally used a temporary coverage file and did not run the core suite or evaluate the final 70% aggregate threshold; aggregate verification owns the full combined gate.
- No provider call, fixture recording, source refresh, SQLMesh command, Dagster job, shared warehouse connection, or runtime-data mutation occurred.
