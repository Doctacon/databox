Status: recorded
Created: 2026-09-08
Updated: 2026-09-08
Relates-To: .10x/tickets/2026-09-04-build-isolated-catalog-recovery-drill.md

# Marker-backed isolated PostgreSQL PITR success

## Authorization and boundaries

The user explicitly authorized a controlled active PostgreSQL credential-refresh restart, temporary marker transaction, WAL archival, restore into a new isolated volume, isolated PostgreSQL startup, exact marker-boundary validation, and active marker cleanup/archive. Restored Polaris, cutover, warehouse mutation, recovery-volume deletion, and timed RPO/RTO claims remained unauthorized.

The exact MFA-assumed `databox-polaris-catalog-backup` role was active. Temporary role credentials and the repository cipher passphrase were loaded with `python-dotenv`, held in process/container environment only, and never printed or written to tracked files. Because Compose parses every service and the unrelated primary-warehouse session token remains unavailable, a clearly noncredential parser-only sentinel satisfied interpolation for the authorized `--no-deps postgres` recreation. Inspection proved `DATABOX_AWS_SESSION_TOKEN` was not injected into PostgreSQL; Polaris was not recreated.

## Active restart and readiness

Only `databox-iceberg-postgres-1` was recreated against existing volume `databox_polaris_postgres`; the new container started at `2026-09-08T21:38:31.476511987Z`. The named catalog-backup readiness gate passed and created differential backup `20260905-162355F_20260908-213839D`. Repository status remained `ok`. Polaris was not recreated: its start time remained `2026-09-05T16:26:22.471908317Z` and it recovered healthy.

Exact database downtime was not captured because the first orchestration harness aborted before persisting its timing result. PostgreSQL became and remained healthy before any marker operation. This evidence does not invent a downtime measurement.

## Marker sequence and operational correction

A first marker-harness attempt used the same primary-key value for `before` and `after`. PostgreSQL rejected the duplicate `after` row before any restore volume was created. The authorized cleanup ran, dropped the probe table, forced/verified WAL archival through `00000001000000000000000F`, and left both active services healthy.

The corrected marker sequence used distinct marker keys under probe ID `95cfab7c-3526-4068-b560-3570313add54`:

- committed `before` at `2026-09-08T21:40:21.012797Z`;
- selected target `2026-09-08T21:40:22Z` strictly after that commit;
- committed `after` at `2026-09-08T21:40:24.652745Z`;
- forced and verified marker WAL archival with zero `pg_stat_archiver` failures.

No recovery volume existed before the corrected restore.

## Isolated restore and startup

The reviewed runner created and ownership-verified volume `databox_polaris_recovery_probe_20260908_214022`, restored it from the encrypted repository, and left all prior recovery volumes untouched. Container `databox-polaris-recovery-probe-20260908_214022` runs pinned image `sha256:7d798550d0d94bfbf8576b0b97fc5b90705e0ebb940756dc9a042ca066b95b93` as `postgres` with:

- only `databox_polaris_recovery_probe_20260908_214022` mounted read-write;
- no active or prior recovery volume/socket;
- no published port;
- Docker `bridge` only for S3 `archive-get`;
- restart policy `no`;
- `listen_addresses=''`;
- `archive_mode=off`;
- no Polaris or bootstrap.

PostgreSQL restored WAL `00000001000000000000000C` through `000000010000000000000011`, reached a consistent state, stopped before the `after` transaction at `2026-09-08T21:40:24.652745Z`, selected timeline 2, promoted, and became writable. The final SQL result was:

- `pg_is_in_recovery() = false`;
- `archive_mode = off`;
- exact `before` marker count = 1;
- exact `after` marker count = 0;
- total rows for the probe ID = 1.

The orchestration harness queried as soon as read-only consistency was reached and initially observed `pg_is_in_recovery() = true`; it preserved the running container. Subsequent observation after normal target promotion produced the required result above. No retry or second restore was performed.

## Active cleanup and safety

The temporary probe table was dropped from the active `polaris` database. Cleanup WAL was forced and archived; active `pg_stat_archiver` reported last archived WAL `000000010000000000000013` and zero failures. The probe relation is absent from active PostgreSQL. Active database size is `8309907` bytes versus the earlier `8293523` bytes; logical cleanup succeeded, while expected PostgreSQL catalog/WAL-related physical growth was not represented as byte-for-byte rollback.

Active PostgreSQL and Polaris are healthy. No Iceberg/warehouse object, IAM/OpenTofu resource, S3 object, recovery volume, or container was deleted. The isolated PostgreSQL container and volume remain running/preserved for separately authorized validation. Prior recovery artifacts remain preserved.

## What this proves

This proves a marker-backed, time-targeted physical restore can replay archived WAL to the selected UTC boundary, exclude a later committed transaction, promote an isolated PostgreSQL 17.6 instance, and expose the expected catalog database without touching the active catalog or starting Polaris.

## Limits and residual risk

This is not restored Polaris validation, registry-derived table validation, a production cutover, or a timed RPO/RTO drill. Exact active restart downtime was not captured. Temporary backup-role credentials expire; the isolated container needs them only for any further archive retrieval. Same-account/same-region loss remains outside the accepted boundary.
