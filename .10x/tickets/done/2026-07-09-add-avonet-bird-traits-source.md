Status: done
Created: 2026-07-09
Updated: 2026-07-10
Parent: .10x/tickets/done/2026-07-09-build-local-birding-pokedex.md
Depends-On: None

# Add AVONET bird-traits source

## Scope

Implement the pinned AVONET v7 dlt/Quack source governed by `.10x/specs/avonet-bird-traits-source.md`:

- exact bounded Figshare download/redirect/size/MD5 validation,
- strict parsing of only `AVONET2_eBird`,
- one normalized raw row per AVONET eBird scientific name/Avibase ID,
- complete morphology/ecology/measurement/dataset provenance fields,
- physical `raw_avonet.species_traits` plus source-scoped dlt metadata,
- independent Dagster ingest job and source registry/configuration,
- no daily schedule or change to existing parallel-refresh membership,
- generated and semantically annotated `.schema/environmental_observations/avonet.dbml`,
- docs/config/source-layout/typing/idempotency/failure tests.

## Explicit exclusions

- No SQLMesh trait/catalog model or browser/API work.
- No raw specimen measurements or other workbook sheets.
- No taxonomy guessing, external narrative source, retained workbook, concurrent/direct ingestion bypass, generic AVONET dedupe, SQLMesh model, or new daily schedule. Only the governed post-Quack atomic publication transaction may write authoritative `raw_avonet` directly.

## Acceptance criteria

- Exact fixture/live-format workbook produces the expected 10,661 source rows at one-row-per-Avibase-ID/scientific-name grain.
- Wrong host/scheme/redirect, length, hash, worksheet, headers, types, duplicate IDs/names, or malformed XLSX fails before authoritative replacement.
- `NA`/blank and categorical/code handling matches the active source spec.
- The source is independently runnable through Dagster, writes through Quack only to transient `raw_avonet_staging`, and atomically publishes the validated complete snapshot after Quack stops, with no persistent staging or `main._dlt*`.
- Re-running an identical workbook is idempotent, and a changed snapshot removes rows absent from the new snapshot.
- Extraction, staged-load, validation, or mid-publication failure preserves the last successful final table and metadata and removes temporary files/staging best-effort; a first-run failure publishes no final business table.
- Source schema, registry/layout, focused tests, Ruff, MyPy, docs, and repository hooks pass.

## Evidence expectations

Record pinned source identity/hash/license, bounded download/parser adversarial tests, normalized row/schema counts, Quack physical layout, idempotency, cleanup/rollback behavior, and independent review. Do not record workbook content beyond field names/counts or any environment secrets.

## Progress and notes

- 2026-07-09: Exact read-only compatibility probe found AVONET v7 article/file metadata, CC BY 4.0 license, expected file size/hash, 10,661 unique `AVONET2_eBird` names, and current Arizona exact-match baseline of 600/624 species plus 82 intentionally unmatched hybrids.
- 2026-07-10: Implemented the pinned AVONET source with the approved exact one-hop signed S3 redirect validation, bounded byte/hash checks, strict worksheet/header/type/grain normalization, full raw provenance, complete-snapshot semantics, and temporary-workbook cleanup.
- 2026-07-10: Registered only an independent `avonet_ingest` Dagster job (`scheduled=False`, `parallel_refresh=False`) and verified a hermetic Quack load into a temporary warehouse with one physical business table plus source-scoped dlt metadata and no persistent `main._dlt*` relations.
- 2026-07-10: Loaded the actual pinned workbook only into a temporary Quack warehouse to generate/verify the normalized schema: 10,661 rows and 38 business/provenance columns plus `_dlt_load_id`/`_dlt_id`; added annotated `avonet.dbml`, taxonomy, ontology, and source lifecycle documentation. Live `data/databox.duckdb` was not accessed for AVONET.
- 2026-07-10: Added hermetic redirect/security, byte/hash/cap, schema/type/null/grain, idempotency, failed-replacement preservation, cleanup, source-layout, registry, no-schedule/no-parallel-membership, definitions, and temporary-Quack tests. Reproducible observations and validation limits are recorded in `.10x/evidence/2026-07-10-avonet-bird-traits-source.md`.
- 2026-07-10: Critical review found `prepare_dlt_source` forces append and invalidated the original direct-to-final replacement claim. Reworked the production route to clear/load `raw_avonet_staging` through Quack, stop Quack, validate exact row/unique-key/column/metadata contracts, and atomically publish final tables in one direct transaction. Production-route tests now cover identical reruns, removal/replacement, extraction and post-stage failure, first-run/final validation failure, mid-publication rollback, staging cleanup, and crash-residue recovery.
- 2026-07-10: Final independent review passed download/parser security, atomic publication/rollback, production idempotency/replacement, schema/provenance, orchestration, and record-governance criteria. Review: `.10x/reviews/2026-07-10-avonet-bird-traits-source-review.md`.
- 2026-07-10: Retrospective: a declared dlt write disposition is not evidence of physical destination behavior after destination preparation. Complete static snapshots over append-only Quack require a non-authoritative staging boundary and validated atomic publish. Production-route replacement/failure tests preserve this lesson; no separate knowledge/skill record is needed.

## Blockers

None. User authorized execution through the parent plan.
