Status: open
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: None

# Simplify recovery infrastructure to catalog-only protection

## Scope

Remove the rejected Iceberg object-recovery plane from `infra/recovery/` and its operator documentation/tests. Preserve only the encrypted Polaris pgBackRest backup bucket and least-privilege catalog-backup role. Generate a fresh non-mutating OpenTofu plan using the already ratified account, region, profile, primary-bucket-derived catalog backup name, and operator-principal decision after the root-trust question is separately resolved.

## Acceptance criteria

- OpenTofu no longer manages an Iceberg recovery bucket, source-bucket versioning, replication configuration, replication role/policy, recovery-reader role/policy, recovery bucket policy, 45-day lifecycle, or related outputs.
- The existing primary `databox-lake` bucket is not mutated by the plan.
- Catalog backup bucket versioning, encryption, public-access block, lifecycle, and least-privilege pgBackRest role remain.
- Active docs and tests describe catalog backup plus source rebuild, not object recovery.
- The superseded plan at `.10x/evidence/2026-09-04-recovery-opentofu-plan.md` remains historical and is never applied.
- OpenTofu formatting/validation and focused tests pass hermetically.
- A fresh exact plan is stored and hashed only after the operator principal is ratified; it is not applied.

## Explicit exclusions

- `tofu apply` or any AWS mutation.
- S3 source versioning, replication, batch replication, or scheduled copying.
- Changes to pgBackRest runtime behavior.
- Restore automation or source-refresh behavior changes.

## References

- `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/evidence/2026-09-04-recovery-opentofu-plan.md`
- `infra/recovery/`

## Evidence expectations

Record changed resources and outputs, exact static validation, proof that no primary-bucket resource remains, fresh plan hash/action summary when unblocked, and explicit no-apply limits.

## Progress and notes

- 2026-09-04: Opened after the user selected no independent Iceberg warehouse copy. The existing 18-create plan is invalid and must not be applied.

## Blockers

Fresh plan generation is blocked until the operator principal is ratified. Code simplification itself is executable without AWS access.
