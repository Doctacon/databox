Status: open
Created: 2026-09-02
Updated: 2026-09-02
Parent: None
Depends-On: None

# Migrate AVONET to dlt-managed Polaris Iceberg

## Scope

Replace AVONET's Quack staging publisher with direct dlt replacement into Polaris-managed `raw_avonet.species_traits`. Remove obsolete staging/Quack mechanics, update SQLMesh and generated observability authority, and verify the complete pinned snapshot.

## Acceptance criteria

- AVONET retains pinned download, byte/hash, worksheet/header/type, exact 10,661-row, Avibase-ID, scientific-name, provenance, and fail-closed validation.
- dlt uses the shared Iceberg destination with `write_disposition="replace"` and `table_format="iceberg"`.
- `raw_avonet.species_traits` is Polaris-authoritative and contains exactly 10,661 unique rows with `_dlt_load_id` and `_dlt_id`.
- Quack staging, manual DuckDB publication, and staging cleanup code are removed.
- `environmental_observations.dim_bird_species_traits`, `rufous_public.avonet_species_traits`, dependent catalog modeling, and `analytics.platform_health` read or refresh from the Iceberg authority.
- AVONET remains independently runnable and unscheduled.
- Focused tests, SQLMesh tests, generator drift, pre-commit, and diff checks pass.

## Explicit exclusions

- Changing the pinned AVONET dataset identity or conformance rules.
- Adding AVONET to scheduled parallel refresh.
- Migrating USFWS.

## References

- `.10x/specs/avonet-bird-traits-source.md`
- `.10x/decisions/avonet-polaris-iceberg-publication.md`
- `.10x/knowledge/dlt-polaris-iceberg-source-cutover.md`

## Evidence expectations

Record the Iceberg row/uniqueness/lineage checks, SQLMesh consumer counts, platform-health status, and validation commands.

## Progress and notes

- 2026-09-02: User ratified direct dlt-managed Iceberg replacement while preserving all pinned-source validation and lineage requirements.
- 2026-09-02: Replaced Quack staging publication with direct dlt Iceberg replacement and removed obsolete staging publisher/tests.
- 2026-09-02: Real pinned ingestion committed exactly 10,661 AVONET rows with `_dlt_load_id` and `_dlt_id`.
- 2026-09-02: User ratified explicit `_dlt_load_status` Iceberg publication for migrated-source observability. Added shared publication and updated every migrated source plus generated platform health.
- 2026-09-02: Restored full eBird authority after the earlier smoke snapshot (`taxonomy=17,891`, `species_list=707`) and refreshed AVONET traits, public traits, catalog, and platform health.
- 2026-09-02: Final verification observed 10,661 AVONET rows, 10,661 unique Avibase IDs, 10,661 unique scientific names, complete dlt lineage, 10,073 modeled trait rows, 10,661 public trait rows, and 707 catalog rows. All seven migrated sources expose one load-status row and platform health reports success. Focused tests passed (32), all SQLMesh tests passed (18), platform-health codegen matched, pre-commit passed, and `git diff --check` passed.

## Blockers

None.
