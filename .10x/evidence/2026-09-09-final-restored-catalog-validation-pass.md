Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/done/2026-09-04-build-isolated-catalog-recovery-drill.md

# Final restored-catalog validation pass

## Procedure

The user authorized one final read-only rerun against preserved recovery Polaris container `databox-polaris-recovery-validation-20260908-214022`, catalog `databox_lake`, and PITR target `2026-09-08T21:40:22Z`. The historical Databox code revision immediately preceding that recovery point was `e95b333092483a7103df9cfcfb39b8124fb7ed82`. Validation used reviewed corrected contract revision `e27990e9a87582db4d467b3fe2adab13bae0319c`, which declares physical child tables that already existed at the recovery point and implements the approved warning policy. The corrected contract revision is not represented as the historical running revision. The run occurred once with no retry, write, bootstrap, restart, port publication, cutover, or cleanup.

The final command directly remeasured active PostgreSQL/Polaris health and unchanged start times `2026-09-08T21:38:31.476511987Z` and `2026-09-05T16:26:22.471908317Z`; it also remeasured that both recovery containers were running without host port bindings. Recovery promotion, `archive_mode=off`, before/after marker counts, readiness, and validation labels were established by prior evidence and validator gating but were not all independently remeasured by this final command.

## Result

The validator exited `0` with status `pass` after `53.539` seconds:

- 25 expected tables;
- 29 actual tables;
- 25 validated tables;
- 0 failed, missing, unexpected-in-canonical-namespace, or malformed tables;
- 6 explicit warnings: two noncanonical namespaces and their four tables.

Warnings remained explicit:

- namespaces: `dlt_polaris_probe`, `raw_usfws`;
- tables: `dlt_polaris_probe.events`, `raw_usfws._dlt_load_status`, `raw_usfws.image_records`, `raw_usfws.image_search_runs`.

All 25 canonical tables passed metadata, current-snapshot, manifest-planning, and limit-one data reads. No credential value was emitted or retained.

## Supports

This proves the restored Polaris catalog is coherent with the corrected canonical registry and that all governed Iceberg table paths are readable through the restored application interface. Noncanonical state remains visible without redefining ownership.

## Limits

Reads are representative rather than exhaustive object-integrity checks. This does not prove the end-to-end 60-minute RTO or five-minute RPO measurement, production cutover, IAM least privilege, cleanup, or complete warehouse-loss reconstruction.
