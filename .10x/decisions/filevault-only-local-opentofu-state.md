Status: active
Created: 2026-09-04
Updated: 2026-09-04

# Keep OpenTofu state only on the FileVault-protected host

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `afa3d97cbc97f10c59fa8a31b63b7384e0b6529d9120df53f320bf72e237aa93`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/decisions/filevault-only-local-opentofu-state.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Context

The catalog-recovery infrastructure uses local OpenTofu state at `infra/recovery/terraform.tfstate`. Earlier recovery records required a second encrypted machine backup. Live inspection showed no Time Machine destination is configured, and the operator questioned the value of adding a backup system solely for this file.

Losing this state would not delete AWS resources, interrupt pgBackRest, or lose catalog backups. It would prevent safe future OpenTofu changes until the existing resources were imported into replacement state.

## Decision

The operator accepts that recovery cost. `infra/recovery/terraform.tfstate` MUST remain local, Git-ignored, mode `0600`, and protected at rest by FileVault. No second copy or machine-backup system is required.

If the state is lost, operators MUST NOT plan or apply against empty replacement state. They MUST reconstruct state with reviewed `tofu import` commands for every live resource, then review a refresh-only plan before any infrastructure change.

This decision supersedes only the encrypted-machine-backup requirement in `.10x/decisions/superseded/catalog-backup-with-rebuildable-iceberg-warehouse.md`. All other recovery and state-handling requirements remain active.

## Alternatives considered

- **Configure encrypted Time Machine:** rejected because its operational overhead is disproportionate for a reconstructible local state file.
- **Remote OpenTofu backend:** rejected as unnecessary infrastructure and credential complexity for this personal project.
- **Commit state to Git:** rejected because state is mutable operator data and may contain sensitive metadata.

## Consequences

Disk or machine loss requires manual import before future OpenTofu use. This is slower and more error-prone than restoring a state backup, but it does not affect running AWS resources or catalog-backup availability. The accepted risk is limited to infrastructure-management recovery effort.
