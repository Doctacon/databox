Status: recorded
Created: 2026-07-15
Updated: 2026-07-15
Relates-To: .10x/tickets/done/2026-07-15-repair-source-contract-enforcement.md, .10x/specs/canonical-dlt-source-registry.md, .10x/specs/registry-derived-source-verification.md

# Source contract enforcement repair evidence

## What was observed

The executable checker and registry-derived matrix now enforce the architecture/correctness review findings instead of relying on scattered current-state tests. Independent reviews of the first two repair passes identified five bounded AST false-negative classes; both follow-ups repaired and retested the exact findings.

### Registry and domain invariants

`scripts/check_source_layout.py` now rejects:

- invalid/non-snake-case and duplicate source names;
- multiple analytics anchors;
- invalid profiles;
- empty, invalid, or duplicate raw-table inventory;
- source-declared dlt resources that do not exactly match registry raw tables, including an empty detected resource set;
- missing source packages, domains, tests, file manifests, or staged-publication tests;
- missing or non-executable Dagster export shapes: the named dlt asset must be a `@dlt_assets` function, `assets` must be exactly that single function, asset/key collections must have their canonical executable list shapes, jobs must use `dg.define_asset_job`, and schedules must use `dg.ScheduleDefinition`;
- absent, async/non-callable, multiple, rebound, or shadowed `_build_source` definitions;
- builder calls outside exactly one `dlt_source=_build_source()` decorator call and exactly one direct executable call in the dlt asset function body; nested function/class/lambda bodies do not count as execution-time construction;
- source factory calls outside the canonical builder;
- smoke limits embedded in the canonical builder;
- schedule/daily exports inconsistent with the registry flag;
- unregistered source/domain implementations and incomplete skip-marked scaffolds;
- reintroduction of each exact retired generic authority file/template (`databox_sources.base`, `databox_sources.registry`, `pipeline_config.py`, the generic quality engine, database templates, or generic REST/file config templates);
- absolute full-module, absolute `from <parent> import <retired child>`, and package-relative active imports of the four retired authority modules across runtime package/script/transform roots, without rejecting legitimate parent-package imports or the live `orchestration/_factories.py` dlt translator.

`source_ci.build_matrix` consumes registry-level checker errors, including legacy-authority errors, while `validate_contract` consumes the complete checker result. An invalid future contract therefore cannot produce the CI matrix.

### Builder and Quack parity

Offline construction tests cover all seven domain builders. They verify callability, registered resource sets, and exact production arguments/defaults for AVONET, eBird, GBIF, NOAA, USGS, USGS Earthquakes, and Xeno-canto. GBIF/Xeno bounded overrides remain explicit. All four USGS Earthquakes profile tests now construct through its canonical domain builder.

A Quack regression test compares `_RAW_DEDUPE_KEYS` membership with every raw table on each `parallel_refresh=True` registry source. The current result is exactly 14 registry relations and 14 Quack-keyed relations. Primary-key tuples remain owned and unchanged in Quack.

### Scaffold contract

REST/file scaffold templates, generator output, tests, and docs now agree:

- skip markers make incomplete work visible but completed checker/CI validation fails;
- file snapshots must add a source-specific pinned `config.yaml`, all four baseline profile tests, and `test_staged_publish.py`;
- empty scaffold assets keep Dagster importable but do not make the contract valid;
- no database profile or generic YAML scaffold was restored;
- scaffold input validation imports the canonical registry's lowercase snake-case pattern, so repeated/trailing underscores cannot generate an identity the checker rejects.

## Procedure and results

### Focused behavior tests

Command:

`.venv/bin/pytest --no-cov -q tests/test_check_source_layout.py tests/test_source_ci.py tests/test_new_source.py tests/test_source_builders.py tests/test_source_registry.py tests/test_quack_destinations.py tests/test_parallel_refresh.py tests/test_avonet_orchestration.py packages/databox-sources/tests/usgs_earthquakes --record-mode=none --block-network`

Initial result: **107 passed**, one USGS Earthquakes snapshot passed. Provider network was blocked.

After the first independent review exposed three exact false negatives, the same command passed **113 tests**, including new empty-resource, misplaced-two-call, builder-rebinding, dlt-asset-shape, assets-shape, job-shape, daily-job-shape, and schedule-shape adversarial cases.

After the second re-review exposed two remaining classes, the same command passed **118 tests**. New coverage proves that a dead nested-function `_build_source()` does not satisfy execution-time construction while the direct call does, rejects mixed `assets`, rejects `None` for `asset_checks`, `dlt_asset_keys`, and `sqlmesh_asset_keys`, and rejects a specs-iterating comprehension that does not emit keys. A final checker/matrix-only replay passed **44 tests**. Provider network remained blocked throughout.

After fresh parent review reopened the ticket, the full focused command passed **137 tests** with recording disabled/network blocked. After formatting, the checker/matrix/new-source subset passed **74 tests** with recording disabled/network blocked. New adversarial coverage rejects all eight exact retired file/template paths, all four retired module imports, package-relative legacy imports, and matrix generation for both file and import reintroduction; it also proves the live `_factories.py` translator remains allowed. Scaffold tests now reject repeated/trailing/leading underscores and accept canonical alphanumeric snake-case names.

A subsequent independent re-review found that absolute `from <parent package> import <retired child>` discarded the imported alias. `_imported_modules` now records both the parent and every non-wildcard `parent.child` candidate for absolute and relative `ImportFrom` nodes. Four checker cases and four matrix cases cover `pipeline_config`, `quality.engine`, `databox_sources.base`, and `databox_sources.registry`; legitimate `databox.config.settings`, `databox_sources.ebird`, and live `_factories` parent imports remain accepted. The final post-format checker/matrix/scaffold run passed **82 tests** recording-disabled/network-blocked.

Coverage now includes executable failure cases for every named review invariant, all seven builder contracts/resource sets, exact Quack membership parity, scaffold guidance/composition, matrix rejection, registry/Dagster inventory, shared refresh behavior, and USGS Earthquakes resource/schema/smoke/idempotency replay.

### Contract, matrix, and Dagster

- `.venv/bin/python scripts/check_source_layout.py` — **7 ok, 0 incomplete, 0 failing, 0 registry errors**.
- `.venv/bin/python scripts/source_ci.py matrix --pretty` — deterministic seven-entry matrix with AVONET `file_snapshot` and six HTTP profiles.
- `.venv/bin/dg check defs --use-active-venv` — all definitions loaded successfully.
- Bounded parity script — **14 registry relations, 14 Quack keyed relations**.

### Static and docs

- Ruff check — passed for checker/matrix/scaffold/domain/focused tests.
- Ruff format check — 23 files formatted.
- `MYPYPATH=packages/databox:packages/databox-sources .venv/bin/mypy ...` — success for 23 source files.
- `.venv/bin/python scripts/generate_docs.py --check` — 20 generated docs in sync.
- `.venv/bin/mkdocs build --strict` — passed; only ignored `site/` output.
- Stale skip-guidance scan — zero matches for prior pass/tolerate/no-fail claims.
- `git diff --check` — passed.
- Shared warehouse SHA-256 remained `de4562f0ea5820f3c0a562e538ba32a2841b57709efebe059480099d80f74bb4`, matching pre-repair aggregate evidence.
- AVONET manifest SHA-256 remained `2995f2e8a37caa7ca2014bdc1acbd75d2b8a7a7067c89a380a8c910a3ad3bf97`.
- Post-review targeted Ruff check/format and workspace-root-configured MyPy — passed for the two repaired checker/test files after both repair rounds.
- Post-review docs drift and strict MkDocs build — passed after both repair rounds.
- Post-review `git diff --check` — passed after both repair rounds.
- `git diff --cached --name-only` — empty.
- Final reopened-ticket validation: workspace Ruff passed with **177 files formatted**; focused MyPy succeeded for the registry/checker/generator; staging, platform-health, and 20-file docs drift checks passed; strict MkDocs passed; `git diff --check` passed; staging remained empty.
- Parent-child import follow-up: targeted Ruff/format passed for the checker and adversarial tests, focused MyPy passed, live checker/matrix remained 7/7, `git diff --check` passed, and staging remained empty.
- Final protected hashes remained unchanged: fixture manifest `e1fc8e745e12692136e3d185b81f637ed98b1431b0cee9641ca276878f5b91de`, shared warehouse `de4562f0ea5820f3c0a562e538ba32a2841b57709efebe059480099d80f74bb4`, and AVONET manifest `2995f2e8a37caa7ca2014bdc1acbd75d2b8a7a7067c89a380a8c910a3ad3bf97`.

## What this supports

This supports every acceptance criterion in `.10x/tickets/done/2026-07-15-repair-source-contract-enforcement.md`: complete checker enforcement, matrix consumption, seven-domain builder behavior, exact Quack membership parity, coherent scaffold guidance, focused offline tests, static/docs validation, and no staged files.

## Limits

- Tests construct dlt source objects and load Dagster definitions but do not iterate provider resources except through existing recording-disabled/network-blocked USGS Earthquakes fixtures.
- No provider request, source refresh, SQLMesh command/apply, deliberate project-warehouse query/write, model call, email, or product/runtime action occurred. Existing Dagster definition loading initialized its normal adapter metadata; the project warehouse hash remained byte-identical.
- Hosted GitHub Actions evaluation remains outside local scope and still requires the first real CI run for integration evidence.
- Source-factory membership remains protected for current code by all-seven builder resource-construction tests. The checker does not attempt static interprocedural resolution of arbitrary source-factory return expressions because doing so would introduce false positives; this is a bounded residual from the second review.
- Independent acceptance re-review and ticket closure remain with the parent orchestrator.
