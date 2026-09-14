Status: open
Created: 2026-09-04
Updated: 2026-09-10
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: None

# Simplify recovery infrastructure to catalog-only protection

> Publication redaction (2026-09-12): deployment account/bucket literals are replaced by labeled placeholders; generic principal labels are retained. This historical record is not a fresh approval or an executable plan. Original conclusions and verification limits still apply.
> Source revision: `027af8b4271d60ffc193967d092b5d2497af13ad`. Original-artifact SHA-256 (NOT this redacted text): `ad23bff030e4343b9659d396c7142eea611f9a90ddd15cd8a28b5cce94b6db9e`.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry with `source_kind=committed-head` and `source_path` equal to this public path. Any preexisting plan/export hashes below identify original artifacts, not this changed counterpart.


> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `f7eba2efe290520eacea6855f2c351fa02857c09b833ac599c10a28a53080504`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Scope

Remove the rejected Iceberg object-recovery plane from `infra/recovery/` and its operator documentation/tests. Preserve only the encrypted Polaris pgBackRest backup bucket and least-privilege catalog-backup role. Generate a fresh non-mutating OpenTofu plan using the already ratified account, region, profile, primary-bucket-derived catalog backup name, and operator-principal decision after the root-trust question is separately resolved.

## Acceptance criteria

- OpenTofu no longer manages an Iceberg recovery bucket, source-bucket versioning, replication configuration, replication role/policy, recovery-reader role/policy, recovery bucket policy, 45-day lifecycle, or related outputs.
- The existing primary `<REDACTED_BUCKET_1>` bucket is not mutated by the plan.
- Catalog backup bucket versioning, encryption, public-access block, lifecycle, and least-privilege pgBackRest role remain; the role can abort its own multipart uploads but has no object-version permissions.
- Local state ownership, encrypted backup, cleanup exclusion, and loss/import procedure are explicit.
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

- `.10x/decisions/superseded/catalog-backup-with-rebuildable-iceberg-warehouse.md`
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
- 2026-09-04: Generated the fresh TLS-enforced catalog-only plan recorded at `.10x/evidence/2026-09-04-catalog-only-tls-recovery-opentofu-plan.md`. Binary hash `4656b197fd1039d4972c614e828ad0be92128fec6c6f83d4a6a6fd88abc98837`; exact text hash `b953de92e2cb80be7d677856cb3c5f9f38345a61f5fe1c0fbe41e4fe140af9fb`; exactly 8 create, 0 change, 0 destroy, plus one deferred local policy-document read. It contains the TLS-deny bucket policy and no primary-bucket, Iceberg, or replication action. No apply or AWS mutation ran.
- 2026-09-04: Independent review `.10x/reviews/2026-09-04-catalog-only-tls-plan-review.md` found the plan must not be applied: backup IAM lacks object-scoped multipart abort, rollout ordering still places apply after restore automation despite the user's corrected proof-first sequence, and local state ownership/preservation is undefined.
- 2026-09-04: Repaired all three findings: added object-scoped multipart abort without version-history authority; reordered provisioning and real backup/WAL proof before restore automation; and ratified ignored local state at `infra/recovery/terraform.tfstate`, protected by FileVault and normal encrypted machine backup with explicit loss/import handling. Plan hash `4656b197fd1039d4972c614e828ad0be92128fec6c6f83d4a6a6fd88abc98837` is invalid and MUST NOT be applied.
- 2026-09-04: Fresh non-mutating plan evidence `.10x/evidence/2026-09-04-catalog-only-final-opentofu-plan.md` records binary hash `77cf23e243859dac24974be21adfb7f5bdf94bb6ec8168cf70039ddda3b69212`, exact text, and 8 create / 0 change / 0 destroy. Twenty-four focused tests and OpenTofu/Ruff/format/diff validation pass. No apply or AWS mutation ran.

- 2026-09-10: Subsequent user-approved same-bucket version protection is owned by `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md` under `.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md`. This ticket documents the earlier removal of the rejected recovery plane; its historical no-source-versioning constraints MUST NOT cause a later executor to remove the newly approved settings. No replica is reauthorized, old plans remain invalid, and this cross-link does not close or repair this ticket's earlier closure obligations.

## Blockers

Independently review the fresh exact plan, then obtain explicit user approval before apply. All earlier plans remain historical evidence and must not be applied.
