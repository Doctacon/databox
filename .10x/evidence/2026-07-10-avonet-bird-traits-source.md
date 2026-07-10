Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Relates-To: .10x/tickets/done/2026-07-09-add-avonet-bird-traits-source.md, .10x/specs/avonet-bird-traits-source.md

# AVONET v7 source implementation evidence

## What was observed

- The fixed Figshare downloader completed only through the approved validated one-hop signed S3 redirect and produced exactly 21,524,673 bytes with MD5 `1445afdcfb6df784010c2ca034544bc8`.
- Strict parsing of only `AVONET2_eBird` produced 10,661 rows with independently unique scientific names and Avibase IDs.
- Critical review invalidated the original direct-to-final dlt replacement claim because `prepare_dlt_source` forces append. The corrected production route loaded the full pinned workbook through Quack only into freshly cleared `raw_avonet_staging`, stopped Quack, then validated and atomically published physical `raw_avonet.species_traits` with 10,661 rows, 10,661 distinct Avibase IDs, 10,661 distinct source names, 38 normalized source/provenance columns, dlt `_dlt_load_id`/`_dlt_id`, and source-scoped `_dlt_loads`/`_dlt_version`. The completed temporary warehouse had zero staging relations and zero persistent `main._dlt*` relations.
- The workbook and temporary warehouse/pipeline directories used for verification were removed. Live `data/databox.duckdb` was not used.
- `avonet_ingest` resolves as an independent Dagster job; AVONET has no schedule and is rejected from shared parallel refresh membership.

## Procedure

1. Ran the real bounded downloader to a temporary file, parsed it under the production row/header/type contract, printed only row count and byte size, then deleted it.
2. Ran the real production lifecycle against a temporary database: clear staging, download/parse, append-load staging through an independent Quack server, stop Quack, validate exact rows/unique keys/columns/metadata, atomically publish final tables, and remove staging. Queried only normalized schema/table names and counts, then removed the temporary database and pipeline state.
3. Ran 105 focused AVONET/source-layout/registry/parallel-refresh/Quack/schema tests: all passed. Production-route tests exercised two identical runs, changed/removal replacement, extraction failure, injected staged-load lifecycle failure, first-run and prior-final validation failure, injected mid-publication rollback, transient cleanup, and crash-residue recovery.
4. Ran Ruff across the repository, project-standard `.venv/bin/mypy packages/`, source-layout lint, staging/platform-health/docs drift checks, strict MkDocs build, secret scan, diff check, and all pre-commit hooks: all passed.
5. Ran the full pytest suite before the critical-review repair: 283 passed and four unrelated source-node/cassette/snapshot failures occurred while all AVONET tests passed. Independent review proved the exact failing nodes are order-dependent and the systemic cassette leak predates AVONET by comparing the current suite, a suite excluding all new AVONET tests, and an isolated unmodified `HEAD`; the systemic issue remains separately owned.

## What this supports

This supports the pinned identity, bounded one-hop download, strict schema/grain/null handling, transient Quack staging, exact pre-publication validation, atomic complete-snapshot replacement, failure rollback/preservation, staging and temporary-file cleanup, crash-residue recovery, independent orchestration lifecycle, and schema/documentation claims in the owning ticket.

## Limits

- No AVONET load was run against the live warehouse.
- No SQLMesh trait/catalog model, API, or UI behavior was implemented or tested.
- Independent final review passed and is recorded at `.10x/reviews/2026-07-10-avonet-bird-traits-source-review.md`.
- The unrelated order-dependent full-suite VCR/snapshot failures were not repaired because they are proven pre-existing and outside this ticket; they are owned by `.10x/tickets/done/2026-07-10-repair-source-vcr-and-schema-snapshot-suite.md`. The corrected focused 105-test suite and all non-pytest repository gates passed.
