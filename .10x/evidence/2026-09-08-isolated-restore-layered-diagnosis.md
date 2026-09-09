Status: recorded
Created: 2026-09-08
Updated: 2026-09-08
Relates-To: .10x/tickets/done/2026-09-04-build-isolated-catalog-recovery-drill.md

# Isolated restore layered diagnosis

## Scope and safety

The user authorized read-only repository diagnosis plus secret-redacted runner diagnostics after the first isolated restore failed. No restore retry, Docker volume creation/mount, database/service action, S3 write/delete, or cleanup ran. Failed volume `databox_polaris_recovery_20260905_162513` was not touched.

The expected MFA-assumed backup-role session was available without prompting. Temporary credentials were exported into process memory only and passed by environment-variable name to stateless, no-target pgBackRest containers. Credential values and the repository cipher passphrase were not printed or persisted.

## Read-only findings

An initial `verify` invocation requested unsupported JSON output and was rejected locally by pgBackRest before repository work. Retrying exact set `20260905-162355F` with supported text output while using an ad hoc `.env` parser reproduced the repository failure mode:

```text
status: error
No usable backup.info file
No usable archive.info file
```

The repository cipher passphrase is quoted in `.env`. The ad hoc parser retained those quote characters, changing the passphrase supplied to pgBackRest. Read-only `info` then reported a format/decryption failure loading encrypted `backup.info` and `archive.info`.

The same commands were rerun using the project's dotenv parser, which removes dotenv quoting correctly. Exact-set `verify` exited `0`, repository `info` reported stanza `ok`, and backup `20260905-162355F` reported `error=false`, start epoch `1788625435`, stop epoch `1788625513`, with WAL `000000010000000000000005` through `000000010000000000000006`. Requested PITR target `2026-09-05T16:25:13Z` equals the recorded backup stop second.

This identifies the failed restore's root cause: the execution-time environment bridge treated dotenv syntax as literal text and supplied a different cipher passphrase. The backup and repository verify correctly when `.env` is parsed as dotenv.

## Diagnostic repair

`scripts/platform/catalog_recovery.py` now includes bounded restore-child diagnostics. It reports sanitized stderr then stdout, retains generic target/preservation context, replaces every nonempty configured backup value, redacts common AWS access-key/session-token forms and labeled secret/token values, tolerates invalid child output bytes, and limits diagnostics to 2,000 characters. It never renders child argv.

Hermetic regression coverage proves an underlying restore marker survives, configured values and common AWS credential forms are redacted, labeled token values are redacted, output is bounded, target context remains, and volume preservation/no-delete behavior remains.

## Limits

No retry or successful restore/PITR exists. The failed empty volume remains preserved and must not be reused or deleted without separate authorization. A retry must use a new volume and a dotenv-aware environment bridge; starting restored PostgreSQL/Polaris and measuring RPO/RTO remain separately gated.
