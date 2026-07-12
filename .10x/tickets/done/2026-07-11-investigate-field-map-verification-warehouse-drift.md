Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: None

# Investigate Field Map verification warehouse drift

## Scope

Determine why full verification during the Field Map data/API ticket changed ignored live `data/databox.duckdb` SHA-256 from recorded `805d6d…9551b` to `87d45e…` despite intended read-only behavior. Do not restore or mutate without an evidence-backed source.

## Acceptance criteria

- Bound the command/time window and identify every path that can open the live database writable.
- Reconcile schema/table inventory and all prior recorded logical invariants read-only.
- Determine whether logical rows/schema changed or only DuckDB physical/checkpoint metadata changed, with reproducible evidence.
- Repair the offending verification/code path if current changes caused it; add no-write regression.
- Establish a defensible current baseline or identify an explicit restoration blocker; do not claim byte restoration without a source copy.
- Independent review passes before map-data ticket closure.

## Exclusions

No guessed restoration, source refresh, SQLMesh apply, media apply, delivery, or unrelated warehouse cleanup.

## Evidence expectations

Record hashes, mtimes, process/command evidence, schema/table checksums where possible, prior invariant comparison, root cause, repair, and limits.

## Progress and notes

- 2026-07-11: Bounded the byte drift after a proven unchanged read at `2026-07-12T01:05:13Z`. All first full verification commands completed by `01:07:12Z`; the second full Python gate completed before the persisted observation timestamp. The live file mtime became `2026-07-11 18:13:31` local.
- 2026-07-11: Identified a pre-existing local Uvicorn process PID 10470, started 16:29:35 local, listening on `127.0.0.1:8000` from this repository with the default live warehouse. The live personal-collection API intentionally opens the warehouse writable only for explicit mutation endpoints.
- 2026-07-11: Read-only inspection found exactly one coherent personal observation created at `2026-07-12T01:12:10.774956+00:00` (18:12 local), with a real current species code and user-shaped date/location presence. No source/test contains that species/date fixture. This is after the first full gate and during the broader verification session, and explains the file hash/mTime/checkpoint change through concurrent loopback product use rather than the map GET or test suite.
- 2026-07-11: All map tests use temporary DuckDB files; the map GET opens read-only and its temp no-write regression passes. No current map diff path can write the live warehouse. No source repair is warranted.
- 2026-07-11: Read-only reconciliation preserved catalog 706 (624 species/82 hybrids), media 1,412 with exact 524/182 photo and 600/106 call status counts, broad public evidence 1,676, strict map evidence 1,575, watches/cancellations/Wishlist/calendar zero, and SMTP verification two. The only prior aggregate difference is personal observations `0 -> 1`, matching the timestamped loopback write.
- 2026-07-11: Established observed post-write byte baseline `87d45ece558cd248aa6efdd295798276775093a4906eeac40f8c41a9eea245bc`; repeated read-only schema/count/checksum queries leave it unchanged. Evidence: `.10x/evidence/2026-07-11-field-map-verification-warehouse-drift.md`.

- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-field-map-verification-warehouse-drift-review.md`.
- 2026-07-11: Retrospective established that aggregate hash gates must account for concurrent explicit local product use; logical reconciliation and process/timestamp attribution prevented destructive restoration. This evidence is sufficient; no code change is needed.

## Blockers

None. The coherent user observation is preserved.
