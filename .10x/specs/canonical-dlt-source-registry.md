Status: active
Created: 2026-07-12
Updated: 2026-07-12

# Canonical dlt source registry

## Purpose and scope

This specification defines the single executable contract for active dlt ingestion sources and how Dagster discovers them. It governs source identity, operational metadata, domain-module construction, composition, scaffolding, and retirement of duplicate legacy configuration.

It does not change provider queries, data meaning, raw table schemas, dlt write dispositions, source cadence values, Quack concurrency, SQLMesh models, Soda contracts, or dlt schema-evolution behavior.

## Canonical registry

`packages/databox/databox/config/sources.py` MUST be the sole active registry of ingestion sources.

Each registered source MUST expose or deterministically derive:

- a unique lowercase snake-case name;
- its `raw_<name>` catalog/schema identity;
- every raw data table expected after a successful load;
- its Dagster domain module identity;
- freshness policy;
- whether it is eligible for a recurring schedule;
- whether it participates in the shared parallel Quack refresh;
- whether it is the single analytics freshness anchor;
- one verification profile: `http` or `file_snapshot`.

The active registry MUST contain exactly the seven current sources unless separately changed by an approved source addition/removal:

- `avonet`
- `ebird`
- `gbif`
- `noaa`
- `usgs`
- `usgs_earthquakes`
- `xeno_canto`

## Domain-module contract

For each registered source `<name>`:

- `databox.orchestration.domains.<name>` MUST exist;
- the module MUST expose the dlt assets and ingest job required by the installed Dagster/dagster-dlt integration;
- scheduled sources MUST expose their current daily job and schedule; unscheduled sources MUST NOT gain one;
- the module MUST use one local source builder for both definition-time metadata and execution-time source construction;
- source constructor literals MUST NOT be repeated between decorator setup and runtime execution;
- smoke limiting MUST remain execution-only and MUST NOT alter the canonical full source definition.

Dagster `Definitions` MUST derive source assets, checks, jobs, and schedules from the registry/domain contract. It MUST NOT contain a manually enumerated import/list entry for every source. Cross-domain analytics/SQLMesh assets MAY remain explicitly composed because they are not ingestion sources.

The shared Quack refresh MUST continue to derive eligible source names from the registry and MUST preserve one-server ownership, process isolation, cleanup, inspection, and SQLMesh-after-success behavior.

## Legacy retirement

The implementation MUST remove generic configuration/runtime artifacts that no longer have an active consumer after migration, including:

- the generic `PipelineConfig`/`PipelineSchedule`/`QualityRule` model and YAML loader;
- the generic `PipelineSource` protocol;
- the `databox_sources.registry` auto-registry;
- legacy per-source wrapper classes and `create_pipeline(config)` factories used only by that registry;
- generic per-source pipeline YAML files and templates;
- the unused generic Psycopg quality engine if no independent active consumer is found.

AVONET's pinned source manifest MUST remain. Its version, DOI, URL, expected size/checksum, worksheet, and row-count contract MUST be preserved exactly unless a separate AVONET specification changes them.

Before deletion, references in tests, docs, scaffolding, imports, exports, and dependency declarations MUST be repaired. Historical terminal records MUST remain historical and need not be rewritten unless they incorrectly present the retired path as current authority.

## New-source workflow

The new-source scaffold MUST:

1. create the source package and Dagster domain module;
2. add one canonical registry entry with an explicit verification profile;
3. create or clearly require the profile's test skeleton;
4. avoid editing a manual source list in Dagster definitions or CI;
5. fail its verification instructions until real raw tables and profile obligations are completed;
6. not create generic pipeline YAML or a legacy wrapper/factory.

The source-layout/contract checker MUST reject:

- a registered source without its package/domain/tests;
- an implemented source package/domain absent from the registry, except an explicitly marked scaffold with a bounded reason;
- duplicate names, invalid profiles, missing raw tables for completed sources, or multiple analytics anchors;
- a domain module whose scheduling exports conflict with registry flags;
- legacy generic registry/config artifacts reintroduced as active authority.

## Acceptance scenarios

### Existing source

Given any of the seven active registry entries, when the contract checker runs, then it resolves exactly one source package, one domain module, one source builder, and one verification profile.

### New source

Given a generated source scaffold, when it is completed and added to the registry, then Dagster and CI discover it without another source-name edit. If profile-required tests are absent, the contract checker fails.

### Registry drift

Given a source directory or domain module with no active registry owner, when validation runs, then validation fails rather than silently skipping it.

### AVONET

Given the AVONET pinned-file source, when generic configuration is retired, then its manifest integrity fields and atomic publication behavior remain unchanged.

## Explicit exclusions

- No provider request or source refresh is required by registry consolidation itself.
- No raw or modeled database row may be changed.
- No source may be added, removed, enabled, disabled, or rescheduled.
- No dlt `schema_contract` mode may be added or changed.
- No SQLMesh model or Dagster full-refresh lifecycle may be redesigned under this specification.
