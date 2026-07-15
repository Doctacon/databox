Status: done
Created: 2026-07-12
Updated: 2026-07-12

# dlt, SQLMesh, and Dagster improvement assessment

## Question

What are the three highest-leverage improvements to Databox's current dlt ingestion, SQLMesh transformation, and Dagster orchestration stack?

## Sources and methods

This was a read-only architecture assessment. It inspected:

- active architecture/specification records under `.10x/`, especially `.10x/specs/parallel-quack-local-refresh.md` and `.10x/specs/local-only-databox-platform.md`;
- prior implementation evidence and reviews for the shared Quack refresh and CDM workflow;
- `packages/databox-sources/databox_sources/` and its source tests;
- `packages/databox/databox/orchestration/`, source registries, and pipeline configuration;
- `transforms/main/`, SQLMesh tests, and Soda contracts;
- `scripts/load_dlt_quack.py`, `scripts/sqlmesh_plan_prod.sh`, `Taskfile.yaml`, and `.github/workflows/ci.yaml`.

No provider requests, source refresh, SQLMesh plan, Dagster run, or warehouse mutation was performed.

## Findings

### 1. Source definitions and source CI are not governed by one enforceable contract

The repository currently has overlapping declarations:

- `packages/databox/databox/config/sources.py` is documented as the one source registry;
- each source also has `packages/databox-sources/databox_sources/<source>/config.yaml`;
- `packages/databox-sources/databox_sources/registry.py` discovers those YAML files through a separate registry;
- each Dagster domain module repeats source parameters both at definition time and execution time;
- `packages/databox/databox/orchestration/definitions.py` manually imports and registers each source.

The CI matrix is materially incomplete for the current registry. `.github/workflows/ci.yaml` has explicit path routing and test jobs only for eBird, NOAA, and USGS. It has no path-routing entries or source-test jobs for AVONET, GBIF, USGS Earthquakes, or Xeno-canto. The aggregate coverage job also executes only core, eBird, NOAA, and USGS tests. A pull request touching only one of the omitted source directories can therefore avoid the heavy source gates, and those source packages do not participate in the aggregate coverage run.

Test contracts are inconsistent. eBird, NOAA, and USGS have resource, schema-snapshot, idempotency, and smoke tests. GBIF and Xeno-canto have resource-level tests only; USGS Earthquakes has no source-package test directory; AVONET has resource/idempotency tests but no equivalent schema/smoke suite.

### 2. The operational refresh is not represented as one coherent Dagster asset execution

The proven shared-Quack safety mechanism should remain, but its Dagster representation is opaque:

- `parallel_quack_full_refresh` is a one-op Dagster job;
- that op runs `execute_parallel_refresh`, which starts a Quack server and launches nested `dg launch` subprocesses for source jobs;
- SQLMesh then runs through `scripts/sqlmesh_plan_prod.sh`, outside Dagster's SQLMesh asset materialization path;
- the routine refresh therefore does not directly materialize the registered SQLMesh assets or execute the registered Soda asset checks as one observable, gating run.

The available schedule topology is also ambiguous. Six per-source schedules and the aggregate parallel refresh schedule are all registered at `0 6 * * *`. They are not necessarily enabled by default, but enabling overlapping schedules can duplicate provider calls and compete with the single-writer/shared-Quack contract. This also conflicts with the current product-level explicit-confirmation refresh workflow unless operators understand which schedule, if any, owns routine execution.

The architecture documentation promises end-to-end Dagster lineage, quality gating, schedules, and backfills more strongly than the routine full-refresh implementation currently provides.

### 3. SQLMesh rebuilds the modeled layer rather than exploiting incremental planning and production audits

The current SQLMesh project contains 18 models: 13 `FULL` models and 5 `VIEW` models. There are no incremental models and no SQLMesh audit files. `scripts/sqlmesh_plan_prod.sh` applies a prod plan and then performs `--restate-model "*"` whenever prod already exists, so every routine successful source refresh deliberately restates the entire model graph.

This is simple and currently viable, but it gives up two reasons recorded for choosing SQLMesh in `docs/adr/0002-sqlmesh-over-dbt.md`: incremental time-partitioned models and model-level audits. Temporal facts such as bird observations, weather observations, streamflow, regional daily statistics, and earthquakes are natural incremental/backfill boundaries.

There are 13 named SQLMesh unit-test cases, but seven current models have no directly named SQLMesh unit test: platform health, three dimensions, and three temporal facts. Soda contracts are broad, but CI validates only their YAML structure, and the routine full-refresh path does not execute the registered live Soda asset checks after its native SQLMesh CLI run.

## Conclusions

The three highest-leverage improvements, in recommended order, are:

1. **Create one executable source contract and derive CI from it.** Consolidate source identity, parameters, cadence, raw tables, and test obligations into one authoritative manifest/factory. Require every registered source to pass the same schema, idempotency, smoke, and orchestration contract. Generate or validate CI routing against the registry so a source cannot exist outside CI.
2. **Make the safe full refresh one coherent Dagster-observable workflow with one schedule owner.** Preserve the one-Quack-server/process-isolation mechanics, but expose source outcomes, SQLMesh materializations, and Soda checks as one run with explicit dependencies and failure gates. Retire or clearly separate competing per-source schedules from the aggregate schedule and the user-confirmed refresh path.
3. **Adopt incremental SQLMesh models and executable production quality gates.** Convert time-based facts first, retain full snapshot dimensions where appropriate, stop wildcard-restating the whole graph, add model audits/unit tests at semantic boundaries, and run live Soda/SQLMesh checks after modeled publication.

## Limits

- This assessment did not run a live refresh or benchmark current data volumes. Incrementalization is justified by architecture and growth behavior, not a measured present-day performance incident.
- Dagster schedules were inspected as definitions only; their local enabled/disabled state was not read or changed.
- The existing shared-Quack implementation has strong recorded correctness evidence. The recommendation is to improve its orchestration representation, not to replace its concurrency safety with unproven direct DuckDB writers.
