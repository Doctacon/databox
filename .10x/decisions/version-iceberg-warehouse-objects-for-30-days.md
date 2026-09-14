Status: active
Created: 2026-09-10
Updated: 2026-09-10

# Retain Iceberg warehouse object versions for 30 days

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `4e64de0ae1ac6f833b2cbc9fe968ac92003dc80fba9211d6c03886c1e12e6d13`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Context and ratification

Catalog PITR was proved while the primary S3 warehouse remained readable. That does not prove recovery of deleted or overwritten warehouse objects. The earlier decision deliberately rejected warehouse replication and source-bucket versioning in favor of source reconstruction.

After that conflict was explained, the user explicitly requested S3 versioning on the existing Iceberg warehouse bucket and retention of previous versions for 30 days. The preceding explanation distinguished noncurrent versions from live objects and stated that expiry is permanent. On 2026-09-10 the user requested tickets and explicitly approved a bucket-policy denial preventing routine `databox-lake-user` version deletion. This authorizes the records below, not an AWS apply, test deletion, or new recovery implementation in this turn.

## Decision

Supersede `.10x/decisions/superseded/catalog-backup-with-rebuildable-iceberg-warehouse.md` with the following bounded protection model:

- Enable versioning on the existing Iceberg warehouse bucket, without replacing the bucket or introducing another warehouse copy.
- Retain previous/noncurrent object versions for 30 days after they become noncurrent, then make them eligible for permanent S3 Lifecycle expiration. Do not introduce age-based deletion of current objects. Exact retention behavior is owned by `.10x/specs/iceberg-warehouse-version-retention.md`.
- Add an explicit bucket-policy Deny for `s3:DeleteObjectVersion` for the verified `databox-lake-user` principal on warehouse-bucket objects. Do not deny ordinary `s3:DeleteObject` or add Allow privileges through this statement. See `.10x/specs/iceberg-writer-version-delete-denial.md`.
- Do not silently expand that approval into denials of versioning, lifecycle, bucket-policy, or IAM administration. Their effective permissions require inspection; uncovered bypass risk blocks protection sign-off pending an explicit policy decision or accepted limitation.
- Manage the bounded settings through the existing OpenTofu recovery root after checking live ownership and preserving existing policies/rules. Every live apply still requires a fresh exact reviewed plan and separate approval. Old rejected plans remain invalid.
- Retained versions are a candidate recovery source. Do not claim usable Iceberg table recovery until the separately specified recovery workflow and isolated drill prove it.

## Retained constraints

- No secondary Iceberg recovery bucket, replication configuration/role, scheduled warehouse copying, Object Lock, or AWS Backup is introduced. No new recovery-reader role or permission grant is authorized by this record.
- Iceberg snapshots remain the logical rollback mechanism while their referenced objects exist. Complete bucket/account/region loss, expired history, or missing retained versions still require source reconstruction; exact source reconstruction and a warehouse RTO are not guaranteed.
- Catalog protection is unchanged: pgBackRest, dedicated catalog repository/role, one Compose runtime, startup gate, isolated no-cutover restore, 30-day catalog PITR, and 60-minute catalog RTO remain governed by `.10x/specs/polaris-catalog-continuity.md` and `.10x/decisions/startup-only-catalog-backup-gate.md`.
- `.10x/decisions/accept-manual-wal-catchup-for-local-catalog.md` governs local durability: manual authenticated catch-up, accepted loss since the last catch-up, and no continuous five-minute off-machine RPO claim.
- `.10x/decisions/filevault-only-local-opentofu-state.md` continues to govern local ignored state, mode `0600`, FileVault, cleanup exclusion, and reviewed imports after loss. No backend or second state copy is added.
- Existing catalog operator/MFA boundaries and backup-role scope are unchanged. `.10x/decisions/allow-long-lived-local-primary-warehouse-key.md` remains the only local primary-key exception. Do not reuse the catalog-backup role for warehouse operations or persist new credentials.

## Alternatives considered

- **Source rebuild only:** remains the fallback but no longer the sole intended protection from object mistakes; it may not reproduce unavailable upstream history.
- **Second bucket/replication:** still excluded because it adds duplicate storage and infrastructure beyond the selected same-bucket recovery layer.
- **Object Lock:** not selected; immutable retention is a different policy/cost commitment.
- **Deny all deletes:** not selected; routine Iceberg cleanup may use ordinary deletes, which preserve versions once versioning is enabled.

## Consequences

This is a 30-day noncurrent-version lifecycle, not 30 days from original creation, an immutable minimum, or automatic table rollback. Versioning cannot be fully undone. Stored versions increase cost according to actual churn; no numeric spend cap or monitoring service has been approved. Live inspection and the rollout approval must expose the cost and existing-version expiration impact.

A bucket-policy version-delete denial does not stop S3 Lifecycle or protect against an administrator changing protection controls. The unresolved permission boundary and recovery choices have owners in `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md`; they are not unspoken implementation defaults.
