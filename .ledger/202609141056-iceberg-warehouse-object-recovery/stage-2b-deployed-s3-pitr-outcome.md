# Stage 2B deployed S3 catalog PITR outcome

Status: bounded proof passed

## Scope

The user authorized the existing catalog-backup role and deployed S3 pgBackRest repository, bounded active marker and WAL operations, an isolated restore, canonical read-only validation, retained private evidence/resources, and no cutover. No IAM, bucket controls, warehouse objects, canonical table data, source refreshes, or active-service topology were changed. The existing backup and WAL history were sufficient, so no optional on-demand backup was created.

## Proof

The maintained timed catalog drill:

1. Verified the pinned active PostgreSQL and Polaris services were healthy, the active volume/network/port topology was exact, generated recovery names were absent, and the deployed repository contained a successful Polaris backup.
2. Exported an MFA-primed short-lived backup-role session directly into process memory and rejected near-expiry credentials.
3. Enumerated and synchronously archived bounded local pending WAL, then created a generated active marker with deterministic before/after rows around a microsecond-precise database recovery target.
4. Switched and synchronously archived the marker WAL, then retrieved and verified every same-timeline segment from the continuity anchor through the marker segment.
5. Restored from the deployed S3 repository into a new ownership-labeled Docker volume and promoted PostgreSQL at the selected time.
6. Proved the recovered database was promoted with archival disabled, the before row present, the after row absent, and no extra marker rows.
7. Restarted recovered PostgreSQL without backup credentials and repeated the marker validation.
8. Started real Polaris against the recovered database and passed readiness.
9. Validated all 25 canonical registry tables through Polaris-vended access: 25 passed and zero failed.
10. Dropped the active marker, synchronously archived its cleanup WAL, stopped credential-bearing Polaris, retained recovered PostgreSQL in its post-scrub secret-free state, and performed no cutover.

The measured end-to-end recovery time was approximately 141.37 seconds, within the 3,600-second objective. Private mode-`0600` evidence retains the complete report without raw pseudo-terminal output. Post-run checks independently confirmed the active marker was absent, both active services remained healthy, the recovered PostgreSQL process contained no backup/AWS credential environment, recovered Polaris was stopped, and the result remained isolated.

## Contained correction

The first invocation stopped before repository inspection or active mutation because the interactive entrypoint attempted a redundant remote login after the operator had already authenticated. It retained only a bounded failure receipt. The maintained command now supports `--reuse-authenticated-session`, which skips only that redundant login while still exporting the MFA-primed backup-role credentials into memory and enforcing the 15-minute minimum lifetime. A focused credential-flow regression and all 118 catalog-recovery tests passed before the successful drill.

## Boundary

This proves the deployed S3 pgBackRest backup and WAL path can restore the current canonical Polaris catalog into isolated resources, meet the one-hour drill objective, and preserve the selected before/after boundary. It does not prove automated cutover, destructive cleanup, continuous protection for WAL that had not reached the repository before catch-up, recovery from account/region loss, or warehouse-object recovery. Stage 1 separately proved constrained Iceberg object reconstruction; Stage 2A separately proved local POSIX PITR.
