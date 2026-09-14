Status: blocked
Created: 2026-09-08
Updated: 2026-09-08
Relates-To: .10x/tickets/done/2026-09-04-build-isolated-catalog-recovery-drill.md

# First isolated catalog restore attempt

> Publication redaction (2026-09-12): deployment account/bucket literals are replaced by labeled placeholders; generic principal labels are retained. This historical record is not a fresh approval or an executable plan. Original conclusions and verification limits still apply.
> Source revision: `027af8b4271d60ffc193967d092b5d2497af13ad`. Original-artifact SHA-256 (NOT this redacted text): `c5de73404f9363ecef42bea26244a61f6e84fb2bcec2fc15b8e6e552c66a93fa`.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry with `source_kind=committed-head` and `source_path` equal to this public path. Any preexisting plan/export hashes below identify original artifacts, not this changed counterpart.


## Authorization and target

The user explicitly authorized only a live isolated pgBackRest restore into new Docker volume `databox_polaris_recovery_20260905_162513` at PITR target `2026-09-05T16:25:13Z`, the recorded full-backup completion second. PostgreSQL/Polaris startup, validation, cutover, active-service restart, archive writes, cleanup, and deletion remained unauthorized.

Before execution, Git was clean; the target volume was absent; active volume `databox_polaris_postgres` existed; active PostgreSQL and Polaris were healthy; the `polaris` database remained readable at 8,293,523 bytes; image `databox-polaris-postgres:17.6-pgbackrest-2.59.1` matched exact reviewed ID `sha256:7d798550d0d94bfbf8576b0b97fc5b90705e0ebb940756dc9a042ca066b95b93`; `.env` had exact bucket `<REDACTED_BUCKET_2>`, region `us-west-1`, and a nonempty cipher passphrase without printing values; and AWS identities were exact IAM user `arn:aws:iam::<REDACTED_ACCOUNT_ID>:user/databox-recovery-operator` plus the expected MFA-assumed backup role.

Temporary role credentials were exported into process memory and mapped only to the child restore environment. Credentials and the repository cipher passphrase were not printed or written to tracked files.

## Result

Execution started at `2026-09-08T18:09:59.503381Z` and stopped at `2026-09-08T18:10:01.048959Z` with exit code `1`. The reviewed runner reported only:

```text
catalog recovery refused: isolated catalog restore failed; the recovery volume was preserved for inspection
```

The per-run ownership label was present and exact ownership verification had therefore passed before any mount. Read-only, no-network inspection found the preserved target empty: no `PG_VERSION` or restored files exist. Its root is owned by UID/GID 999, proving ownership initialization completed before pgBackRest failed. No restored recovery-target configuration exists.

A separate read-only pgBackRest `info` call under the same short-lived role succeeded and showed repository status `ok` with source full backup `20260905-162355F`, start epoch `1788625435`, stop epoch `1788625513`, and backup WAL range `000000010000000000000005` through `000000010000000000000006`. This narrows the failure to restore execution rather than basic repository availability but does not identify the underlying pgBackRest error because the reviewed runner intentionally suppresses child stderr.

Post-failure checks confirmed active PostgreSQL and Polaris remained healthy, the active database size remained 8,293,523 bytes, and neither active volume nor service was stopped, restarted, or mounted by the restore. No restored PostgreSQL/Polaris process was started. No volume or S3 object was deleted.

## Blocker

The runner's generic error handling is too opaque to diagnose a live restore failure. Add secret-redacted diagnostic capture that preserves actionable pgBackRest error text without exposing credentials or the cipher passphrase, cover it hermetically, independently review the change, and only then request authorization to retry or choose a different PITR target. Preserve `databox_polaris_recovery_20260905_162513`; do not reuse, mount read-write, or delete it without separate authorization.

## Limits

No restore, PITR, catalog validation, RPO, or RTO proof exists. The 1.5-second failed attempt is not an RTO measurement. The preserved target is empty and is evidence of failure only.
