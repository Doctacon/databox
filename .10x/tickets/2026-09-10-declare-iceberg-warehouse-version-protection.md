Status: blocked
Created: 2026-09-10
Updated: 2026-09-10
Parent: .10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md
Depends-On: .10x/tickets/2026-09-10-inspect-iceberg-warehouse-protection-prerequisites.md

# Declare and review warehouse version protection

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `44ddee597fd5386c78da05049d626841bc5ea13af0bc5703bcb9e92e67c12091`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/tickets/2026-09-10-declare-iceberg-warehouse-version-protection.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Scope

After prerequisite inspection resolves target/ownership conflicts, extend the existing `infra/recovery/` root with the smallest settings-only adoption of the primary warehouse: enabled versioning, 30-day noncurrent expiration, and the approved exact routine-writer version-delete Deny. Add focused tests/runbook instructions and produce a fresh exact reviewable OpenTofu plan. No AWS apply.

## Governing references

- `.10x/specs/iceberg-warehouse-version-retention.md`
- `.10x/specs/iceberg-writer-version-delete-denial.md`
- `.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md`
- `.10x/decisions/filevault-only-local-opentofu-state.md`
- `infra/recovery/{main,variables,versions,outputs}.tf`, `infra/recovery/terraform.tfvars.example`, `tests/platform/test_recovery_infrastructure.py`, `docs/runbook.md`.
- The inspection dependency's evidence, once recorded.

## Acceptance criteria derived from active specs

- Existing bucket identity and writer ARN are explicit validated non-secret inputs, never credentials or inferred from whichever account is logged in. The warehouse cannot alias the catalog-backup target.
- Settings resources never create/replace/destroy the primary bucket. Existing policies/rules have one owner, are explicitly composed/preserved, and are not blindly replaced. Catalog-resource addresses, permissions and state remain intact.
- Resource-scoped tests establish `Enabled`, noncurrent-only 30 days, and the exact Deny principal/action/object ARN. They establish no new ordinary-delete denial or Allow grants, no current-data expiration, no replica or new maintenance behavior.
- Narrow the old global “no primary/iceberg/version action anywhere” tests only where the new active specs require it. Preserve catalog-role no-version-access checks and all unrelated security, state, same-account/region and no-replication assertions. Do not delete protective coverage to make configuration pass.
- OpenTofu formatting/validation, focused hermetic policy tests and applicable secret/diff checks pass. Verify command side effects first; do not update `uv.lock` or unrelated artifacts.
- Runbook distinguishes version history, expiration, restoration, source rebuild, and catalog recovery. It documents the exact operator approval/propagation gate without asserting a new recovery command exists.
- Once state/adoption and planning access are explicitly authorized, generate and hash a fresh plan from the owned root. Independent review confirms only approved settings change, no unexpected drift, no bucket/data/backup destruction, and no secrets. Any necessary state-only import is separately reviewed/authorized; do not plan over existing unmanaged conflicting resources.

## Exclusions

Live AWS writes/apply, production object tests, writer/service interruption, broad IAM audit or new grants/control-plane Denies, new buckets/replication, restore tooling, and old catalog-drill cleanup. Existing full IAM audit remains with `.10x/tickets/2026-09-05-establish-primary-warehouse-session-credentials.md`.

## Evidence expectations

Record changed files, rendered/composed policy and lifecycle semantics, exact validation output, preserved safety assertions, plan hash/action summary, state ownership and imports (if separately authorized), independent review, and explicit no-AWS-write limits.

## Progress and notes

- 2026-09-10: Created after active retention/deletion specs. Not executable until the inspection supplies a safe ownership/adoption contract. No code or tests were written.

## Blockers

- Inspection dependency: actual identity, current rules/policy, conflicting owners/retention and state adoption remain unknown.
- Any newly required control-plane permissions restriction or accepted bypass limitation must be exactly ratified first; `DeleteObjectVersion` approval does not supply it.
- Implementation/planning and any needed state import require subsequent execution authorization. No authorization is inferred from creating this ticket.
