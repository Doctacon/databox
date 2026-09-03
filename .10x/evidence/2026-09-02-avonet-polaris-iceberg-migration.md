Status: recorded
Created: 2026-09-02
Updated: 2026-09-02
Relates-To: .10x/tickets/done/2026-09-02-migrate-avonet-to-polaris-iceberg.md, .10x/specs/avonet-bird-traits-source.md, .10x/decisions/avonet-polaris-iceberg-publication.md

# AVONET Polaris Iceberg migration evidence

## What was observed

The pinned AVONET ingestion published `raw_avonet.species_traits` through dlt-managed Polaris Iceberg with exactly 10,661 rows, 10,661 distinct Avibase IDs, 10,661 distinct scientific names, and both `_dlt_load_id` and `_dlt_id`. The explicit load-status table contained one successful load row.

Refreshed consumers contained:

- `environmental_observations.dim_bird_species_traits`: 10,073 rows
- `rufous_public.avonet_species_traits`: 10,661 rows
- `birding_agent.arizona_species_catalog`: 707 rows

`analytics.platform_health` reported AVONET success with 10,661 committed rows.

## Procedure

1. Ran the independent pinned AVONET ingest against the configured Polaris/S3 catalog.
2. Loaded `raw_avonet.species_traits` and `_dlt_load_status` through PyIceberg and counted rows, distinct identifiers, and lineage fields.
3. Refreshed the AVONET trait dimension, public projection, dependent Arizona catalog, and platform health through targeted SQLMesh plans.
4. Queried the local modeled relations after attaching `polaris_aws`.
5. Ran the focused AVONET/load-status tests, all SQLMesh tests, platform-health generation check, pre-commit, and whitespace check.

Observed verification results:

```text
Focused pytest: 32 passed
SQLMesh tests: 18 passed
Platform-health codegen: matched
Pre-commit: passed
git diff --check: passed
```

## What this supports

This supports the ticket claims that AVONET retains its exact pinned snapshot contract, uniqueness, dlt lineage, direct Iceberg replacement, explicit load observability, and functioning downstream consumers without Quack staging.

## Limits

This is evidence from the configured local Polaris deployment and AWS S3 warehouse. It does not establish remote Polaris availability, public Rufous deployment behavior, or indefinite upstream file availability. The exact command output was observed during execution and summarized here; no secret values or workbook contents are retained.
