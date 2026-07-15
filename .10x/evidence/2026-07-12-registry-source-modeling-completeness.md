Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-enforce-registry-source-modeling-completeness.md, .10x/specs/registry-source-modeling-completeness.md

# Registry source modeling completeness guard

## What was observed

The repository had complete annotate/taxonomy/ontology/CDM/SQLMesh artifacts for all seven registered dlt sources, but no single executable guard linked those stages. The new guard derives source identities and raw-table inventories only from `databox.config.sources.SOURCES`.

Current derived coverage:

- seven registered sources;
- 15 registered raw tables;
- 14 modeled and transformed business tables;
- one reasoned taxonomy exclusion: `raw_noaa.datasets` source metadata;
- exactly one annotated DBML owner per source;
- every modeled concept present in `ontology.ison` and as a `source_entity` in `CDM.dbml`;
- every modeled table consumed by a real SQLMesh `FROM` or `JOIN` dependency.

Per-source modeled table counts are eBird 6, GBIF 1, AVONET 1, Xeno-canto 1, NOAA 2 plus one exclusion, USGS 2, and USGS Earthquakes 1. No semantic modeling artifact changed.

## Implementation

`scripts/check_source_modeling.py` statically:

1. discovers source DBML files under `.schema/*/` and matches each registry inventory to exactly one owner;
2. parses exact DBML note fields and requires the `concept:` plus `also_concept:` set to equal taxonomy mappings, while requiring `excluded:` if and only if taxonomy excludes the table;
3. reads the owning pipeline's taxonomy and requires every table to be modeled or reasoned-excluded, never both;
4. checks each modeled concept against ontology entities and CDM `source_entity` notes;
5. parses SQL with `sqlmesh.core.dialect.parse`, traverses `sqlglot.exp.Table` nodes only beneath structural `exp.From` or `exp.Join` clauses, and counts a raw dependency only when its SQLMesh MODEL output is declared in `CDM.dbml` and that output's `source_entity` intersects the raw table's taxonomy concepts;
6. rejects operational-only dependencies such as `analytics.platform_health` and any source with no modeled/transformed business table.

`tests/test_source_modeling_contract.py` is the CI guard and contains temporary-artifact adversarial coverage for complete and reasoned-exclusion cases plus missing/ambiguous DBML ownership, exact concept-set mismatches, `unconcept:` substring impostors, both DBML/taxonomy exclusion-disagreement directions, missing taxonomy, modeled/excluded conflicts, missing exclusion reasons, missing ontology, missing CDM, genuine quoted/commented FROM and JOIN dependencies, commented/string-only false dependencies, raw INSERT/UPDATE/DELETE targets, operational-only models, non-intersecting CDM entities, fully excluded sources, and missing stage files.

`.github/workflows/ci.yaml` now classifies `.schema/**` and all `transforms/main/models/**` changes as cross-cutting so pull requests changing governed modeling artifacts run the core/full test jobs. `tests/test_source_ci.py` protects that routing. `docs/source-layout.md` names the executable guard and its policy.

## Procedure and results

- Initial `.venv/bin/pytest --no-cov -q tests/test_source_modeling_contract.py tests/test_source_ci.py` — **45 passed** before independent review.
- First post-review focused run of the same command — **54 passed**, including 25 modeling-contract tests and 29 CI tests.
- Final write-target re-review repair run — **58 passed**, including 29 modeling-contract tests and 29 CI tests.
- `.venv/bin/python scripts/check_source_modeling.py` — **7 registered sources complete the modeling workflow**.
- Derived inventory script — **7 sources, 15 registered tables, 14 modeled/transformed, one reasoned exclusion**.
- `.venv/bin/ruff check scripts/check_source_modeling.py tests/test_source_modeling_contract.py tests/test_source_ci.py` — passed.
- `.venv/bin/ruff format --check ...` — passed; three files already formatted.
- `MYPYPATH=packages/databox:packages/databox-sources .venv/bin/mypy --explicit-package-bases scripts/check_source_modeling.py tests/test_source_modeling_contract.py` — no issues.
- `git diff --check` — passed.
- Workflow parse — `.schema/**` and `transforms/main/models/**` are both in `cross_cutting`, so each triggers full CI.
- Final AST/CDM-qualified inventory report — eBird 6/0, GBIF 1/0, AVONET 1/0, Xeno-canto 1/0, NOAA 2/1, USGS 2/0, USGS Earthquakes 1/0 semantic/excluded; total **7 sources, 15 tables, 14 semantically transformed, one excluded**.
- `git diff --cached --name-only` — empty.

## What this supports

This supports every acceptance criterion in `.10x/tickets/done/2026-07-12-enforce-registry-source-modeling-completeness.md`: registry-derived discovery, complete stage enforcement, documented exclusions, actionable adversarial failures, current seven-source success without semantic artifact changes, CI routing, documentation, and static validation.

## Limits

The guard proves repository coherence, not that SQLMesh models successfully execute against live data. Existing SQLMesh/unit/data-quality tests retain that responsibility. SQLMesh/sqlglot AST inspection proves static MODEL declarations and parsed table dependencies. Only tables structurally beneath `exp.From` or `exp.Join` count; write targets and unrelated table nodes do not. Runtime-generated Jinja or dynamic SQL that does not expose a static dependency intentionally fails closed. No provider request, source refresh, SQLMesh command/apply, shared warehouse access, model call, email, application action, staging, or commit occurred.
