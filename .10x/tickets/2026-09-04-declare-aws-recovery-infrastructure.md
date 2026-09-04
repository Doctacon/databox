Status: open
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: None

# Declare AWS recovery infrastructure with OpenTofu

## Scope

Add the smallest maintainable OpenTofu module/root needed to describe the dedicated Polaris catalog-backup bucket, Iceberg recovery bucket, primary-to-recovery copy/replication, version/retention behavior, encryption, public-access blocking, and least-privilege IAM boundaries in the existing AWS account and `us-west-1`.

Expose non-secret outputs and inputs consumed by local pgBackRest and recovery tooling. Add formatting, validation, policy-focused static tests, and operator plan instructions. Generate a non-applying plan only when authenticated read-only planning can do so without external mutation.

## Acceptance criteria

- OpenTofu is pinned or bounded through documented installation/version requirements and uses only open-source tooling.
- Bucket names, primary warehouse bucket/prefix, AWS account context, and credential-process profile/command are explicit inputs rather than committed personal identifiers.
- The catalog-backup bucket and Iceberg recovery bucket are distinct from each other and the primary warehouse.
- Both buckets enable versioning, encryption, public-access blocking, and ratified retention behavior.
- Iceberg recovery covers the configured warehouse prefix and preserves recoverable object versions for at least 45 days.
- Routine Iceberg writer permissions cannot delete backup objects or mutate retention controls.
- Catalog backup and Iceberg recovery permissions are separately scoped.
- Delete-marker/version behavior is explicit and structurally tested; primary deletion cannot immediately remove the only recovery copy.
- Configuration is same-account and `us-west-1`; docs state the accepted regional/account-wide residual risk.
- `tofu fmt -check`, `tofu validate`, policy/static tests, secret scan, and diff checks pass.
- No `tofu apply`, bucket creation, policy mutation, replication, or external write occurs.

## Explicit exclusions

- Live AWS apply or import.
- Cross-account/cross-region design.
- Long-lived AWS keys.
- PostgreSQL runtime or restore implementation.
- Iceberg maintenance operations.

## References

- `.10x/decisions/polaris-iceberg-backup-and-recovery.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/specs/iceberg-object-recovery.md`
- `.10x/research/2026-09-04-polaris-iceberg-disaster-recovery.md`

## Evidence expectations

Record changed files, exact OpenTofu/static-test commands, rendered resource/policy assertions, secret-scan result, plan limitations, and confirmation that no live apply or AWS write ran.

## Progress and notes

- 2026-09-04: Opened from the ratified disaster-recovery architecture.

## Blockers

None. Resource names may remain validated inputs; no live account identifiers are required for the automation slice.
