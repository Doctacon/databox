Status: open
Created: 2026-09-10
Updated: 2026-09-10
Parent: None
Depends-On: None

# Protect and prove recovery of Iceberg warehouse object versions

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `5f4d17e283d84f1eeb5bba43b972504e302e33402553f7487d1b2f71e090bd2f`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Aggregate scope — plan, not executable

Plan the user's selected same-bucket versioning, 30-day noncurrent history, explicit `databox-lake-user` version-delete denial, reviewed deployment, and separately defined recovery-tool/table-proof work. No child is launched by ticket creation. This is new warehouse protection, not reopening the rejected replica design or expanding the completed catalog recovery implementation.

## Governing records

- `.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md`
- `.10x/specs/iceberg-warehouse-version-retention.md`
- `.10x/specs/iceberg-writer-version-delete-denial.md`
- `.10x/specs/iceberg-object-version-restore.md` — draft; not implementation authority.
- `.10x/research/2026-09-10-s3-warehouse-versioning-semantics.md`

## Child sequence

1. `.10x/tickets/2026-09-10-inspect-iceberg-warehouse-protection-prerequisites.md` — open; read-only discovery of exact target, rule/policy/state ownership, relevant access and cost/expiration exposure. Reuses the existing primary-writer IAM audit owner.
2. `.10x/tickets/2026-09-10-declare-iceberg-warehouse-version-protection.md` — blocked on inspection; add bounded OpenTofu settings, resource-scoped tests, runbook, and a fresh reviewable plan. No apply.
3. `.10x/tickets/2026-09-10-apply-iceberg-warehouse-version-protection.md` — blocked on the reviewed exact plan, operator/maintenance readiness, cost/expiration acknowledgement, and explicit live approval. Apply only approved changes and read back configuration; no destructive proof.
4. `.10x/tickets/2026-09-10-build-iceberg-object-version-restore.md` — blocked shaping/implementation owner for exact recovery behavior. The draft must be ratified before implementation or tests encode it.
5. `.10x/tickets/2026-09-10-prove-iceberg-object-version-recovery.md` — blocked on deployment, reviewed recovery tooling/specification, and a separately approved disposable drill plan.

After inspection, record-only recovery shaping can proceed independently of infrastructure implementation. Configuration/policy changes share one root/state and have one writer; never parallelize their mutations. Tool implementation may later run in isolation alongside rollout only after its own spec/authorization gate. The live drill requires both branches.

## Aggregate acceptance and evidence

- Exact existing bucket/account/region and policy/lifecycle owner are recorded; no competing configuration owner or bucket replacement is introduced.
- Versioning and 30-day noncurrent-only expiration are reviewed and read back after approved deployment. Current data is not age-expired by the new rule.
- The exact routine writer receives an explicit version-delete Deny without new grants or loss of ordinary-delete behavior from this statement. Unknown/bypass permissions are not presented as complete protection.
- The restore contract is active and independently reviewed before code/live use; a separately authorized disposable table proof demonstrates coherent snapshot and data recovery, not only an object copy.
- Catalog behavior/resources, primary data, unrelated files, and prior preserved recovery resources remain untouched except for the exact later-approved write boundaries.
- Each child maps criteria to durable evidence and review, states limits, and completes its retrospective before closure. Configuration success, direct denial proof, and table recovery are separate claims.

## Assumption and side-effect inventory

| Item | Authority / state |
| --- | --- |
| Existing warehouse bucket versioning; 30 days after becoming noncurrent | User-ratified after explanation; lifecycle deletes eligible prior versions permanently. Actual bucket state/other owners require inspection. |
| Explicit `s3:DeleteObjectVersion` Deny for routine `databox-lake-user` | User-ratified; exact ARN and policy composition require inspection. |
| Deny changes to lifecycle/versioning/bucket policy, or indirect IAM/role bypasses | Not ratified. Audit through existing owner; additional controls or acceptance of exposed risk require exact approval. |
| Extra storage cost | Full previous object copies incur charges; no numeric budget/cap approved. Estimate/exposure and operator acknowledgement gate rollout. No monitoring service is added. |
| Existing old versions becoming immediately expiration-eligible | Technical finding; quantify and obtain rollout acknowledgement before apply. |
| AWS first-enable propagation / writes | AWS recommends 15 minutes without PUT/DELETE; maintenance owner, coordination and interruption authority unresolved for live rollout. No implicit service stop. |
| Recovery identity, destination, selection, failures/retries and cleanup | Blocked in the draft restore specification; no defaults implemented. |
| Live launch / operational owner | User approves exact plan/drill; named authenticated operator and write boundary must be established before execution. |
| Notifications, schedules, automatic failover/cutover | Excluded; no recipients, cadence or service owner invented. |

## Explicit exclusions and existing owners

No second warehouse bucket, replication, Object Lock, AWS Backup, routine Iceberg maintenance, broader IAM grants, automatic recovery/cutover, or deletion of preserved catalog-drill resources. No changes to `uv.lock`, personal calendar files, source data/model semantics, or active-stack lifecycle.

`.10x/tickets/2026-09-05-establish-primary-warehouse-session-credentials.md` remains the full least-privilege audit owner. `.10x/tickets/2026-09-04-run-timed-catalog-recovery-drill.md` retains its separate recovery-resource cleanup blocker. The earlier catalog plan `.10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md` is not closed or retroactively redefined here.

## Progress and notes

- 2026-09-10: User requested tickets only and explicitly approved routine-writer object-version deletion denial. Inspected current source/records and official AWS lifecycle/versioning behavior. Created focused contracts, a draft recovery contract, and bounded children. No AWS authentication, plan/apply/import, test, implementation, service operation, or object write occurred.

- 2026-09-10: Records-only validation passed: common headers and local record references checked for all 12 new/moved records; six-ticket parent/dependency graph is acyclic; no references remain to the moved decision's old path; new/moved Markdown whitespace and `git diff --check` pass. Inspected the existing-record diff: changes are scoped supersession/cross-links, catalog-spec boundary clarification, and append-only ownership notes. No application test or AWS verification ran; pre-existing `uv.lock` changes remain untouched.

## Blockers

Aggregate completion awaits all children. Only the read-only inspection child is ready to start upon execution authorization. Live readiness and restoration semantics remain explicit gates above; creating these tickets does not approve them.
