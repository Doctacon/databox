Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: None
Depends-On: None

# Enforce registry source modeling completeness

## Scope

Add one registry-derived static contract test implementing `.10x/specs/registry-source-modeling-completeness.md` across the current annotated DBML, taxonomy, ontology, CDM, and SQLMesh artifacts.

The test must discover all sources and raw tables from `packages/databox/databox/config/sources.py`; it must not contain a manually maintained list of the seven current source names.

## Acceptance criteria

- The guard proves exactly one annotated DBML owner for every registered source inventory.
- Every registered raw table is modeled or explicitly excluded with a reason, never both.
- Every modeled concept is present in the ontology and CDM.
- Every modeled raw table has a real SQLMesh `FROM` or `JOIN` dependency.
- Every source contributes at least one modeled/transformed table.
- Focused adversarial tests prove missing/ambiguous annotation ownership, missing taxonomy, modeled-plus-excluded conflict, missing ontology, missing CDM, missing transformation, and fully excluded source all fail with useful diagnostics.
- The current seven-source repository passes without changing semantic modeling artifacts.
- `docs/source-layout.md` identifies the executable guard alongside the existing skill sequence.
- Focused pytest, Ruff, format, MyPy, `git diff --check`, and empty staging checks pass.

## Explicit exclusions

- Changing source, taxonomy, ontology, CDM, or transformation semantics merely to satisfy the test
- Provider requests, source refreshes, SQLMesh apply, warehouse access/mutation, or application changes
- A manually maintained source-name mapping in the test

## Evidence expectations

Record the derived source/table inventory, per-stage coverage, exclusion handling, adversarial cases, commands/results, and static-only limits.

## Progress and notes

- 2026-07-12: Opened after inspection found all seven current sources have complete artifacts but no end-to-end executable guard. User ratified documented table exclusions, required at least one transformed table per source, and required the CDM stage.
- 2026-07-12: First implementation passed 45 focused tests and current inventory, but independent review failed closure on three false-negative classes: DBML/taxonomy disagreement, lexical SQL parsing around quoted strings/comments, and operational platform-health dependencies satisfying business transformation coverage.
- 2026-07-12: Second implementation repaired those classes and passed 54 focused tests. Re-review found one remaining AST-context false positive: a raw table used only as an `INSERT INTO` target counts as a dependency because all `exp.Table` nodes are collected. Repair remains active.
- 2026-07-12: Added `scripts/check_source_modeling.py` and `tests/test_source_modeling_contract.py`. The registry-derived guard enforces unique annotated DBML ownership, annotation/taxonomy classification, ontology/CDM concepts, real SQLMesh raw dependencies, reasoned exclusions, and at least one modeled/transformed table per source without a seven-source list.
- 2026-07-12: Added adversarial temporary-artifact coverage for every acceptance failure mode. Current inventory passes: seven sources, 15 registered tables, 14 modeled/transformed, and one reasoned NOAA metadata exclusion.
- 2026-07-12: Routed `.schema/**` and all SQLMesh model changes through full CI and documented the executable guard. Focused tests passed 45/45; CLI, Ruff, format, focused MyPy, diff, and empty staging checks passed. Evidence: `.10x/evidence/2026-07-12-registry-source-modeling-completeness.md`.
- 2026-07-12: Final validation corrected one diagnostic edge case so a missing taxonomy classification is not mislabeled as a fully excluded source. Final focused run passed 45 tests; workflow parsing, 7-source/15-table inventory, Ruff, format, focused MyPy, CLI, diff, and empty staging all passed.
- 2026-07-12: Independent review failed closure on three bounded false-negative/false-positive classes: substring DBML annotations could disagree with taxonomy, lexical SQL scanning was not AST-authoritative, and operational models could satisfy semantic transformation coverage.
- 2026-07-12: Repaired exact DBML `concept:`/`also_concept:` set equality and bidirectional `excluded:` parity; replaced lexical scanning with SQLMesh/sqlglot AST parsing; and limited dependencies to CDM-declared MODEL outputs whose `source_entity` intersects the raw table's taxonomy concepts. Added quoted/comment/string, substring-impostor, exclusion-direction, operational-only, and wrong-entity probes.
- 2026-07-12: Final post-review validation passed 54 focused tests, the current 7-source/15-table AST-qualified report, workflow routing, Ruff, format, focused MyPy, CLI, diff, and empty staging. Evidence updated at `.10x/evidence/2026-07-12-registry-source-modeling-completeness.md`.
- 2026-07-12: Second re-review found one exact remaining false positive: raw tables used only as INSERT/UPDATE/DELETE targets were counted because every AST `exp.Table` was traversed. Dependency extraction now accepts tables only beneath structural `exp.From` or `exp.Join` clauses. Added three write-target rejection cases and a genuine JOIN positive case.
- 2026-07-12: Final validation passed 58 focused tests, the unchanged 7-source/15-table semantic report, workflow routing, Ruff, format, focused MyPy, CLI, diff, and empty staging. Evidence updated at `.10x/evidence/2026-07-12-registry-source-modeling-completeness.md`.
- 2026-07-12: Independent final review `.10x/reviews/2026-07-12-registry-source-modeling-completeness-review.md` passed every criterion after independently probing write targets, genuine dependencies, cross-artifact parity, semantic model qualification, current inventory, and CI routing.
- 2026-07-12 retrospective: Static workflow guards must prove cross-artifact agreement and AST context, not merely artifact presence or matching text. This lesson is encoded in the guard and adversarial tests; no separate skill/knowledge record is required. Ticket closed.

## Blockers

None.

## References

- `.10x/specs/registry-source-modeling-completeness.md`
- `.pi/skills/annotate-sources/SKILL.md`
- `.pi/skills/create-ontology/SKILL.md`
- `.pi/skills/generate-cdm/SKILL.md`
- `.pi/skills/create-transformation/SKILL.md`
- `docs/source-layout.md`
