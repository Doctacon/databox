Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-12-unify-dlt-source-contract-and-ci.md
Depends-On: None

# Consolidate the canonical dlt source registry

## Scope

Implement `.10x/specs/canonical-dlt-source-registry.md` without changing provider behavior or data semantics.

- Enrich the canonical `Source` contract with verification profile and deterministic domain identity.
- Refactor every source domain to use one local dlt source builder for definition-time and runtime construction.
- Derive Dagster ingestion-source composition from the registry/domain contract rather than manual source lists.
- Preserve explicit cross-domain analytics/SQLMesh composition.
- Retire the unused generic `PipelineConfig`, `PipelineSource`, source auto-registry, generic quality engine, generic YAML pipeline configs, and wrapper classes/factories after repairing consumers.
- Preserve AVONET's pinned source manifest and atomic publication invariants.
- Update source scaffolding, templates, layout/contract checks, tests, and current docs.

## Acceptance criteria

- The canonical registry contains exactly the seven current sources with valid unique names, raw tables, current flags/freshness, domain identity, and test profile.
- Every domain uses one builder; constructor literals are not duplicated within the domain.
- Dagster definitions discover all seven source domains from the registry and retain the same assets/jobs/schedules as before.
- The shared Quack eligible-source set remains unchanged: six routine sources, excluding AVONET.
- Generic legacy registry/config/quality artifacts and their active references are absent; AVONET's pinned manifest remains intact.
- New-source dry-run/scaffold and contract checker enforce the new registry/profile workflow without manual Definitions or CI source-list edits.
- Existing focused registry, settings, Dagster definition, source-layout, Quack, and scaffold tests pass.
- No provider request, source refresh, SQLMesh run, or warehouse mutation occurs.

## Evidence expectations

Record before/after source inventory, Dagster definition inventory, shared-refresh eligibility, AVONET manifest hash, removed artifact/reference scan, commands/results, and explicit limits.

## Explicit exclusions

- Building missing provider fixtures/source suites owned by the next child
- GitHub Actions matrix changes owned by the CI child
- Runtime dlt schema-contract changes
- Schedule cadence/status changes
- SQLMesh, Soda, API, frontend, or warehouse behavior changes

## Progress and notes

- 2026-07-12: Opened from the user-ratified Python-registry decision. No implementation performed in the shaping turn.
- 2026-07-12: Implemented canonical verification profiles/domain identities, one builder per source domain, registry-derived Dagster composition, legacy generic registry/config/quality retirement, and registry-only rest/file scaffolding.
- 2026-07-12: Preserved the exact existing raw-table values after the parent confirmed that inventory expansion would violate this ticket's SQLMesh/refresh exclusions. Opened `.10x/tickets/done/2026-07-12-reconcile-canonical-raw-table-inventory.md` and made aggregate verification depend on it.
- 2026-07-12: Initial focused validation passed 60 tests, but parent review found stale generic-config imports in two source tests, unsafe generated-stub composition, and missing enforcement of profile test artifacts. Closure remained open.
- 2026-07-12: Repaired all parent findings: GBIF/Xeno-canto focused tests no longer import the deleted loader; domains expose registry-composable `assets` lists so scaffold stubs contribute no fake assets; generated-stub composition is tested; and the layout checker now rejects completed profiles missing required artifacts. Focused validation passed 67 tests plus Dagster definitions, Ruff, and formatting. Layout intentionally reports 4 incomplete profiles owned by `.10x/tickets/done/2026-07-12-complete-source-contract-test-suites.md`; evidence no longer overstates 7/7 completion.
- 2026-07-12: Parent-observed post-repair validation confirmed 67 focused tests, Dagster definition loading, Ruff, formatting, diff checks, empty staging, legacy-reference cleanup, and the unchanged AVONET manifest hash.
- 2026-07-12: Fresh re-review passed. Review: `.10x/reviews/2026-07-14-canonical-dlt-source-registry-consolidation-review.md`.
- 2026-07-12: Retrospective complete. The durable architecture and scaffold/profile invariants are captured by the active decision/specifications. The only newly discovered unfinished behavior has the bounded raw-table reconciliation owner, so no additional knowledge or skill record is required.

## Blockers

None.

## References

- `.10x/decisions/python-source-registry-as-canonical-contract.md`
- `.10x/specs/canonical-dlt-source-registry.md`
- `.10x/research/2026-07-12-single-source-contract-and-ci-architecture.md`
- `.10x/specs/parallel-quack-local-refresh.md`
