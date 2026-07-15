Status: active
Created: 2026-07-12
Updated: 2026-07-12

# Python source registry as the canonical ingestion contract

## Context

Databox currently has overlapping source declarations:

- the active Python `SOURCES` registry in `packages/databox/databox/config/sources.py`;
- generic per-source YAML loaded through `PipelineConfig`;
- an auto-discovered `databox_sources.registry` and `PipelineSource` protocol;
- repeated constructor arguments in Dagster domain modules;
- manual source imports and list entries in Dagster `Definitions`;
- manually enumerated GitHub Actions source paths and test jobs.

The Python registry is the only declaration already used by the shared Quack refresh, raw-table inspection, freshness mapping, SQLMesh catalogs, smoke behavior, and registry/domain coherence tests. The generic YAML registry and its Psycopg quality engine are not on an active production path. AVONET's YAML is different: it is a pinned-source manifest containing version, checksum, size, and publication invariants.

This duplication allowed four active sources—AVONET, GBIF, Xeno-canto, and USGS Earthquakes—to exist outside the explicit source CI routing and aggregate source-test coverage.

The architecture options and official dlt/GitHub Actions research are recorded in `.10x/research/2026-07-12-single-source-contract-and-ci-architecture.md`.

## Decision

1. `packages/databox/databox/config/sources.py` is the sole canonical registry for active ingestion-source identity and dataset-agnostic operational metadata.
2. Each source record MUST own or derive its name, raw tables, freshness policy, scheduling eligibility, parallel-refresh eligibility, analytics-anchor role, domain-module identity, and verification profile.
3. Source-specific constructor parameters MUST have exactly one executable owner in the source's Dagster domain module. Definition-time and execution-time dlt source construction MUST call the same local builder.
4. Dagster source composition and source CI enumeration MUST derive from the canonical registry. Adding a source MUST NOT require manually adding its name to Dagster `Definitions` lists or a GitHub Actions source list.
5. The unused generic `PipelineConfig`, `PipelineSource`, source auto-registry, generic quality engine, generic source YAML files, and legacy wrapper classes/factories will be retired when their remaining tests/docs are migrated.
6. AVONET's pinned source manifest remains source-specific configuration and is not converted into the retired generic pipeline YAML contract.
7. Verification obligations are profile-based. Current profiles are HTTP-provider and pinned-file snapshot. A future source requiring a new profile must add that profile explicitly to the canonical contract.
8. This decision does not change dlt runtime schema-evolution semantics. Adopting `freeze`, `discard_row`, or `discard_value` requires a separate behavioral decision.

## Alternatives considered

### Make generic YAML canonical

Rejected. It would reactivate and expand an unused configuration subsystem, add runtime indirection, make typed/callable behavior harder to validate, and force AVONET's materially different pinned manifest into an artificial common shape.

### Keep Python and YAML authorities with parity checks

Rejected. Parity checks detect some drift but preserve two authorities and make every future field a permanent synchronization obligation.

### Keep hand-maintained CI source lists

Rejected. The current omission exists precisely because a source can be added without updating every workflow list. GitHub Actions supports a matrix supplied by an earlier job's JSON output, allowing the canonical registry to drive source jobs.

## Consequences

- Adding a source becomes a registry entry plus its source/domain implementation and profile-required tests; Dagster and CI composition follow automatically.
- Generic configuration and quality code that is not part of the current DuckDB/Quack/Soda architecture is deleted rather than maintained speculatively.
- Source domain modules remain thin, explicit owners of source-specific construction while avoiding repeated literals within the module.
- All active sources incur equivalent profile-appropriate offline verification.
- CI may run more source jobs for a source-related change. At seven sources, correctness and omission resistance are preferred over fine-grained path optimization.
- AVONET retains an explicit exception because its manifest is an active immutable-source integrity contract, not generic scheduling/runtime configuration.
