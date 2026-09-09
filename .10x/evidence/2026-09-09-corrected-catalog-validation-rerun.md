Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/2026-09-04-build-isolated-catalog-recovery-drill.md

# Corrected restored-catalog validation rerun

## Procedure

The user authorized a read-only rerun against preserved container `databox-polaris-recovery-validation-20260908-214022`, catalog `databox_lake`, and PITR target `2026-09-08T21:40:22Z`. The validator used corrected registry contract revision `d5fce6f4dd6cacd89565e6b6e535a307db7b3a27`; this is the reviewed post-recovery contract correction, not a claim that the commit existed at the recovery timestamp.

Active PostgreSQL and Polaris were healthy before and after with unchanged start times `2026-09-08T21:38:31.476511987Z` and `2026-09-05T16:26:22.471908317Z`. Both recovery containers remained running with no host port bindings. No write, restart, bootstrap, cutover, cleanup, or retry occurred.

## Result

The single run exited `1` after `59.199` seconds, correctly fail-closed on noncanonical state:

- expected tables: 25;
- actual tables: 29;
- validated tables: 25;
- failed tables: 0;
- missing tables/namespaces: none;
- malformed identifiers: 0;
- unexpected namespaces: `dlt_polaris_probe`, `raw_usfws`;
- unexpected tables: `dlt_polaris_probe.events`, `raw_usfws._dlt_load_status`, `raw_usfws.image_records`, `raw_usfws.image_search_runs`.

All 25 corrected registry expectations passed metadata, current-snapshot, manifest-planning, and limit-one data reads. The only remaining failure is the separately owned warning/failure policy for the four explicitly visible noncanonical tables in `.10x/tickets/done/2026-09-09-classify-noncanonical-restored-catalog-state.md`.

## Limits

This is representative read evidence, not exhaustive warehouse integrity proof. RPO/RTO, cutover, cleanup, IAM least privilege, and complete warehouse-loss reconstruction remain unproven or out of scope.
