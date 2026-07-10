Status: open
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
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
- No taxonomy guessing, external narrative source, retained workbook, direct DuckDB write, or new daily schedule.

## Acceptance criteria

- Exact fixture/live-format workbook produces the expected 10,661 source rows at one-row-per-Avibase-ID/scientific-name grain.
- Wrong host/scheme/redirect, length, hash, worksheet, headers, types, duplicate IDs/names, or malformed XLSX fails before authoritative replacement.
- `NA`/blank and categorical/code handling matches the active source spec.
- The source is independently runnable through Dagster and writes through Quack to `raw_avonet` with no persistent `main._dlt*`.
- Re-running an identical workbook is idempotent.
- Failed refresh preserves the last successful table and removes temporary files.
- Source schema, registry/layout, focused tests, Ruff, MyPy, docs, and repository hooks pass.

## Evidence expectations

Record pinned source identity/hash/license, bounded download/parser adversarial tests, normalized row/schema counts, Quack physical layout, idempotency, cleanup/rollback behavior, and independent review. Do not record workbook content beyond field names/counts or any environment secrets.

## Progress and notes

- 2026-07-09: Exact read-only compatibility probe found AVONET v7 article/file metadata, CC BY 4.0 license, expected file size/hash, 10,661 unique `AVONET2_eBird` names, and current Arizona exact-match baseline of 600/624 species plus 82 intentionally unmatched hybrids.

## Blockers

None. User authorized execution through the parent plan.
