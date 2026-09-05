Status: open
Created: 2026-09-04
Updated: 2026-09-04
Parent: None
Depends-On: None

# Build Polaris and Iceberg disaster recovery

## Aggregate outcome

Deliver reviewable, tested automation for Polaris catalog PITR while retaining Iceberg snapshot rollback and source-driven warehouse rebuild, then separately provision and prove catalog recovery only after explicit approval of a catalog-only OpenTofu plan.

## Child plan

1. `.10x/tickets/2026-09-04-declare-aws-recovery-infrastructure.md` — add OpenTofu for the two same-account, same-region buckets, retention, replication, and least-privilege IAM. Can begin immediately.
2. `.10x/tickets/done/2026-09-04-add-pgbackrest-catalog-protection.md` — completed pgBackRest, host-injected temporary credentials, startup cadence, backup/check commands, tests, and local image packaging proof.
3. `.10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md` — remove the rejected Iceberg replication plane and generate a fresh catalog-only plan.
4. `.10x/tickets/2026-09-04-build-isolated-catalog-recovery-drill.md` — add fail-closed catalog PITR restore and conventional validation when the primary warehouse remains readable.
5. `.10x/tickets/2026-09-04-verify-disaster-recovery-automation.md` — adversarially review and verify the complete non-live catalog automation and documentation.
6. `.10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md` — blocked live rollout and timed catalog-restore proof; begins only after the user reviews the replacement OpenTofu plan and explicitly authorizes AWS mutation.

Child 3 supersedes the Iceberg portions of child 1. Catalog restore work follows the catalog-only infrastructure contract. Final verification precedes the live child, which also requires separate plan approval.

## Integration points

- `compose.iceberg.yml` remains the local Polaris/PostgreSQL runtime.
- OpenTofu outputs and environment-variable names form the boundary between AWS infrastructure and local backup tooling.
- `Taskfile.yaml` and `docs/runbook.md` expose operator commands.
- Recovery validators reuse the canonical source registry and Polaris client rather than a second source/table list.
- No child may alter provider behavior, SQLMesh model semantics, source schedules, or primary Iceberg authority.

## Aggregate acceptance criteria

- Repository automation covers PostgreSQL catalog PITR without long-lived credentials; Iceberg object loss is explicitly rebuilt from sources rather than represented as independently backed up.
- Non-live validation is hermetic and does not mutate AWS or current local data.
- The generated OpenTofu plan is reviewable before apply and contains no secret values.
- Recovery defaults to an isolated empty target and cannot overwrite the active catalog.
- Documentation distinguishes backup, restore, table rollback, object recovery, and last-resort re-registration.
- Live provisioning and RPO/RTO claims remain blocked until separately authorized and evidenced.
- Related decisions, specifications, tickets, evidence, reviews, and documentation remain coherent.

## Explicit exclusions

- Live AWS apply in children 1–4.
- Claiming that static tests prove five-minute RPO or 60-minute RTO.
- PostgreSQL/Polaris high availability.
- Iceberg compaction, snapshot expiration, or orphan cleanup.
- Cross-account or cross-region recovery.

## References

- `.10x/research/2026-09-04-polaris-iceberg-disaster-recovery.md`
- `.10x/decisions/startup-only-catalog-backup-gate.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md`
- `.10x/specs/superseded/iceberg-object-recovery.md`
- `docs/adr/0008-polaris-iceberg-raw-authority.md`

## Progress and notes

- 2026-09-04: Opened after the user approved execution. User selected automation-first OpenTofu delivery, same AWS account and `us-west-1`, separate catalog and Iceberg recovery buckets, renewable credential-process authentication, 30-day catalog PITR, 45-day object history, five-minute RPO while running, and 60-minute RTO.
- 2026-09-04: User ratified one-Compose fail-closed operation: Polaris and writers remain unavailable unless pgBackRest repository, credentials, WAL archival, and required base backup are healthy. Optional unprotected startup is superseded.
- 2026-09-04: User selected host-injected short-lived backup session credentials instead of AWS CLI/profile mounting or a credential broker inside PostgreSQL.
- 2026-09-04: User rejected a separately maintained pre-disaster catalog inventory and selected conventional restore validation: restore the catalog in isolation, derive expected tables from the corresponding source-registry revision, enumerate and load restored tables, verify S3 metadata/snapshots and representative queries, and record temporal drill evidence.
- 2026-09-04: User removed the secondary encrypted logical dump as redundant; pgBackRest physical backup plus WAL/PITR is the sole catalog backup mechanism.
- 2026-09-04: User rejected continuous backup monitoring and per-write blocking as overkill. The startup gate plus standard pgBackRest WAL archiving, startup-driven physical-backup cadence, manual maintenance commands, and restore drills is authoritative; five-minute RPO is an objective only while archiving is healthy.
- 2026-09-04: User ratified lifecycle-driven scheduling because the local Compose stack is expected to restart reasonably often: the startup gate applies daily differential and weekly full age thresholds, while no cron or host scheduler is added.
- 2026-09-04: Catalog-protection child 2 passed independent static repair review, then reopened for local image-build and pinned-binary proof. That proof passed; AWS repository/WAL/backup proof remains separately gated.
- 2026-09-04: User rejected the Iceberg recovery bucket and S3 replication after clarifying that it duplicates warehouse storage and requires primary-bucket versioning. Warehouse loss now uses source rebuild; 45-day object recovery is removed and the 60-minute RTO applies only when the primary warehouse remains readable. The 18-create plan is invalid and must not be applied.

## Blockers

None for automation children 1–4. Child 5 is intentionally blocked pending review of the generated OpenTofu plan and explicit live-apply authorization.
