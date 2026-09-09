Status: recorded
Created: 2026-09-08
Updated: 2026-09-08
Relates-To: .10x/tickets/done/2026-09-04-build-isolated-catalog-recovery-drill.md

# Isolated catalog restore files success

## Authorization and target

The user explicitly authorized only a dotenv-aware pgBackRest restore into new volume `databox_polaris_recovery_20260905_162514` at PITR input `2026-09-05T16:25:14Z`, strictly after full backup `20260905-162355F` stopped at `2026-09-05T16:25:13Z`. Starting restored PostgreSQL/Polaris, catalog validation, cutover, active-service changes, cleanup/deletion, archive writes, and any read-write access to the three earlier failed volumes remained unauthorized.

Preconditions proved the exact operator IAM user and MFA-assumed backup role, absent target, present active and three prior recovery volumes, healthy active PostgreSQL/Polaris, unchanged active database size `8293523`, and pinned image ID `sha256:7d798550d0d94bfbf8576b0b97fc5b90705e0ebb940756dc9a042ca066b95b93`. Project `python-dotenv` parsing produced exact bucket `databox-lake-catalog-backup`, region `us-west-1`, and a nonempty cipher passphrase without printing values.

Temporary backup-role credentials were exported into process memory and mapped only to child `PGBACKREST_*` variables. Credentials and the cipher passphrase were not printed, written to `.env`, or recorded.

## Result

The reviewed runner executed from `2026-09-08T20:03:58.484255Z` through `2026-09-08T20:04:54.224044Z` and returned `0`. It created the target with its cryptographic ownership label, verified exact ownership before mounting, initialized ownership, and restored the selected encrypted S3 backup/WAL into the isolated volume. It opened no port, mounted no active volume/socket, started no database/service, performed no archive push, and deleted nothing.

Read-only, no-network inspection of the restored target observed:

- `PG_VERSION=17`;
- `1312` files totaling `31835448` bytes;
- target root ownership `999:999`, matching the pinned image's `postgres` user;
- `recovery.signal` present;
- `restore_command = 'pgbackrest --config=/etc/pgbackrest/pgbackrest.conf --stanza=polaris archive-get %f "%p"'`;
- `recovery_target_time = '2026-09-05 16:25:14+00'`; and
- `recovery_target_action = 'promote'`.

All three earlier failed volumes remained present and were not mounted. Active PostgreSQL retained start time `2026-09-05T16:23:42.020120423Z`; active Polaris retained start time `2026-09-05T16:26:22.471908317Z`; both remained healthy, and active database size remained exactly `8293523` bytes.

## What this proves

The pinned runner can safely materialize the reviewed full-backup/PITR file set from the encrypted S3 repository into a newly owned isolated Docker volume without touching the active catalog or starting restored services.

## Limits

This is a successful restore-file operation, not proof that PostgreSQL can replay WAL to and reach the target, promote, expose a coherent Polaris catalog, or satisfy RPO/RTO. The 55.7-second file restore is not an end-to-end RTO. Restored PostgreSQL startup and catalog validation remain separately authorized work. The successful volume and all three failed volumes remain preserved; none may be reused, mounted read-write, or deleted without authorization.
