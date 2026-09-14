Status: blocked
Created: 2026-09-10
Updated: 2026-09-10
Parent: .10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md
Depends-On: .10x/tickets/2026-09-10-declare-iceberg-warehouse-version-protection.md

# Apply reviewed warehouse version-protection settings

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `57bb7125dee37a8177a310ec5acaf84bd5df8ce7df0a3fcd703fc7d5bad8ee22`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/tickets/2026-09-10-apply-iceberg-warehouse-version-protection.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Scope

Apply only the exact reviewed warehouse-settings plan after explicit approval, then read back versioning, lifecycle and bucket policy. This outcome is configuration deployment, not object restoration or deletion testing.

## Governing references

- `.10x/specs/iceberg-warehouse-version-retention.md`
- `.10x/specs/iceberg-writer-version-delete-denial.md`
- `.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md`
- `.10x/decisions/filevault-only-local-opentofu-state.md`
- Inspection evidence and the dependency's exact plan/hash/review, when available.

## Acceptance criteria derived from active specs

- Record the explicit approval of the exact plan/hash, authenticated operator identity/account, local state lineage, read-back procedure, and any required imports. Drift or a changed plan invalidates approval and stops execution.
- Before apply, the user acknowledges irreversible versioning enablement, permanent eligibility of already-old noncurrent versions, affected scope, and estimated storage-cost exposure/limits. No numeric cap or automatic spending response is assumed.
- Resolve and document control-plane/assumable-role bypass findings with the existing IAM audit owner before protection sign-off. Extra policies cannot enter the apply under this ticket without their own explicit ratification and reviewed plan.
- Establish the live writer/maintenance owner and explicit coordination authority. For first enablement, follow AWS's recommended 15-minute no-PUT/DELETE propagation period; do not restart/stop jobs, services, or CI implicitly. If coordination is unavailable, do not apply.
- Apply only approved settings. Read-back shows versioning enabled, the composed noncurrent-only 30-day rule, and exact version-delete Deny; all preserved policy/rule and catalog-backup settings remain coherent with the reviewed plan.
- Evidence distinguishes observed configuration from time-elapsed lifecycle deletion, effective live denial, and Iceberg recovery. Those latter outcomes are not proven by this ticket.
- Failures stop without blind retry, automatic rollback/suspension, permanent object deletion, or cleanup. Preserve secret-free diagnostics and actual partial state in this ticket for a reviewed next action.

## Exclusions

No bucket recreation, new storage/roles, authoritative object writes/deletions, synthetic drill, source refresh, catalog cutover/restart, cleanup of retained resources, or credential persistence. No shortening retention to accelerate verification.

## Evidence expectations

Exact plan/hash/approval, redacted identity, pre/post configuration, apply result, propagation/write-coordination evidence and limits, preserved state/resources, and independent review. A configuration read-back is not a table-recovery claim.

## Progress and notes

- 2026-09-10: Created as a separately gated live deployment ticket. User requested tickets, not an AWS mutation. No plan has been generated for this change.

## Blockers

Reviewed exact plan and explicit apply approval; planning/adoption completion; operator permissions; existing-history/cost acknowledgement; protection-bypass resolution; and authorized write coordination are all outstanding. This ticket is not executable.
