Status: active
Created: 2026-09-10
Updated: 2026-09-10

# Iceberg warehouse object-version retention

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `70394a7c25c4df5787442360e5593fb9e888c7f2fbfc78a4dc41f96720221954`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/specs/iceberg-warehouse-version-retention.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Purpose, authority, and scope

Define the selected same-bucket retention layer under `.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md`. This is desired behavior, not a claim that AWS is configured. The target is the existing bucket selected by `DATABOX_AWS_S3_BUCKET`, not the catalog-backup bucket. Live identity and configuration ownership MUST be verified before adopting settings.

The user's bucket-level request covers previous object versions across that warehouse bucket. Versioning is intrinsically bucket-wide; the proposed noncurrent lifecycle uses the same bucket-wide scope, including metadata, manifests, data/delete files and test prefixes. If inspection finds another owner's data or conflicting retention obligations, implementation MUST block for an explicit scope decision rather than choose a prefix exception or delete unrelated history.

## Behavior

1. The existing bucket MUST have versioning `Enabled`. Automation MUST NOT create, replace, empty, or destroy it, enable `force_destroy`, or change the warehouse location.
2. Existing live objects MUST NOT be rewritten just to acquire version IDs; pre-enable objects with version ID `null` MUST be recognized as legitimate existing state. No historical recovery before enablement is promised.
3. The lifecycle MUST use `NoncurrentVersionExpiration` with `NoncurrentDays=30`. The clock starts when an object version becomes noncurrent. It MUST NOT use current-object age expiration or a keep-N-versions exception as a substitute.
4. At expiry, noncurrent versions become eligible for permanent deletion under AWS's UTC rounding and asynchronous processing. Documentation MUST NOT promise deletion at exactly 720 hours or recoverability after expiry.
5. This change MUST NOT introduce current-object expiration, storage-class transitions, delete-marker cleanup, multipart-abort rules, or Iceberg snapshot/orphan/compaction jobs. Existing rules MUST be inventoried and preserved unless an explicit supersession authorizes changing them. Overlapping/conflicting rules MUST block rather than silently shorten retention.
6. OpenTofu MUST manage only the required existing-bucket settings within `infra/recovery/`, retaining catalog-resource addresses and state. Existing lifecycle/policy management MUST have one owner; no competing configuration resource or blind replacement is permitted. Necessary imports require reviewed state-only authorization separately from AWS mutation.
7. Before live enablement, the operator MUST review existing-version expiration exposure and cost assumptions and coordinate writes for AWS's first-enable propagation window. AWS recommends no object PUT/DELETE for 15 minutes after first enablement; this contract does not authorize stopping any running service/job.
8. A fresh exact plan and independent review MUST precede explicit apply approval. Absent access, unexpected live drift, conflicting ownership/rules, or an unknown target MUST fail closed. No automatic retry/apply/destroy is allowed.

## Acceptance scenarios

- **Overwrite:** given an enabled bucket and an existing key, a PUT creates a new current version and preserves the prior version as noncurrent. It does not immediately delete the prior bytes.
- **Ordinary delete:** deleting without a version ID creates a delete marker and preserves the former current version until eligible expiration or another authorized permanent delete.
- **Age:** a live object older than 30 days MUST NOT be expired by the new rule. An object becoming noncurrent today is governed by 30 noncurrent days, irrespective of its original creation date.
- **Existing history:** if previously noncurrent versions are already older than 30 days, the plan approval MUST disclose their potential immediate eligibility; application is not a fresh 30-day grace period.
- **Configuration conflict:** an existing lifecycle rule or owner incompatible with this scope blocks the change; it is never overwritten by an empty/new template.

## Evidence and limits

Static evidence MUST inspect the resource-scoped lifecycle/versioning configuration and preserve regression coverage for catalog isolation, account/region checks, TLS/encryption/public-access controls, and no replication. Live configuration read-back belongs to the separately authorized deployment ticket. No accelerated expiration test may shorten the actual warehouse retention.

The companion permission contract is `.10x/specs/iceberg-writer-version-delete-denial.md`. Versioning/lifecycle configuration alone MUST NOT be presented as proof of table recovery, full warehouse PITR, immutable retention, or account/regional disaster recovery. Recovery workflow semantics remain draft at `.10x/specs/iceberg-object-version-restore.md`.
