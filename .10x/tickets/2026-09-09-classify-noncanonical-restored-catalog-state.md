Status: blocked
Created: 2026-09-09
Updated: 2026-09-09
Parent: .10x/tickets/2026-09-04-build-isolated-catalog-recovery-drill.md
Depends-On: None

# Classify noncanonical restored-catalog state

## Scope

Define whether tables in namespaces outside the seven canonical registry sources, including restored `raw_usfws` and `dlt_polaris_probe`, remain recovery-validation failures or become explicitly reported warnings. Preserve visibility and fail closed until the policy is approved. Do not silently allowlist identifiers.

## Acceptance criteria

- An approved policy defines warning versus failure behavior for noncanonical namespaces.
- Every noncanonical namespace and table remains explicit in validation output.
- Unexpected tables inside canonical namespaces remain failures.
- No catalog deletion, mutation, or cleanup is implied or performed.

## Progress and notes

- 2026-09-09: Split from `.10x/tickets/done/2026-09-09-reconcile-restored-catalog-registry-drift.md` when the user authorized only the three eBird generated child-table declarations.

## Blockers

User decision on whether retained noncanonical namespaces are explicit warnings or recovery-validation failures.

## Exclusions

- Adding USFWS to the canonical seven-source registry.
- Catalog/table deletion or cleanup.
- Source refresh, warehouse writes, cutover, or RPO/RTO claims.
