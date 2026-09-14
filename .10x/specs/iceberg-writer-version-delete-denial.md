Status: active
Created: 2026-09-10
Updated: 2026-09-10

# Deny routine-writer permanent object-version deletion

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `d5f681610e42d78b267c51f3909e180428c183a917642826694b118ae1c839ac`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/specs/iceberg-writer-version-delete-denial.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Purpose and authority

Implement only the explicit deletion restriction approved in `.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md`. The actor is the existing IAM user `databox-lake-user`; its exact account-qualified ARN MUST be established by read-only inspection. It MUST NOT be inferred from an unrelated login or applied to all principals.

## Policy behavior

- The existing warehouse bucket policy MUST contain an explicit `Deny` for exactly `s3:DeleteObjectVersion`, scoped to that verified user ARN and `arn:aws:s3:::<verified-warehouse-bucket>/*`.
- The new statement MUST NOT deny `s3:DeleteObject`, ordinary reads/writes, or unrelated principals. It MUST NOT grant any new Allow authority. Existing policies still decide whether otherwise-unaffected operations are permitted.
- The statement MUST coexist with, not replace or weaken, existing TLS, access, integration, encryption-related, or other bucket-policy protections. Existing policy ownership and contents MUST be inspected before adoption; unknown ownership or conflicting policy state blocks implementation.
- Catalog-backup resources/permissions, credentials, CI principal grants, and the primary bucket's public-access/encryption settings MUST remain unchanged.
- The denial applies to version-specific deletion of data versions and delete-marker versions. Any restoration method requiring delete-marker removal therefore needs separate operator authority or another ratified recovery method, not an exemption for the routine writer.

## Boundaries not yet ratified

The user approved version deletion denial, not an automatic expansion into `s3:PutBucketVersioning`, `s3:PutLifecycleConfiguration`, `s3:PutBucketPolicy`, `s3:DeleteBucketPolicy`, or IAM administration restrictions. These are candidate additional controls only. Inspect direct and relevant assumable-role authority through the existing audit owner `.10x/tickets/2026-09-05-establish-primary-warehouse-session-credentials.md`.

If the routine writer can change protection controls, remove the Deny, or assume an identity that bypasses it, record that result. Protection sign-off and rollout readiness MUST remain blocked until the user approves exact additional controls or explicitly accepts the named limitation. Do not invent an administrator exemption, IAM grant, new role, or accepted risk.

S3 Lifecycle bypasses bucket-policy denial. This contract intentionally permits the separately configured 30-day expiration and does not promise immutable retention against administrators or account compromise.

## Acceptance scenarios

- **Explicit Deny wins:** with otherwise broad object Allow permissions, a version-specific delete request by the exact routine writer matches the explicit Deny on warehouse-bucket object versions.
- **Routine cleanup preserved:** an ordinary delete without a version ID is not denied by this new statement. After versioning enablement its normal S3 behavior is a delete marker, subject to existing authorization.
- **Bounded actor/target:** another principal, another bucket, and the catalog-backup bucket do not match this new Deny. The statement itself grants none of them access.
- **No policy clobber:** all unrelated existing statements and their effects survive adoption; ownership/merge uncertainty blocks the plan.
- **Bypass visibility:** a delete denial alone MUST NOT be labeled complete writer isolation when relevant control-plane or role-assumption permissions are unknown or permit circumvention.

## Evidence and exclusions

Static tests MUST inspect the actual composed principal/action/resource semantics, not merely find a Deny string somewhere in the file. Live denial proof, when separately authorized, MUST target only run-owned disposable versions and distinguish the expected policy denial from unrelated credential/network failures. No deletion attempt against authoritative warehouse objects is authorized.

The broader least-privilege audit retains its existing ticket; passing this specific policy test does not close that audit. New credentials, privilege grants, maintenance-policy changes, and production restores are excluded.
