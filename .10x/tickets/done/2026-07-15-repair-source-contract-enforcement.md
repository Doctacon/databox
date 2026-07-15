Status: done
Created: 2026-07-15
Updated: 2026-07-15
Parent: .10x/tickets/done/2026-07-12-unify-dlt-source-contract-and-ci.md
Depends-On: .10x/tickets/done/2026-07-12-consolidate-canonical-dlt-source-registry.md, .10x/tickets/done/2026-07-12-complete-source-contract-test-suites.md, .10x/tickets/done/2026-07-12-derive-source-ci-from-registry.md

# Repair source contract enforcement

## Scope

Resolve the exact final architecture/correctness review findings against `.10x/specs/canonical-dlt-source-registry.md` and `.10x/specs/registry-derived-source-verification.md`:

1. Make the executable source contract checker reject invalid/non-snake-case names, duplicate names, multiple analytics anchors, missing/non-callable/multiple builders, missing required domain exports, scheduling export conflicts, empty/incomplete declared resource inventory where mechanically knowable, invalid profiles, and missing profile artifacts.
2. Ensure registry-derived matrix validation consumes those invariants rather than accepting a contract the standalone checker rejects.
3. Add canonical builder behavior coverage for all seven source domains, including USGS Earthquakes and mature eBird/NOAA/USGS paths, without provider calls.
4. Add a parity invariant between parallel-refresh registry raw tables and Quack `_RAW_DEDUPE_KEYS` membership while preserving Quack-specific key ownership.
5. Reconcile scaffold behavior/docs: generated file sources must clearly require the file-snapshot manifest/tests; skipped scaffolds must fail completed contract/matrix verification, and docs must not claim otherwise.

## Acceptance criteria

- Every MUST-level checker invariant in the canonical registry spec has an executable failing test.
- A future invalid registry/domain/profile contract cannot produce a CI matrix.
- All current domain builders are callable, singular, construct the expected resource set, and have production defaults/arguments protected without network access.
- Quack dedupe membership exactly matches all `parallel_refresh=True` registry raw tables; primary-key definitions remain Quack-owned.
- Scaffold generator/tests/docs agree that in-flight skip markers are visible locally but rejected by completed contract/matrix validation until profile obligations are satisfied.
- Focused checker, scaffold, registry, builder, Quack, matrix, Dagster-definition, Ruff, format, MyPy, docs, and diff checks pass.
- No provider request, source refresh, SQLMesh apply, warehouse access/write, or runtime side effect occurs.

## Explicit exclusions

- Changing provider queries, source semantics, raw schemas, schedules, or Quack dedupe keys
- Implementing a new database verification profile
- Privacy fixture repair owned by the sibling ticket
- Hosted GitHub Actions execution

## Evidence expectations

Record each prior finding-to-test mapping, commands/results, current inventory parity, and no-runtime limits.

## Progress and notes

- 2026-07-15: Opened from failed final aggregate architecture/correctness reviews. Current-state tests cover some invariants, but the executable checker/matrix contract is weaker than the active MUST-level specification.
- 2026-07-15: First repair pass implemented registry/domain/profile checks, seven-builder tests, USGS Earthquakes canonical profile construction, Quack membership parity, and scaffold coherence; 107 focused tests passed. Independent review failed closure on three checker false negatives: empty dlt resource declarations, two arbitrary builder calls/non-callable rebinding, and required Dagster exports assigned `None`.
- 2026-07-15: Second repair rejected empty resource declarations, rebinding, misplaced top-level builder calls, and direct `None` artifact substitutions; 113 focused tests passed. Re-review still failed two adversarial forms: a dead nested execution-time builder call, and mixed/presence-only invalid Dagster collection exports (`assets=[expected,None]`, `asset_checks=None`, `dlt_asset_keys=None`). Repair remains open.
- 2026-07-15: Implemented executable registry/domain/profile/resource/builder/schedule/scaffold invariants and made registry-derived matrix validation consume the complete checker result.
- 2026-07-15: Added offline canonical builder/default/resource coverage for all seven domains, routed all USGS Earthquakes profile tests through its builder, and added exact 14-relation registry/Quack dedupe-membership parity without changing keys.
- 2026-07-15: Reconciled REST/file scaffold templates, generator output, tests, and active docs so skip markers remain visible but fail completed validation; file snapshots explicitly require a pinned manifest and staged-publication coverage.
- 2026-07-15: Focused validation passed 107 tests with network blocked, 7/7 checker/matrix, Dagster definitions, Ruff, formatting, MyPy, docs drift/strict build, Quack parity, diff check, and empty staging. Evidence: `.10x/evidence/2026-07-15-source-contract-enforcement-repair.md`.
- 2026-07-15: Ticket remains active for parent-owned independent review and closure.
- 2026-07-15: Repaired all three independent-review false negatives narrowly: empty resource sets now mismatch non-empty registry inventory; `_build_source` must be one unshadowed synchronous function called exactly once by the dlt decorator and once in the dlt asset body; Dagster exports now require executable AST shapes rather than names. Added empty-resource, misplaced two-call, rebinding, and five `None`/non-callable export adversarial cases.
- 2026-07-15: Post-review validation passed 113 focused offline/network-blocked tests, 39 final checker/matrix tests, 7/7 real repository contracts, deterministic seven-source matrix, Ruff/format/MyPy, docs drift/strict build, diff check, and empty staging. Updated evidence: `.10x/evidence/2026-07-15-source-contract-enforcement-repair.md`.
- 2026-07-15: Repaired both second re-review false-negative classes narrowly. Execution-time builder detection now traverses executable statements but skips nested function/class/lambda definitions; collection validation now requires exactly `[<name>_dlt_assets]`, list-shaped `asset_checks`/`sqlmesh_asset_keys`, and a `<name>_dlt_assets.specs`-derived `dlt_asset_keys` comprehension. Added dead nested-call, mixed-assets, and `None` collection adversarial cases.
- 2026-07-15: Final bounded validation passed 118 focused offline/network-blocked tests, 44 final checker/matrix tests, 7/7 real contracts, deterministic matrix, Ruff/format/MyPy, docs drift/strict build, diff check, and empty staging. Source-factory membership remains bounded to the existing all-seven resource-construction test rather than speculative interprocedural AST analysis. Evidence updated at `.10x/evidence/2026-07-15-source-contract-enforcement-repair.md`.
- 2026-07-15: Independent final review `.10x/reviews/2026-07-15-source-contract-enforcement-repair-review.md` passed every acceptance criterion. Ticket closed.
- 2026-07-15 retrospective: The durable lesson is encoded directly in the checker, adversarial tests, and scaffold docs: validate canonical executable shapes rather than mere names/substrings. No separate skill or knowledge record is warranted.
- 2026-07-15: Reopened after fresh parent architecture review found one omitted active-spec MUST: the executable checker does not reject reintroduced legacy generic authority files/imports. Fresh correctness review also found `new_source.py` accepts malformed underscore names rejected by the canonical checker. Both are within this ticket's all-MUST/scaffold-coherence scope.
- 2026-07-15: First reopened repair centralized the name regex and rejected exact retired paths plus full-module/direct-relative imports; 137 focused tests passed. Re-review found one remaining standard import syntax bypass: `from <parent package> import <retired child>` aliases are discarded, so checker/matrix fail open. Ticket remains active for exact repair.
- 2026-07-15: Implemented exact legacy-authority path/template rejection for eight retired artifacts plus absolute/package-relative import rejection for the four retired modules across active code roots. Explicit regression coverage proves the live `orchestration/_factories.py` dlt translator remains valid and matrix generation fails closed for legacy files/imports.
- 2026-07-15: Moved the lowercase snake-case regex to canonical `databox.config.sources.SOURCE_NAME_PATTERN`; checker and scaffold now share it. Scaffold validation rejects repeated, trailing, and leading underscores.
- 2026-07-15: Final reopened-ticket validation passed 137 focused offline/network-blocked tests, then 74 checker/matrix/scaffold tests after formatting; live checker/matrix remained 7/7; Dagster definitions, workspace Ruff/177-file formatting, focused MyPy, staging/platform-health/docs codegen, strict MkDocs, diff check, empty staging, and protected hashes passed.
- 2026-07-15: Follow-up re-review exposed the remaining `from <parent> import <retired child>` syntax bypass. `_imported_modules` now records both parent and non-wildcard parent-child candidates for absolute and relative imports. Four checker and four matrix adversarial cases cover every retired child; legitimate parent imports and live `_factories` remain allowed. Final post-format focused run passed 82 tests recording-disabled/network-blocked; live checker/matrix, targeted Ruff/format, MyPy, diff, and empty staging passed. Evidence updated at `.10x/evidence/2026-07-15-source-contract-enforcement-repair.md`.
- 2026-07-15: Independent final review `.10x/reviews/2026-07-15-source-contract-enforcement-final-review.md` passed after 20/20 retired import combinations and 8/8 retired paths failed checker/matrix, six legitimate imports passed, and 145 focused tests/static/integrity checks passed. Ticket re-closed.
- 2026-07-15 retrospective addendum: Exact file deletion is insufficient protection when active imports can recreate authority under standard syntax. Bounded import-shape regression cases are now executable contract tests; no separate knowledge/skill record is needed.

## Blockers

None.

## References

- `.10x/specs/canonical-dlt-source-registry.md`
- `.10x/specs/registry-derived-source-verification.md`
- `.10x/evidence/2026-07-15-unified-source-contract-aggregate-verification.md`
- `.10x/reviews/2026-07-15-unified-source-contract-architecture-review.md`
- `.10x/reviews/2026-07-15-unified-source-contract-correctness-review.md`
