Status: open
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: .10x/tickets/2026-09-04-declare-aws-recovery-infrastructure.md, .10x/tickets/done/2026-09-04-add-pgbackrest-catalog-protection.md, .10x/tickets/2026-09-04-build-isolated-catalog-recovery-drill.md

# Verify disaster-recovery automation

## Scope

Adversarially review the integrated OpenTofu, pgBackRest, credential delivery, registry-derived restore validation, restore safety, Iceberg recovery, tests, and operator documentation. Repair only findings within the ratified automation-first scope, record evidence and review, and prepare the exact non-secret OpenTofu plan/apply inputs for user review.

## Acceptance criteria

- Every criterion in `.10x/specs/polaris-catalog-continuity.md` and `.10x/specs/iceberg-object-recovery.md` is mapped to code, tests, documentation, or an explicitly blocked live-proof criterion.
- OpenTofu formatting/validation and policy-focused tests pass.
- Compose rendering and all focused backup/restore tests pass without credentials or network side effects.
- Full `task ci`, strict docs, secret scan, generated-file checks, and diff checks pass.
- Review challenges destructive permissions, delete propagation, retention mismatch, credential expiry, secret leakage, restore-to-active-volume paths, accidental bootstrap, stale/missing WAL, catalog/object inconsistency, and unproven RPO/RTO wording.
- Documentation presents one coherent backup, inspection, restore-drill, object-recovery, and escalation path.
- No live AWS mutation, provider refresh, backup upload, or production restore occurs.
- The live rollout ticket contains exact remaining plan review, apply, first-backup, and timed-drill obligations.

## Explicit exclusions

- Live apply or external-state repair.
- Accepting residual findings without durable user authorization.
- Weakening retention or restore safety to pass tests.

## References

- `.10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/specs/iceberg-object-recovery.md`

## Evidence expectations

Create focused evidence and an adversarial review with changed files, exact commands/results, acceptance mapping, plan limitations, residual risks, and confirmation that live claims remain unproven.

## Progress and notes

- 2026-09-04: Opened as the automation-first aggregate gate.

## Blockers

Depends on completion of the three implementation children.
