Status: blocked
Created: 2026-09-08
Updated: 2026-09-08
Relates-To: .10x/tickets/2026-09-04-build-isolated-catalog-recovery-drill.md

# Isolated restored PostgreSQL PITR startup attempt

## Authorization and preconditions

The user explicitly authorized starting PostgreSQL only from restored volume `databox_polaris_recovery_20260905_162514` to prove WAL replay to target `2026-09-05 16:25:14+00` and promotion. Restored Polaris, catalog/table validation, cutover, cleanup/deletion, active-stack changes, and retries remained unauthorized.

Preconditions proved the exact MFA-assumed backup role, healthy unchanged active PostgreSQL/Polaris with start times `2026-09-05T16:23:42.020120423Z` and `2026-09-05T16:26:22.471908317Z`, active database size `8293523`, exact pinned image `sha256:7d798550d0d94bfbf8576b0b97fc5b90705e0ebb940756dc9a042ca066b95b93`, target ownership label, `PG_VERSION=17`, `recovery.signal`, exact target/action/archive-get configuration, no existing target mount, and all three failed volumes present.

The repository passphrase was loaded with project `python-dotenv`; temporary backup-role credentials were exported into process memory. Values were passed by environment-variable name and were not printed or persisted.

## Isolated execution

Container `databox-polaris-recovery-postgres-20260905-162514` used the pinned image as user `postgres`, only the restored target volume read-write, Docker bridge solely for S3 archive-get, no published ports, no active/socket mount, restart policy `no`, and command overrides `archive_mode=off` plus empty `listen_addresses`. No archive command or archive-push was configured.

PostgreSQL restored WAL segments `000000010000000000000005` through `00000001000000000000000A`, entered time-based recovery, completed backup recovery, reached a consistent state at LSN `0/6000088`, and briefly accepted read-only local connections. Replay then ended at `0/A000168` without encountering a transaction timestamp at or after `2026-09-05 16:25:14+00`, so PostgreSQL failed closed with:

```text
FATAL: recovery ended before configured recovery target was reached
```

The startup process exited `1`; PostgreSQL shut down; promotion did not occur; and no SQL success claim is made. Container remains exited with restart policy `no`. The target remains mounted only by that stopped container, retains `recovery.signal`, and was not deleted or retried.

## Active-system verification

Active PostgreSQL and Polaris retained their exact pre-attempt start times, remained healthy, and active database size remained exactly `8293523`. Active volume was never mounted. All three earlier failed recovery volumes remained present and untouched. No restored Polaris, bootstrap, cutover, S3 write/delete, volume deletion, or retry occurred.

## Required next decision

The archive contains no transaction commit that reaches the selected post-backup timestamp. Do not guess another time or retry this volume. A future drill must either (a) explicitly authorize a harmless, identifiable transaction on the active catalog followed by WAL archival and then restore to its recorded timestamp, or (b) separately authorize an immediate/end-of-backup recovery that proves startup but not arbitrary time-based PITR. Either path requires a newly restored volume.

## Limits

File restore remains proven; WAL retrieval and consistent recovery were observed, but configured-target reach, promotion, readable restored SQL, catalog validation, PITR, RPO, and RTO remain unproven.
