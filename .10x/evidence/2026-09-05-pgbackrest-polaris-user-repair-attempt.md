Status: blocked
Created: 2026-09-05
Updated: 2026-09-05
Relates-To: .10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md

# pgBackRest Polaris-user repair and live retry

## Approved repair

The user approved only configuring pgBackRest with `pg1-user=polaris`; no database role, password, or permission was added. Commit `342825c` adds that exact configuration and focused regression coverage.

Validation passed:

- `uv run pytest tests/platform/test_catalog_recovery.py --no-cov -q`: 17 passed;
- focused Ruff check and format check: passed;
- `git diff --check`: passed.

Image `databox-polaris-postgres:17.6-pgbackrest-2.59.1` was rebuilt as `sha256:adb2ef7a4ab22d790cbd91bc299addae0fece9cc390e5db17f5901dfb5e15261`. Runtime inspection as `postgres` proved pgBackRest `2.59.1`, exact `pg1-user=polaris`, and no AWS CLI.

## Live retry

Cached backup-role credentials were exported only into child-process memory and were neither printed nor written. The installed standalone `docker-compose` recreated PostgreSQL, bootstrap, and the readiness gate against the preserved `databox_polaris_postgres` volume. A non-secret interpolation sentinel was provided only because the untargeted Polaris service declares a required primary `DATABOX_AWS_SESSION_TOKEN`; Polaris was not recreated or given that value.

The user repair worked: direct sanitized `stanza-create` no longer reported the nonexistent `postgres` database role. It stopped at the next exact blocker:

```text
unable to verify certificate presented by 'databox-lake-catalog-backup.s3.us-west-1.amazonaws.com:443'
unable to get local issuer certificate
```

The image does not currently install the CA certificate bundle required for verified HTTPS to S3. The readiness gate exited `1`, PostgreSQL remained healthy on the preserved volume, bootstrap exited `0`, and Polaris plus its console remained stopped. PostgreSQL reports `archive_mode=on`, five-minute archive timeout, and exact pgBackRest archive command. The `polaris/` S3 prefix remains empty. No stanza, WAL, backup, restore, RPO, or RTO proof is claimed.

## Required next repair

Review the smallest image packaging repair: install Debian `ca-certificates` alongside pgBackRest/Python, prove the package/bundle in the pinned image, and rerun this authorized proof. Do not disable TLS verification.

The whole Compose file also currently requires a nonempty primary `DATABOX_AWS_SESSION_TOKEN`, while the local `.env` lacks it. This did not affect the targeted PostgreSQL/readiness retry but must be resolved before recreating Polaris through Compose; do not persist or fabricate a primary AWS session token.
