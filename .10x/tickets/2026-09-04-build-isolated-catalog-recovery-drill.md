Status: open
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: .10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md, .10x/tickets/done/2026-09-04-add-pgbackrest-catalog-protection.md

# Build isolated Polaris catalog recovery drill

## Scope

Add fail-closed automation that restores a selected pgBackRest backup/PITR target into a new isolated PostgreSQL volume, starts compatible Polaris recovery services without replacing restored realm state, validates the restored catalog conventionally and, when the primary warehouse remains readable, every canonical registered Iceberg table, and leaves production cutover manual.

Provide deterministic offline tests using temporary local fixtures/fakes. Initial implementation excluded live backup downloads; the user later superseded only that exclusion through separately authorized, exact isolated file-restore attempts. Do not restore production objects, run infrastructure providers, or mutate AWS infrastructure.

## Acceptance criteria

- Restore requires an explicit recovery target and a new empty destination; active catalog volumes and configured primary paths are rejected.
- Recovery runs with compatible pinned PostgreSQL, pgBackRest, and Polaris versions.
- Restored realm state is not silently bootstrapped or replaced.
- Writers remain disabled in the recovery environment.
- Validation derives expected registry-owned tables from the Databox source registry at the Git revision corresponding to the recovery point, enumerates restored catalog/namespace/table state through Polaris, and reports missing or unexpected state without a second hardcoded list.
- Missing metadata, manifests, data objects, permissions, status tables, or snapshot divergence fail visibly before cutover when the primary warehouse remains readable.
- Complete primary-warehouse loss is reported as requiring source rebuild and is not represented as object-level recovery or as satisfying the 60-minute catalog RTO.
- Documentation distinguishes catalog PITR, Iceberg snapshot rollback, source rebuild, and last-resort table re-registration.
- The drill records start/end timestamps and computes achieved RPO/RTO but does not report objectives as proven in offline tests.
- Adversarial tests cover non-empty target, active-volume alias, malformed timestamp, absent backup/WAL, registry/restored-state mismatch, missing object, failed table scan, accidental bootstrap, and secret redaction.
- Focused tests, Compose rendering, Ruff, format, MyPy, secret scan, and diff checks pass without live external mutation.

## Explicit exclusions

- Any live restore not separately authorized with an exact target and new isolated volume; restored-service startup remains separately gated.
- Timed guarantee, AWS apply, or production cutover.
- Iceberg object restoration, recovery buckets, replication, or scheduled warehouse copies.
- Iceberg snapshot expiration, orphan deletion, or compaction.
- Changing source/model semantics.

## References

- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md`
- `.10x/decisions/startup-only-catalog-backup-gate.md`
- `.10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md`
- `.10x/tickets/done/2026-09-04-add-pgbackrest-catalog-protection.md`

## Evidence expectations

Record adversarial restore-safety cases, registry-derived restored-table validation cases, elapsed-time calculation, changed files, exact commands/results, and no-AWS-infrastructure-mutation/no-production-restore limits.

## Progress and notes

- 2026-09-04: Opened from the ratified disaster-recovery architecture.
- 2026-09-04: Timeboxed implementation added a preparation-only recovery helper that requires a zoned timestamp, rejects the active and non-empty destinations, creates only an empty isolated target, keeps writers disabled/bootstrap forbidden, and computes RPO/RTO without claiming proof. Focused adversarial tests and runbook distinctions were added. The ticket remains open because actual pgBackRest restore composition, conventional registry-derived catalog/table validation, and full failure-path tests are not yet implemented; no live restore ran.
- 2026-09-05: After the first physical backup/WAL proof passed, the user selected implementation-only restore work. The helper now plans and can explicitly execute a pinned one-shot pgBackRest PITR restore into a newly created named volume, rejects active/invalid/pre-existing targets, passes secrets by environment-variable name, mounts no active volume/socket, opens no ports, and preserves the target on failure. Hermetic tests mock every Docker action; no volume, container, S3 request, or live restore ran.
- 2026-09-08: Independent review `.10x/reviews/2026-09-08-isolated-restore-runner-review.md` raised a P1 check/create race: Docker volume creation is idempotent, so a target created after the absence check could be mounted and modified. Repair requires per-run ownership labeling and verification before any mount.
- 2026-09-08: Repaired the P1 with a cryptographically random per-execution ownership token applied as `com.databox.catalog-recovery.owner` during volume creation and verified by exact label inspection before any mount. Missing or mismatched ownership refuses without `docker run` or deletion; prepare-only generates no token. Twenty-nine focused hermetic tests plus Ruff, format, MyPy, secret scan, and diff checks passed. No Docker or AWS mutation and no live restore ran.
- 2026-09-08: Independent re-review `.10x/reviews/2026-09-08-isolated-restore-volume-race-repair-review.md` passed with no findings.
- 2026-09-08: User authorized PITR target `2026-09-05T16:25:13Z` into new volume `databox_polaris_recovery_20260905_162513`. Evidence `.10x/evidence/2026-09-08-first-isolated-catalog-restore-attempt.md` records exact preconditions and safe credential handling, but restore exited `1` after volume ownership initialization and before writing any restored files. The owned target is preserved empty, the source backup remains readable, and active services/data were unchanged and healthy. No restore/PITR/RTO claim was made.
- 2026-09-08: Layered read-only diagnosis `.10x/evidence/2026-09-08-isolated-restore-layered-diagnosis.md` identified the root cause: an ad hoc environment bridge preserved `.env` quote characters in the repository cipher passphrase. That reproduced unusable encrypted repository metadata; dotenv-aware parsing made exact-set `verify` and repository `info` pass. The runner now emits bounded, secret-redacted child diagnostics; 29 focused tests and static checks pass. No retry or volume touch occurred.
- 2026-09-08: Repaired the diagnostic review P1 by redacting standard quoted credential-process JSON `SecretAccessKey` and `SessionToken` values, including non-IQo session tokens, while preserving JSON structure and actionable fields. Volume safety and redaction-before-truncation are unchanged.
- 2026-09-08: Independent review `.10x/reviews/2026-09-08-isolated-restore-diagnostic-repair-review.md` passed with no findings after the JSON redaction repair.
- 2026-09-08: User authorized a dotenv-aware retry into `databox_polaris_recovery_20260905_162513_retry1`. Evidence `.10x/evidence/2026-09-08-isolated-catalog-restore-retry.md` records a safe fail before data restore: pgBackRest 2.59.1 rejected the runner's ISO `T`/`Z` target representation and requires `YYYY-MM-DD HH:MM:SS+00`. The owned retry volume is preserved empty; the first failed volume and healthy active services/data remained untouched.
- 2026-09-08: Repaired only timestamp rendering: timezone-required input remains normalized to UTC and the pgBackRest command now uses `YYYY-MM-DD HH:MM:SS+00`. Exact tests cover selected target `2026-09-05 16:25:13+00` and non-UTC-to-UTC normalization. No Docker, AWS, volume, or restore operation ran.
- 2026-09-08: Independent review `.10x/reviews/2026-09-08-pgbackrest-target-format-repair-review.md` passed with no findings.
- 2026-09-08: User authorized dotenv-aware retry2 into new volume `databox_polaris_recovery_20260905_162513_retry2` at target `2026-09-05T16:25:13Z`. Evidence `.10x/evidence/2026-09-08-isolated-catalog-restore-retry2.md` records a safe fail before restore: pgBackRest requires an automatically selected backup to stop strictly before the target, while full backup `20260905-162355F` stopped exactly at the selected second. Retry2 is preserved empty; both prior failed volumes and active services/data remained untouched.
- 2026-09-08: User authorized target `2026-09-05T16:25:14Z` in new volume `databox_polaris_recovery_20260905_162514`. Evidence `.10x/evidence/2026-09-08-isolated-catalog-restore-files-success.md` records successful file restore in 55.7 seconds, `PG_VERSION=17`, 1312 files/31835448 bytes, ownership `999:999`, recovery signal and exact PITR settings, untouched prior/active volumes, unchanged active service start times/database size, and healthy active PostgreSQL/Polaris. No restored service started and no PITR/RTO claim was made.
- 2026-09-08: Independent review `.10x/reviews/2026-09-08-isolated-catalog-file-restore-review.md` found the technical evidence coherent but raised a P2 record contradiction: the original implementation-only exclusion had not been updated after exact live file-restore authorization. Scope and exclusions now record that narrow supersession while keeping restored startup, validation, cutover, and timed claims gated.
- 2026-09-08: User authorized isolated restored-PostgreSQL startup only. Evidence `.10x/evidence/2026-09-08-isolated-postgres-pitr-start-attempt.md` records successful archive-get through WAL `...00A` and consistent recovery, followed by fail-closed shutdown because no transaction timestamp reached the selected post-backup target. Promotion and SQL validation did not occur. Active services/data and all prior failed volumes remained untouched; the stopped recovery container/volume are preserved.
- 2026-09-08: User authorized marker-backed time PITR. Evidence `.10x/evidence/2026-09-08-marker-backed-isolated-pitr-success.md` records fresh credential injection, readiness/differential backup, distinct before/after marker commits around target `2026-09-08T21:40:22Z`, WAL archival, a new isolated restore/start, promotion with `pg_is_in_recovery()=false`, before marker present/after marker absent, active probe cleanup and cleanup-WAL archival, healthy active services, and no restored Polaris/cutover/RPO/RTO claim. The isolated PostgreSQL container remains running for validation.
- 2026-09-08: Independent review `.10x/reviews/2026-09-08-marker-backed-isolated-pitr-review.md` passed with no findings.
- 2026-09-08: User authorized restored Polaris credential compatibility proof. Evidence `.10x/evidence/2026-09-08-restored-polaris-primary-credential-proof.md` records authorized replacement of only the isolated PostgreSQL container over its preserved volume, dedicated no-port recovery bridge, promoted before-only PostgreSQL state with archiving off, healthy no-bootstrap Polaris 1.7.0, restored OAuth plus 9-namespace/29-table enumeration, and representative `raw_gbif.occurrences` load-table credential vending with explicitly blank primary session token and no backup credentials. Active services retained exact start times/health/database size. No write, all-table validation, cutover, cleanup, or RPO/RTO claim occurred.
- 2026-09-08: Independent review `.10x/reviews/2026-09-08-restored-polaris-primary-credential-proof-review.md` passed with no findings.
- 2026-09-08: Implemented read-only `catalog_recovery_validate.py`. Its only expected inventory is each canonical `SOURCES` entry's declared raw tables plus its explicit `_dlt_load_status`; it queries only an explicitly named no-port restored Polaris container, inventories namespaces/tables, consumes vended credentials only in process memory, and uses PyIceberg to require metadata, current snapshot, manifest planning, and a limit-one data read for every expected table. It emits bounded secret-free JSON and fails on aggregate drift or unreadability. Eight hermetic tests cover derivation, missing/unexpected state, metadata/snapshot/manifest/data failures, empty tables, vended-secret exclusion, sanitized Docker failure, and aggregate nonzero exit. No Docker, AWS, catalog, warehouse, or recovery artifact operation ran in this implementation slice.

## Blockers

Independent implementation review, then separately authorized execution against the exact restored target/container. Do not delete or reuse recovery artifacts without authorization. Complete failure-path coverage and the timed drill remain unimplemented.
