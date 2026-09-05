Status: blocked
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: .10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md

# Provision and prove Polaris catalog backups

## Scope

After explicit user approval of a fresh catalog-only OpenTofu plan, apply only the reviewed infrastructure in the authenticated AWS account, preserve local OpenTofu state, assume the least-privilege backup role, initialize and verify the pgBackRest repository, and create and inspect the first physical backup plus WAL archive before restore automation begins.

## Acceptance criteria

- The user reviews and explicitly approves the exact non-secret OpenTofu plan before apply.
- Apply creates only the reviewed same-account, `us-west-1` resources and policies.
- Local state is preserved at `infra/recovery/terraform.tfstate` on the FileVault-protected host and its encrypted machine backup.
- Root is used only for approved bootstrap apply and role-access verification, then logged out; Compose receives only short-lived catalog-backup-role credentials.
- pgBackRest stanza check, first full backup, WAL archive check, and repository verification/info complete successfully.
- Evidence records successful repository access, first physical backup, WAL archive round trip, and repository metadata without claiming restore or RPO/RTO proof.
- Retained catalog backups and local state are preserved.

## Explicit exclusions

- Unreviewed `tofu apply`.
- Restore automation, restore execution, timed RPO/RTO proof, or production catalog cutover.
- Destructive testing against authoritative warehouse objects.
- Iceberg recovery buckets, replication, object restoration, or source-bucket versioning.
- Cross-account or cross-region changes.

## References

- `.10x/decisions/startup-only-catalog-backup-gate.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md`
- `.10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md`

## Evidence expectations

Record the approved replacement catalog-only plan hash/summary, durable local-state location and backup confirmation, apply result, resource identities without secrets, root logout, assumed-role identity, backup/WAL status, and remaining same-account/same-region risk.

## Progress and notes

- 2026-09-04: Opened as the live rollout owner; automation was authorized before AWS mutation.
- 2026-09-04: Default-profile authentication failed before planning; no mutation occurred.
- 2026-09-04: Three generated plans were invalidated in sequence by removal of Iceberg replication, addition of TLS enforcement, and then independent findings for multipart abort, rollout ordering, and state ownership. None was applied.
- 2026-09-04: User ratified proof-first ordering: approved infrastructure and a real pgBackRest backup/WAL round trip must succeed before isolated restore automation. Local state is operator-owned at `infra/recovery/terraform.tfstate`, protected by FileVault and normal encrypted machine backup; no remote backend is added.
- 2026-09-04: Repaired plan evidence `.10x/evidence/2026-09-04-catalog-only-final-opentofu-plan.md` records binary hash `77cf23e243859dac24974be21adfb7f5bdf94bb6ec8168cf70039ddda3b69212` and 8 create / 0 change / 0 destroy. It is not approved or applied.
- 2026-09-04: Independent review `.10x/reviews/2026-09-04-catalog-only-final-plan-review.md` passed with no findings. Parent immediately reproduced the exact binary hash. The plan is safe to present but remains unauthorized until the user explicitly approves this hash for apply.

## Blockers

Explicit user approval of exact binary plan hash `77cf23e243859dac24974be21adfb7f5bdf94bb6ec8168cf70039ddda3b69212`. All earlier plans are rejected and must not be applied.
