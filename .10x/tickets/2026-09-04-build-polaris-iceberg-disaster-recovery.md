Status: open
Created: 2026-09-04
Updated: 2026-09-04
Parent: None
Depends-On: None

# Build Polaris and Iceberg disaster recovery

## Aggregate outcome

Deliver reviewable, tested automation for the ratified Polaris catalog and Iceberg object recovery architecture, then separately provision and prove it only after explicit approval of the OpenTofu plan.

## Child plan

1. `.10x/tickets/2026-09-04-declare-aws-recovery-infrastructure.md` — add OpenTofu for the two same-account, same-region buckets, retention, replication, and least-privilege IAM. Can begin immediately.
2. `.10x/tickets/2026-09-04-add-pgbackrest-catalog-protection.md` — add pgBackRest, renewable credential-process integration, backup/check/inventory commands, and tests. Can proceed in parallel with child 1 against the defined interfaces.
3. `.10x/tickets/2026-09-04-build-isolated-catalog-recovery-drill.md` — add fail-closed PITR restore and Iceberg/catalog validation after children 1 and 2 establish inputs.
4. `.10x/tickets/2026-09-04-verify-disaster-recovery-automation.md` — adversarially review and verify the complete non-live automation and documentation.
5. `.10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md` — blocked live rollout and timed restore proof; begins only after the user reviews the OpenTofu plan and explicitly authorizes AWS mutation.

Children 1 and 2 are parallelizable in isolated worktrees. Child 3 depends on both. Child 4 depends on the first three. Child 5 depends on verified automation and separate authorization.

## Integration points

- `compose.iceberg.yml` remains the local Polaris/PostgreSQL runtime.
- OpenTofu outputs and environment-variable names form the boundary between AWS infrastructure and local backup tooling.
- `Taskfile.yaml` and `docs/runbook.md` expose operator commands.
- Recovery validators reuse the canonical source registry and Polaris client rather than a second source/table list.
- No child may alter provider behavior, SQLMesh model semantics, source schedules, or primary Iceberg authority.

## Aggregate acceptance criteria

- Repository automation covers both PostgreSQL catalog PITR and Iceberg object recovery without long-lived credentials.
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
- `.10x/decisions/polaris-iceberg-backup-and-recovery.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/specs/iceberg-object-recovery.md`
- `docs/adr/0008-polaris-iceberg-raw-authority.md`

## Progress and notes

- 2026-09-04: Opened after the user approved execution. User selected automation-first OpenTofu delivery, same AWS account and `us-west-1`, separate catalog and Iceberg recovery buckets, renewable credential-process authentication, 30-day catalog PITR, 45-day object history, five-minute RPO while running, and 60-minute RTO.

## Blockers

None for automation children 1–4. Child 5 is intentionally blocked pending review of the generated OpenTofu plan and explicit live-apply authorization.
