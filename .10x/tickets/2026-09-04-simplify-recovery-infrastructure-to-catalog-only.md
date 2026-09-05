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
- 2026-09-04: Removed the complete rejected Iceberg recovery plane and all primary warehouse inputs from OpenTofu. The remaining inventory is seven catalog-only resources (bucket, versioning, AES256 encryption, public-access block, 30-day lifecycle, backup role, inline policy), one local IAM trust-policy document, and three outputs. Updated the example, runbook, and focused tests to require source rebuild and prove no primary/replication/recovery surface remains. OpenTofu formatting/validation, 22 focused tests, Ruff, format, focused MyPy, secret scan, and diff checks pass without provider/AWS calls. No plan, apply, service, volume, backup, or restore ran.
- 2026-09-04: User ratified account root only for the initial reviewed bootstrap apply, followed by short-lived assumption of the created least-privilege catalog-backup role and root logout. Authenticated profile `databox-debug` generated the fresh catalog-only plan recorded at `.10x/evidence/2026-09-04-catalog-only-recovery-opentofu-plan.md`: exactly 7 create, 0 change, 0 destroy, with no primary-bucket, Iceberg, or replication resource. No apply or AWS mutation ran.
- 2026-09-04: Added the standard catalog-bucket transport policy: deny all `s3:*` requests to the bucket and object ARNs when `aws:SecureTransport` is `false`. Public-access blocking, AES256 at rest, pgBackRest client encryption, versioning/lifecycle, and backup-role permissions are unchanged. This infrastructure edit invalidates catalog-only plan commit `ba60000` and binary hash `9f01f222d146efa13ef66d13992b8bb9f190198a9caa1a9bca30d1d53fd91292`; that plan MUST NOT be applied.

## Blockers

Generate and independently review a fresh exact plan containing the transport policy before any explicit apply approval. Both earlier plans remain historical evidence and must not be applied.
