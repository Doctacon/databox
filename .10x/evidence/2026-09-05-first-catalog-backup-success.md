Status: recorded
Created: 2026-09-05
Updated: 2026-09-05
Relates-To: .10x/tickets/done/2026-09-04-apply-and-prove-disaster-recovery.md

# First live Polaris catalog backup and WAL proof

## Authorized repair

The user approved adding Debian `ca-certificates` to the pinned PostgreSQL image, verifying the trust bundle, rebuilding, and retrying the already-authorized live pgBackRest proof. Commit `5f9bd43` adds only that package and a nonempty-bundle build assertion plus focused static regression coverage. TLS and certificate verification remain enabled.

## Validation and image

Seventeen focused tests passed. Ruff check/format, diff checks, pre-commit hooks, and a 871-file secret scan passed. Image `databox-polaris-postgres:17.6-pgbackrest-2.59.1` rebuilt as `sha256:7d798550d0d94bfbf8576b0b97fc5b90705e0ebb940756dc9a042ca066b95b93`.

Runtime checks as the Compose pgBackRest user proved PostgreSQL `17.6`, pgBackRest `2.59.1`, `pg1-user=polaris`, a nonempty 224449-byte `/etc/ssl/certs/ca-certificates.crt`, and no AWS CLI. The running PostgreSQL process UID equals the image's `postgres` UID 999. The existing named volume `databox_polaris_postgres` remained mounted and the readable `polaris` database remained approximately 8.3 MB.

## Live proof

The cached MFA-protected `databox-polaris-catalog-backup` role session was exported into process memory and mapped only to child Compose environment. Credentials and the repository cipher passphrase were never printed or written to `.env` or evidence.

PostgreSQL was recreated against the preserved named volume using the repaired image. The named `catalog-backup-readiness` service completed with exit code `0`. This executed stanza creation/check, verified WAL archiving, created the required initial full backup, and freshly re-read repository information before success.

Observed pgBackRest repository state:

- stanza status: `ok`;
- successful full backup label: `20260905-162355F`;
- backup started at epoch `1788625435` and stopped at `1788625513`;
- backup error: `false`;
- archive id: `17-1`;
- WAL range: `000000010000000000000001` through `000000010000000000000007`.

A forced WAL switch completed. PostgreSQL `pg_stat_archiver` reported seven archived entries, last archived `000000010000000000000005.00000028.backup`, and zero failures. Runtime settings were `archive_mode=on`, `archive_timeout=5min`, and exact archive command `/usr/local/bin/run-pgbackrest --stanza=polaris archive-push %p`.

Read-only S3 enumeration under `polaris/` observed 1327 current objects totaling 7553136 bytes, with both archive and backup paths present. PostgreSQL and Polaris were healthy and the Polaris console was running after the successful gate.

## Limits and residual risk

This proves the first physical catalog backup and WAL archive round trip, not restore, PITR, five-minute RPO, or 60-minute RTO. The temporary role credentials expire; under the accepted startup-only design, unusually long sessions require operator credential refresh and a controlled Compose restart rather than synchronous writer shutdown.

The existing Polaris container was restarted after the successful named gate rather than recreated because `.env` still lacks the required primary-warehouse `DATABOX_AWS_SESSION_TOKEN`. No backup-role credential was injected into Polaris. A future full Compose recreation remains blocked until valid primary-warehouse session credentials are supplied; this does not invalidate the completed catalog backup/WAL proof.
