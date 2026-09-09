Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/2026-09-04-build-isolated-catalog-recovery-drill.md

# Live REST-to-S3 snapshot validation

## Procedure

The user authorized one read-only validator rerun against preserved recovery Polaris container `databox-polaris-recovery-validation-20260908-214022`, catalog `databox_lake`, PITR target `2026-09-08T21:40:22Z`, and reviewed contract revision `17c45b067622d6fd5100d1e8c37636e83c21438a`. No retry, write, restart, bootstrap, cutover, port publication, or cleanup occurred.

Active PostgreSQL and Polaris were healthy before and after with unchanged start times `2026-09-08T21:38:31.476511987Z` and `2026-09-05T16:26:22.471908317Z`. Both recovery containers remained running and unexposed.

## Result

The validator exited `0` with status `pass` after `59.725` seconds:

- 25 expected and validated canonical tables;
- zero failed, missing, malformed, or unexpected-in-canonical-namespace tables;
- every expected table passed the new Polaris REST embedded-current-snapshot versus S3 metadata current-snapshot comparison, followed by manifest planning and a limit-one data read;
- two noncanonical namespaces and their four tables remained six explicit warnings: `dlt_polaris_probe`, `raw_usfws`, `dlt_polaris_probe.events`, `raw_usfws._dlt_load_status`, `raw_usfws.image_records`, and `raw_usfws.image_search_runs`.

No credential value was emitted or retained. A local evidence-summary expression initially looked for a nonexistent report field and printed `snapshot_matches=0`; that expression was not part of the validator, made no request, and does not describe the result. The authoritative per-table result contained zero failures; the validator would emit `snapshot_missing`, `snapshot_malformed`, or `snapshot_divergent` on any failed comparison.

## Limits

This is representative, read-only coherence evidence rather than exhaustive warehouse integrity proof. It does not measure end-to-end RPO/RTO or authorize cutover or cleanup.
