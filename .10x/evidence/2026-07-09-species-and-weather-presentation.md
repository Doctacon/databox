Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-improve-species-and-weather-presentation.md, .10x/specs/trip-plan-result-presentation.md

# Species and weather presentation evidence

## What was observed

The production `birding_agent.gbif_occurrence_evidence` SQLMesh view now derives a lowercase authority-free binomial key from GBIF accepted/species/scientific names and joins it to one guarded row per `environmental_observations.dim_species` natural key. The guard ranks eBird rows first, then loaded time and stable species key, so even a duplicate dimension input cannot multiply GBIF evidence.

The planner receives the conformed species code, common name, and authority-free scientific name while retaining raw GBIF scientific and accepted scientific names plus source table/record provenance. Recommendation ranking was not changed.

The React result view reloads persisted Open-Meteo `forecast_summary` and elevation values from the API evidence payload. Pure deterministic application code maps bounded WMO codes and displays low/high temperature, humidity, precipitation chance/total, sustained wind, gusts, and elevation. Temperature, wind, precipitation, and elevation render in both US customary and metric units. Missing partial fields are labeled individually, while available elevation and weather caveats remain visible. Source status is secondary.

## Production warehouse observation

After the selected view-only SQLMesh production plan was applied, a read-only query against the single `data/databox.duckdb` warehouse returned:

```text
Aegolius acadicus (J.F.Gmelin, 1788) -> Northern Saw-whet Owl / Aegolius acadicus / nswowl
Melanerpes uropygialis (S.F.Baird, 1854) -> Gila Woodpecker / Melanerpes uropygialis / gilwoo
Sialia mexicana Swainson, 1832 -> Western Bluebird / Sialia mexicana / wesblu
raw_gbif.occurrences rows: 1000
birding_agent.gbif_occurrence_evidence rows: 1000
duplicate occurrence_evidence_id groups: 0
```

This directly supports authority removal, eBird-first common-name recovery, row-count preservation, and duplicate protection on the current local data.

## Deterministic validation

### SQLMesh

```text
cd transforms/main && ../../.venv/bin/sqlmesh test
```

Result: 11 SQLMesh tests passed. The new fixture covers all three named species, unparenthesized and parenthesized authorities, eBird-first selection over a newer duplicate GBIF dimension row, and guarded partial-column comparison.

```text
cd transforms/main && ../../.venv/bin/sqlmesh plan prod --skip-backfill --no-prompts --explain --select-model birding_agent.gbif_occurrence_evidence
cd transforms/main && ../../.venv/bin/sqlmesh plan prod --skip-backfill --no-prompts --auto-apply --select-model birding_agent.gbif_occurrence_evidence
cd transforms/main && ../../.venv/bin/sqlmesh diff prod
```

Result: the explanation identified only `birding_agent.gbif_occurrence_evidence`; the view-only production plan applied without model batches; the final diff reported that project files match `prod`.

### Python/API

```text
uv run --no-sync ruff check packages/databox/databox/agents/birding_trip_planner.py packages/databox/databox/api.py tests/test_birding_trip_planner.py tests/test_api.py
uv run --no-sync ruff format --check packages/databox/databox/agents/birding_trip_planner.py packages/databox/databox/api.py tests/test_birding_trip_planner.py tests/test_api.py
uv run --no-sync mypy packages/databox/databox/agents/birding_trip_planner.py packages/databox/databox/api.py
uv run --no-sync pytest --no-cov -q tests/test_birding_trip_planner.py tests/test_api.py tests/test_open_meteo_tool.py
```

Result: Ruff, format, and MyPy passed; 29 focused tests passed. Tests prove the three conformed names/codes collapse to three recommendations despite duplicate GBIF evidence, and the stable API reloads the full persisted forecast summary/elevation.

### React

```text
cd app && npm run typecheck && npm test && npm run build
task app:audit-bundle
```

Result: strict TypeScript passed; 14 Vitest tests passed across two files; Vite built 30 modules; bundle audit found all three configured Cloudflare names and all three configured values absent. Tests cover common-name-primary/scientific-secondary display, scientific-only fallback, all dual-unit conversions, bounded WMO labels, complete weather, partial weather, caveats, and secondary status.

After the final pre-commit pass, the short validation was repeated: strict TypeScript and all 14 Vitest tests passed, and all 11 SQLMesh tests passed.

### Aggregate

```text
task ci
task docs:build
.venv/bin/pre-commit run --all-files
```

Results: repository CI passed Ruff, formatting, MyPy for 72 source files, all 210 tests at 82.48% coverage, secret scan, staging drift, and platform-health drift. Strict MkDocs generated 16 model pages plus lineage/index and built successfully. The final sequential pre-commit run passed every hook. A final documentation regeneration/build repeated successfully after the pre-commit pass.

## What this supports

- Current GBIF uncommon evidence exposes Western Bluebird, Gila Woodpecker, and Northern Saw-whet Owl common names without dropping source provenance or multiplying rows.
- Recommendation cards make common names primary and scientific names secondary when available.
- Weather values are deterministic renderings of persisted DuckDB evidence, not browser refetches or model-generated facts.
- Both-unit output and partial-source behavior match the active specification.

## Independent-review repair

Independent review found that the SQLMesh view exposed `source_scientific_name`, but the bounded planner lookup omitted it. Because persistence serializes only the lookup row, API-visible evidence lost the original GBIF name whenever it differed from the accepted/conformed name.

The repair adds `source_scientific_name` to `lookup_gbif_occurrence_evidence` and adds both `source_scientific_name` and `accepted_scientific_name` to the occurrence summary; the full bounded lookup row continues to be stored in the payload. Recommendation display still uses conformed `scientific_name`.

A new HTTP integration regression starts with a planner-view row representing these distinct source values:

```text
source_scientific_name: Sialia occidentalis Townsend, 1837
accepted_scientific_name: Sialia mexicana Swainson, 1832
scientific_name: Sialia mexicana
common_name: Western Bluebird
```

It creates a plan through `POST /api/trip-plans`, verifies the recommendation uses `Western Bluebird` / `Sialia mexicana`, verifies persisted response summary and payload retain all three scientific-name forms, reloads the plan through `GET /api/trip-plans/{id}`, and verifies both JSON objects survive unchanged. The SQLMesh fixture was also strengthened so an authority-qualified raw `scientific_name` differs from `accepted_scientific_name`, proving the raw-to-view handoff independently of the integration fixture.

Repair validation:

```text
cd transforms/main && ../../.venv/bin/sqlmesh test
uv run --no-sync ruff check packages/databox/databox/agents/birding_trip_planner.py tests/test_birding_trip_planner.py tests/test_api.py tests/evals/test_birding_trip_copilot_deepeval.py
uv run --no-sync ruff format --check packages/databox/databox/agents/birding_trip_planner.py tests/test_birding_trip_planner.py tests/test_api.py tests/evals/test_birding_trip_copilot_deepeval.py
uv run --no-sync mypy packages/databox/databox/agents/birding_trip_planner.py
uv run --no-sync pytest --no-cov -q tests/test_birding_trip_planner.py tests/test_api.py
uv run --no-sync pytest --no-cov -q tests/evals/test_birding_trip_copilot_deepeval.py
```

Results: all 11 SQLMesh tests passed; Ruff, format, and MyPy passed; all 25 planner/API tests passed; both deterministic DeepEval tests passed. No live model call ran.

## Limits

- Authority-free matching intentionally targets binomial species names; hybrid/subgenus/global taxonomy expansion remains excluded.
- WMO presentation is a bounded deterministic label set and does not generate narrative forecast prose.
- No live model call was run.
