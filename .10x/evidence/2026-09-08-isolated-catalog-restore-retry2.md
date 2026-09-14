Status: blocked
Created: 2026-09-08
Updated: 2026-09-08
Relates-To: .10x/tickets/done/2026-09-04-build-isolated-catalog-recovery-drill.md

# Isolated catalog restore retry 2

## Authorization and preconditions

The user explicitly authorized only a dotenv-aware isolated pgBackRest restore retry into new Docker volume `databox_polaris_recovery_20260905_162513_retry2` at input PITR target `2026-09-05T16:25:13Z`, rendered by reviewed code as `2026-09-05 16:25:13+00`. PostgreSQL/Polaris startup, catalog validation, cutover, active-service changes, cleanup/deletion, archive writes, and any access to the two earlier failed volumes remained unauthorized.

Before execution, the target was absent; both prior owned failed volumes existed; active PostgreSQL and Polaris were healthy; their start times were recorded; the active `polaris` database was 8,293,523 bytes; image `databox-polaris-postgres:17.6-pgbackrest-2.59.1` matched `sha256:7d798550d0d94bfbf8576b0b97fc5b90705e0ebb940756dc9a042ca066b95b93`; and the exact operator IAM user plus MFA-assumed backup role were active. Project `python-dotenv` parsing produced the expected bucket, region, and nonempty cipher passphrase without printing values.

Temporary role credentials were exported into process memory and mapped to child `PGBACKREST_*` variables. Credentials and the cipher passphrase were not printed or persisted.

## Result

The authorized attempt ran from `2026-09-08T19:58:53Z` through `2026-09-08T19:58:55Z` and exited `1`. The runner created and proved ownership of the new target, initialized ownership, then emitted this bounded diagnostic:

```text
ERROR: [075]: unable to find backup set with stop time less than '2026-09-05 16:25:13+00'
```

Repository evidence records full backup `20260905-162355F` stopping at exactly epoch `1788625513`, or `2026-09-05T16:25:13Z`. pgBackRest requires the automatically selected backup stop time to be strictly earlier than a time-based recovery target. The authorized target equals the stop second, so no backup set was eligible. This is a target-selection boundary, not another timestamp-format, dotenv, TLS, or repository-access failure.

Read-only, no-network inspection found the owned retry2 volume empty: no `PG_VERSION`, zero files, no recovery/standby signal, no target settings, UID/GID `999:999`. Both earlier failed volumes remained present and were not mounted. Active PostgreSQL and Polaris retained exact prior start times, remained healthy on the active volume, and the active database remained 8,293,523 bytes. No restored PostgreSQL/Polaris process started; no volume or S3 object was deleted.

## Required next step

If the user authorizes another isolated restore, use a new volume and a recovery target strictly after the backup stop, minimally `2026-09-05T16:25:14Z`. Continue dotenv-aware loading and all existing isolation constraints. Do not reuse or delete any failed volume without separate authorization.

## Limits

No successful restore, PITR, catalog validation, RPO, or RTO proof exists. The two-second rejected attempt is not an RTO measurement.
