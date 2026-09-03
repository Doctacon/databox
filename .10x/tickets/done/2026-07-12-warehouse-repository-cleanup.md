Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: None
Depends-On: None

# Warehouse repository cleanup

## Plan outcome

Make Databox intuitive for data engineers by simplifying the public repository
surface and warehouse core without changing functionality.

This is a parent plan, not an executable ticket.

## Governing context

- `.10x/knowledge/warehouse-first-cleanup.md`
- `https://github.com/Doctacon/rufous/blob/main/.10x/knowledge/public-readme-details-on-demand.md`
- `.10x/decisions/python-source-registry-as-canonical-contract.md`
- `.10x/specs/canonical-dlt-source-registry.md`
- `.10x/specs/registry-derived-source-verification.md`
- `.10x/specs/registry-source-modeling-completeness.md`

## Child sequence

1. `.10x/tickets/done/2026-07-12-audit-warehouse-repository-simplicity.md`
   - Established the newcomer path, proven cleanup candidates, rejected
     speculative removals, and preservation gates.
2. Independent cleanup slices:
   - `.10x/tickets/done/2026-07-12-remove-repository-runtime-noise.md`
   - `.10x/tickets/done/2026-07-12-simplify-public-warehouse-onboarding.md`
   - `.10x/tickets/done/2026-07-12-break-source-package-dependency-cycle.md`
   - `.10x/tickets/done/2026-07-12-delete-superseded-smoke-runner.md`
3. `.10x/tickets/done/2026-07-12-investigate-analytics-asset-check-inventory.md`
   - Establish exact runtime/check coverage before any correctness-sensitive
     inventory repair is shaped.
4. `.10x/tickets/done/2026-07-12-derive-soda-checks-from-sqlmesh-assets.md`
   - Replace manual 14-model check authority with exact 18-model SQLMesh/contract-derived coverage.
5. `.10x/tickets/done/2026-07-12-reconcile-bird-alert-delivery-action-contract.md`
   - Stabilize the unchanged state-dependent delivery API test exposed by aggregate verification without changing delivery semantics.
6. `.10x/tickets/done/2026-07-12-verify-warehouse-repository-cleanup.md`
   - Aggregate behavior-preservation verification and independent review.

## Aggregate acceptance criteria

- A data engineer can identify the repository purpose, install/run path,
  ingestion contract, modeling workflow, warehouse location, and extension path
  without navigating Rufous internals.
- Public docs and commands have one clear owner for each concept; duplicate or
  contradictory guidance is removed.
- Proven dead/duplicate warehouse paths are deleted or consolidated without
  changing source, model, quality, orchestration, or warehouse behavior.
- Repository/package boundaries and names reflect the canonical dlt → DuckDB →
  taxonomy/ontology/CDM → SQLMesh workflow.
- Existing functionality and safety controls remain intact and verified.
- Every implementation slice has evidence and passing independent review.

## Explicit exclusions

- Product behavior changes
- Rufous feature or large-module refactors
- Source/provider, schema, cadence, or data-semantic changes
- New abstraction layers, dependencies, or speculative architecture
- Full refresh, provider capture, SQLMesh apply, or shared warehouse mutation

## Progress and notes

- 2026-07-12: User selected data engineers as the primary audience, warehouse +
  public surface as the first wave, and proven duplication/dead paths as the
  maximum refactoring depth.
- 2026-07-12: Read-only audit completed at `.10x/research/2026-07-12-warehouse-repository-simplicity-audit.md`. Opened four independent high-confidence cleanup slices, one correctness-sensitive inventory investigation, and the final verification gate.
- 2026-07-12: Runtime hygiene, public onboarding, package dependency direction, and obsolete smoke-runner deletion passed review and closed. Inventory investigation proved 18 SQLMesh assets/contracts but only 14 checks; bounded repair derived all 18 checks from SQLMesh specs/contracts, passed review, and closed. Aggregate verification activated.
- 2026-07-12: Aggregate verification exposed one unchanged wall-clock-sensitive Rufous delivery test. Record-backed test-only time stabilization passed correctness/privacy review without runtime changes.
- 2026-07-12: Final aggregate verification and independent navigation/architecture/correctness reviews passed. Parent closure review: `.10x/reviews/2026-07-12-warehouse-repository-cleanup-parent-review.md`.
- 2026-07-12 retrospective: The cleanup reduced authority count rather than rearranging code: runtime caches are untracked, public guidance has clear owners, package metadata follows imports, refresh has one runner, and modeled checks derive from SQLMesh plus contracts. Compatibility and lifecycle lessons are executable in tests. No further first-wave cleanup is left unowned.

## Blockers

None.
