Status: open
Created: 2026-09-10
Updated: 2026-09-10
Parent: .10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md
Depends-On: None

# Inspect existing warehouse protection prerequisites

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `4f427cab26e57b4205cdf674cc2680ea7cfc7742e9e93a09ce93ec3385677f8f`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/tickets/2026-09-10-inspect-iceberg-warehouse-protection-prerequisites.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Scope

Produce a read-only, secret-free adoption assessment for the selected warehouse bucket before any configuration code/plan relies on its ownership or current settings. This is an inspection ticket, not authority to provision, import state, stop writers, modify policies, or test deletion.

## Governing references

- `.10x/specs/iceberg-warehouse-version-retention.md`
- `.10x/specs/iceberg-writer-version-delete-denial.md`
- `.10x/research/2026-09-10-s3-warehouse-versioning-semantics.md`
- `.10x/decisions/filevault-only-local-opentofu-state.md`
- `.10x/tickets/2026-09-05-establish-primary-warehouse-session-credentials.md` — existing full IAM audit owner.
- `infra/recovery/`, `packages/databox/databox/config/settings.py`, `.github/workflows/polaris-iceberg-integration.yaml`, `tests/platform/test_recovery_infrastructure.py`.

## Acceptance criteria

1. Establish the configured warehouse bucket, actual owner account/region, configured prefixes, exact `databox-lake-user` ARN, and distinction from the catalog-backup bucket. Compare current observations to local configuration and prior evidence; never substitute source defaults for live proof.
2. Read current versioning, lifecycle, bucket policy, relevant public-access/encryption/Object Lock settings, and configuration/state ownership. Record absent configuration separately from access denied/unknown. Inspect local state only through a bounded secret-safe projection; never dump credentials or full state.
3. Identify existing lifecycle overlaps, immediately expiration-eligible history, and any other data/owner affected by bucket-wide versioning/retention. Use bounded metadata/listing or existing metrics, not downloads/full warehouse scans. Report sampling limits; do not claim a total from a partial listing.
4. Record available current/noncurrent storage and churn/cost information with source/date/limits, or explicitly record unavailable metrics. Identify the cost and old-history deletion acknowledgement required for rollout; do not invent a spend threshold.
5. With the existing IAM audit owner, establish relevant direct and role-assumption authority for version deletion and changing lifecycle/versioning/bucket policy. If administrative visibility is absent, update that existing blocker and mark downstream readiness blocked. A denied IAM read is not evidence of least privilege. Do not duplicate or close the full audit.
6. Identify a safe single-owner OpenTofu adoption path for versioning/lifecycle/policy, including any exact imports requiring later authorization, and the authenticated operator/maintenance prerequisites for first-enable propagation. Discovery does not grant missing permissions or authorize pausing writers.
7. Store reproducible evidence with sanitized commands/results, identity/observation timestamps, confirmed facts versus unknowns, and a ready-or-blocked disposition for each downstream concern. Link evidence into the parent and affected child/audit owner. A fully documented unavailable prerequisite may complete inspection but cannot release downstream work.

## Execution boundaries and evidence

Only read local configuration/records and authorized remote GET/LIST/identity/policy inspection. Request human assistance for an existing read-capable identity if needed; do not retrieve credentials from unrelated stores, create credentials, assume root authorization from older work, or persist/export secrets. No AWS write, login/cache manipulation without authorization, `tofu init/plan/import/apply`, tests, refresh, Docker operation, payload reads, or object probe.

## Progress and notes

- 2026-09-10: Created from the user's ticket request. Source proves the current OpenTofu root is catalog-only and the primary-writer effective-policy audit is already owned. Live warehouse configuration has not been read for this new workstream.

## Blockers

None for beginning authorized local read-only inspection. Remote findings remain unknown; unavailable credentials/permissions must be recorded as blockers rather than guessed. This open ticket has not been authorized for execution by the records-only request.
