Status: blocked
Created: 2026-09-05
Updated: 2026-09-05
Relates-To: .10x/tickets/done/2026-09-04-apply-and-prove-disaster-recovery.md

# First live catalog backup attempt

> Publication redaction (2026-09-12): deployment account/bucket literals are replaced by labeled placeholders; generic principal labels are retained. This historical record is not a fresh approval or an executable plan. Original conclusions and verification limits still apply.
> Source revision: `027af8b4271d60ffc193967d092b5d2497af13ad`. Original-artifact SHA-256 (NOT this redacted text): `2e5a026d1e9fd55a468d2fa4e6816d261134ae963be8f1730240ad125453cb74`.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry with `source_kind=committed-head` and `source_path` equal to this public path. Any preexisting plan/export hashes below identify original artifacts, not this changed counterpart.


## Authorization and preconditions

The user explicitly authorized a brief local PostgreSQL/Polaris restart against the existing named volume plus the first real S3 pgBackRest stanza, WAL, and full-backup proof. At `2026-09-05T16:10:45Z`:

- Git was clean;
- `.env` contained a nonempty repository cipher passphrase and exact bucket `<REDACTED_BUCKET_2>` without either value being printed;
- `databox-recovery-operator` resolved to exact IAM user `arn:aws:iam::<REDACTED_ACCOUNT_ID>:user/databox-recovery-operator`;
- `databox-polaris-catalog-backup` resolved to the expected assumed-role ARN;
- the root CLI profile was logged out;
- named volume `databox_polaris_postgres`, created `2026-08-31T18:07:11-07:00`, existed; and
- the live `polaris` database was readable and approximately 8.3 MB.

Temporary role credentials were exported into process memory and mapped only to child Compose environment variables. They were not printed, written into `.env`, or recorded in evidence.

## Attempt and fail-closed result

The host has standalone `docker-compose` 5.1.3 rather than the `docker compose` plugin, so the first invocation failed before mutation and was retried with the installed executable. Polaris and its console were stopped before PostgreSQL was recreated. PostgreSQL was recreated against the same named data volume, became healthy, and bootstrap completed successfully.

The catalog backup readiness container then exited `1`. Its generic public error was `catalog backup is not ready: catalog backup readiness command failed: run-pgbackrest`. Direct sanitized diagnosis of `stanza-create` showed:

```text
unable to connect to dbname='postgres' port=5432
FATAL: role "postgres" does not exist
unable to find primary cluster - cannot proceed
```

This existing cluster was initialized with `POSTGRES_USER=polaris`, so it has no database role named `postgres`, while pgBackRest's stanza discovery currently defaults to that role/database. This is an implementation/configuration defect; no unapproved database-role or pgBackRest configuration repair was made.

The failure was fail-closed as designed. At `2026-09-05T16:12:48Z`, PostgreSQL was healthy with `archive_mode=on`, `archive_timeout=5min`, and exact archive command `/usr/local/bin/run-pgbackrest --stanza=polaris archive-push %p`; the readiness container was exited `1`; Polaris and its console remained stopped. The named data volume and database remained present. The intended `polaris/` S3 prefix had zero objects, so no stanza, backup, or WAL archive was claimed.

## Required repair

Determine and review the smallest correct way for pgBackRest to connect to this intentionally `polaris`-owned cluster (configuration versus a dedicated database role), add focused regression coverage, then rerun this already-authorized proof only after the repair is accepted. Do not bypass the readiness gate or start Polaris while it is failing.

## Limits

No S3 object, successful stanza, backup label, WAL archive range, restore, PITR, RPO, or RTO proof exists. No volume or warehouse object was deleted. Credentials and the repository passphrase were not logged. PostgreSQL remains internally available only for repair; application services remain unavailable.
