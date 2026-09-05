Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Target: .10x/tickets/2026-09-04-add-pgbackrest-catalog-protection.md
Verdict: concerns

# Catalog protection final static review

## Target

Catalog-protection implementation on `feat/backup-plan-iceberg` through commit `f28c31c`, governed by `.10x/specs/polaris-catalog-continuity.md` and `.10x/decisions/startup-only-catalog-backup-gate.md`.

## Findings

### P1 — Active specification still requires the removed logical export

`.10x/specs/polaris-catalog-continuity.md:42` requires a periodic encrypted logical PostgreSQL export, while its explicit exclusions and the owning ticket remove `pg_dump`. Delete the stale MUST; retain the explicit exclusion.

### P1 — Manual pgBackRest tasks do not select the PostgreSQL user

`Taskfile.yaml` invokes all four `docker compose exec postgres` commands without `--user postgres`. The one-shot Compose gate explicitly uses `user: postgres`, the PostgreSQL service has no Compose user, and its Dockerfile has no final `USER`; a later `exec` is therefore likely to run as root. Add `--user postgres` to check, full, differential, and info commands, add focused structural coverage, and prove the identity during eventual live image validation.

### P2 — Repository path requirement conflicts with the fixed configuration

The ticket requires bucket, region, and path inputs, while `infra/recovery/pgbackrest.conf.example` fixes `repo1-path=/polaris` and Compose exposes no path variable. Either add an input or ratify `/polaris` as the intentionally fixed path. The active specification currently requires only a configurable bucket.

### P2 — Missing encryption-secret behavior lacks focused coverage

The readiness implementation correctly requires `PGBACKREST_REPO1_CIPHER_PASS`, but the missing-setting parametrized test covers only the access key, secret key, and session token. Add the cipher passphrase to the missing-setting case and retain secret-redaction assertions.

## Acceptance assessment

Passed statically:

- one-Compose PostgreSQL → bootstrap → backup gate → Polaris sequence;
- fail-closed startup settings and reduced diagnostics;
- database, stanza, WAL, and machine-readable repository checks;
- `archive_timeout=300s` and pgBackRest `archive-push`;
- pinned PostgreSQL/pgBackRest configuration;
- AES-256-CBC and 30-day time-based retention configuration;
- exact seven-day full and one-day differential cadence;
- fresh successful backup label/type verification;
- absence of rejected credential process, AWS CLI/profile mounts, continuous monitor, cron, and pre-generated inventory machinery.

Concerns prevent closure for manual task identity, repository-path contract, missing encryption-secret coverage, and active specification coherence.

## Residual risk and limits

No image was built; no Compose stack or manual command was run; no AWS/provider call, repository access, stanza operation, WAL round trip, backup, retention expiry, or restore occurred. Package compatibility, shared socket/data-volume permissions, S3 integrity, and recoverability remain live-proof responsibilities. The accepted startup-only model does not detect later credential or repository failure until a manual command or later startup.
