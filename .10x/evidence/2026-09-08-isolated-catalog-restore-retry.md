Status: blocked
Created: 2026-09-08
Updated: 2026-09-08
Relates-To: .10x/tickets/done/2026-09-04-build-isolated-catalog-recovery-drill.md

# Isolated catalog restore retry

## Authorization and preconditions

The user explicitly authorized retrying only the isolated pgBackRest restore to target `2026-09-05T16:25:13Z` in new Docker volume `databox_polaris_recovery_20260905_162513_retry1`, using the reviewed runner and dotenv-aware environment loading. Starting PostgreSQL/Polaris, catalog validation, cutover, active-service changes, deletion, cleanup, and reuse or read-write mounting of the first failed volume remained unauthorized.

Before execution, the exact source user and MFA-assumed backup role were active; the retry volume was absent; the first failed volume remained present; active PostgreSQL and Polaris were healthy on `databox_polaris_postgres`; the active database size was 8,293,523 bytes; and the pinned image ID was `sha256:7d798550d0d94bfbf8576b0b97fc5b90705e0ebb940756dc9a042ca066b95b93`. The project dotenv parser produced exact bucket `databox-lake-catalog-backup`, region `us-west-1`, and a nonempty cipher passphrase without printing values.

Temporary backup-role credentials were exported into process memory and mapped to child `PGBACKREST_*` variables. Credentials and the cipher passphrase were not printed or persisted.

## Result

The reviewed runner created and proved ownership of the new volume, initialized its ownership, and then failed before restoring any file. Its bounded redacted diagnostic identified the exact defect:

```text
ERROR: [029]: automatic backup set selection cannot be performed with provided time '2026-09-05T16:25:13Z'
HINT: time format must be YYYY-MM-DD HH:MM:SS with optional msec and optional timezone (+/- HH or HHMM or HH:MM) - if timezone is omitted, local time is assumed (for UTC use +00)
```

The runner currently normalizes the valid user input into ISO `T`/`Z` form, but pgBackRest 2.59.1 requires a space-separated timestamp and numeric UTC offset. The retry therefore exited before repository restore selection or data download.

Read-only, no-network inspection found the retry volume empty, without `PG_VERSION`, owned by UID/GID 999, and carrying the runner's ownership label. It is preserved and MUST NOT be reused, mounted read-write, or deleted without separate authorization. The first failed volume also remains present and was not mounted.

Active PostgreSQL and Polaris retained their original start times, remained healthy, stayed on `databox_polaris_postgres`, and the active database remained 8,293,523 bytes. No active service or volume was stopped, restarted, or mounted by the retry. No PostgreSQL/Polaris recovery process started. No volume or S3 object was deleted, and no restore/PITR/RPO/RTO claim exists.

## Required repair

Render the already timezone-normalized target in pgBackRest's accepted UTC format `YYYY-MM-DD HH:MM:SS+00`, add exact command-contract coverage, independently review the repair, and obtain separate authorization before retrying into another new volume.
