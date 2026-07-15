Status: done
Created: 2026-07-12
Updated: 2026-07-12

# Single source contract and CI architecture

## Question

How should Databox implement the first improvement from `.10x/research/2026-07-12-dlt-sqlmesh-dagster-improvement-assessment.md`: one enforceable source contract with complete CI coverage?

## Sources and methods

### Repository inspection

Inspected the current source declarations, factories, scaffolding, tests, and CI:

- `packages/databox/databox/config/sources.py`
- `packages/databox/databox/config/pipeline_config.py`
- `packages/databox-sources/databox_sources/registry.py`
- `packages/databox-sources/databox_sources/base.py`
- all per-source `config.yaml` files and Dagster domain modules
- `scripts/new_source.py` and `scripts/check_source_layout.py`
- `packages/databox-sources/README.md`
- `.github/workflows/ci.yaml`
- current per-source tests and `.10x/knowledge/dlt-vcr-http-client-isolation.md`

### External documentation

- dlt schema contracts: https://dlthub.com/docs/general-usage/schema-contracts
- dlt source behavior: https://dlthub.com/docs/general-usage/source
- dlt resource behavior: https://dlthub.com/docs/general-usage/resource
- GitHub Actions matrix jobs: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations
- GitHub Actions workflow syntax and path filters: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax

The globally installed `turbo-search` executable was broken because its installed Python package was unavailable. The repository fallback was inspected; no clearly identified dlt, Dagster, or GitHub Actions namespace existed, so no namespace was invented and official documentation was used directly.

No source refresh, provider request, Dagster run, SQLMesh plan, warehouse write, or CI mutation was performed during research.

## Findings

### The Python `SOURCES` registry is the active operational authority

`packages/databox/databox/config/sources.py` currently drives shared refresh eligibility, raw table inspection, freshness, SQLMesh gateway catalogs, source smoke behavior, and registry/domain coherence tests. Active specifications and source comments already describe it as the single declaration for dataset-agnostic behavior.

The generic YAML `PipelineConfig` path is a partial legacy architecture:

- `databox_sources.registry` discovers YAML and creates `PipelineSource` wrappers, but no active production entrypoint consumes that registry.
- Generic `quality_rules` feed `databox.quality.engine`, but that engine has no active caller and targets a Psycopg/Postgres-style path rather than the current local DuckDB/Quack architecture.
- Dagster domain modules construct dlt sources directly and repeat YAML parameters rather than consuming them.
- AVONET's `config.yaml` is a real pinned-source manifest with a different schema and must not be treated as equivalent to the generic pipeline YAML shape.

Making generic YAML canonical would reactivate and expand a second configuration system. Keeping both authorities and merely validating parity would preserve ongoing duplication. The smallest durable architecture is to keep the Python `Source` registry canonical, remove the unused generic registry/protocol/config/quality-engine path, preserve AVONET's source-specific pinned manifest, and make each domain module expose one local source factory so definition-time and runtime construction cannot drift.

### CI can be registry-derived without fragile hand-maintained path entries

GitHub Actions supports a matrix supplied by an earlier job's JSON output through `fromJSON(...)`. A repository script can emit the current source names and test profiles from the Python registry; the workflow can use that output for one source-test matrix. This is preferable to seven hand-maintained path filters because adding a registry entry automatically creates a test job.

For this repository's small source count, the robust trigger is broad: any source package, orchestration domain, source registry, source test harness, source scaffold, or CI workflow change runs the entire registry-derived source matrix. Fine-grained changed-source optimization is unnecessary and risks recreating the current omission bug.

The existing all-workspace coverage job should also include every registered source test directory. Source shards should remain isolated because the active VCR knowledge record documents cross-source dlt HTTP-client/cassette contamination in a shared pytest process.

### Test obligations need profiles, not exceptions hidden in CI

A single contract does not mean every provider uses identical mechanics. The registry should declare a small test profile:

- `http`: resource behavior, offline VCR replay, schema snapshot, repeat-run/idempotency, and in-memory pipeline smoke;
- `file_snapshot`: deterministic parser/resource behavior, schema validation, idempotency/atomic publication, and smoke using bounded local fixtures;
- any future profile requires an explicit code-reviewed contract addition rather than ad hoc missing files.

Current gaps:

- eBird, NOAA, and USGS have the mature HTTP suite.
- GBIF and Xeno-canto have resource tests based on bespoke request mocks but lack VCR schema/idempotency/smoke coverage.
- USGS Earthquakes has no source-package test directory.
- AVONET has resource/idempotency tests but needs its file-source obligations made explicit rather than forced into HTTP/VCR mechanics.

Creating protective VCR cassettes for uncovered HTTP sources requires bounded live metadata requests. Those requests can be isolated from the warehouse and must not run a source refresh, but they still require explicit authorization because they contact external providers and may use the local Xeno-canto credential.

### dlt runtime schema evolution is a separate behavioral decision

Official dlt documentation supports `evolve`, `freeze`, `discard_row`, and `discard_value` contracts at source, resource, and pipeline levels. Changing from the current behavior to `freeze` or discard semantics would alter ingestion failure/data-loss behavior. It is not required to solve registry/CI drift and should be excluded from this work unless separately ratified.

## Options considered

### A. Canonical Python registry; retire generic legacy config (recommended)

- Enrich `Source` with module/factory identity and test profile where needed.
- Use one local source builder per domain module to remove duplicated constructor arguments.
- Dynamically compose or mechanically validate Dagster definitions from the registry.
- Remove unused `PipelineSource`, generic registry, generic pipeline config, dead quality engine, and generic YAML files.
- Preserve AVONET's pinned source manifest as source-specific configuration.
- Derive source CI matrix and contract validation from `SOURCES`.

This minimizes active systems and aligns with existing operational authority.

### B. Make generic YAML canonical

Standardize AVONET into the generic schema, have Dagster consume YAML, and derive the Python registry from YAML. This offers editable data files but increases runtime indirection, revives a currently dead subsystem, and makes typed/callable behavior harder to validate.

### C. Keep both and add parity checks

Least disruptive initially, but retains duplicate authority and makes every new field a permanent synchronization obligation. Rejected as a durable target.

## Recommendation

Approve Option A with these boundaries:

1. One canonical Python source registry for operational identity, raw tables, cadence flags, freshness, source factory identity, and test profile.
2. One local source builder per Dagster domain; no repeated constructor literals inside a domain.
3. Registry-derived source contract validation and GitHub Actions matrix covering all seven active sources.
4. Uniform profile-based offline tests; bounded live provider calls only to capture missing sanitized VCR cassettes if separately authorized.
5. No source refresh, warehouse mutation, SQLMesh model change, Dagster schedule behavior change, or dlt schema-evolution policy change.

## Limits

- The exact dlt schema snapshot produced by GBIF, Xeno-canto, and USGS Earthquakes cannot be honestly recorded without either bounded provider-backed cassette capture or a user-ratified weaker mock-only contract.
- Dynamic Dagster asset construction details still need implementation-level validation against the installed Dagster/dagster-dlt versions; the contract may retain thin per-domain modules if fully dynamic composition introduces import-time instability.
