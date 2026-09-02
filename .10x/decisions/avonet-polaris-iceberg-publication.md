Status: active
Created: 2026-09-02
Updated: 2026-09-02

# Publish AVONET through dlt-managed Polaris Iceberg

## Context

The former DuckDB/Quack destination could not execute dlt replacement semantics directly, so AVONET required a staging schema and a custom single-writer transaction. The source platform is now Polaris-managed Iceberg on AWS S3. Iceberg provides atomic snapshot replacement, and dlt 1.30 supports `write_disposition="replace"` with `table_format="iceberg"` through its filesystem destination.

The user ratified replacing the Quack-specific staged publisher while preserving AVONET's pinned-source validation and dlt lineage.

## Decision

AVONET remains an independently runnable, unscheduled dlt source. It MUST retain the pinned file identity, redirect restrictions, byte-size and MD5 validation, exact worksheet/header/type validation, exactly 10,661 unique rows, provenance fields, and dlt lineage. dlt MUST publish `raw_avonet.species_traits` directly as a Polaris-managed Iceberg table with replacement semantics. Iceberg snapshot commit is the atomic publication boundary.

The Quack destination, `raw_avonet_staging`, manual DuckDB copy transaction, staging cleanup, and independent Quack-server requirement are removed. SQLMesh and platform-health consumers MUST read `polaris_aws.raw_avonet` and refresh after a successful Iceberg commit.

## Alternatives considered

- Retain Quack staging: rejected because it preserves destination-specific complexity that Iceberg makes unnecessary.
- Load Iceberg outside dlt: rejected because dlt normalization, metadata, and `_dlt_*` lineage remain requirements.
- Append and deduplicate: rejected because AVONET is a complete pinned snapshot and requires true replacement.

## Consequences

The source remains strict and fail-closed before publication. A successful dlt replacement creates one atomic authoritative Iceberg snapshot. Failed validation cannot publish; a failed Iceberg commit leaves the prior snapshot authoritative. Destination metadata and SQLMesh observability move to Polaris.

Supersedes `.10x/decisions/superseded/avonet-atomic-staged-publication.md`.
