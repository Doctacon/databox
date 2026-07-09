Status: recorded
Created: 2026-07-08
Updated: 2026-07-08
Relates-To: .10x/tickets/done/2026-07-08-model-birding-planner-sql-interfaces.md

# Evidence: Birding planner SQL interfaces

## What was observed

Implemented planner-ready SQLMesh view interfaces for Birding Trip Copilot source evidence and stable physical persistence-table interfaces for generated trip plans, recommendations, evidence, and tool traces.

## Models and persistence interfaces added

SQLMesh models added under `transforms/main/models/birding_agent/planner/`:

- `birding_agent.species_lookup`
- `birding_agent.recent_observation_evidence`
- `birding_agent.gbif_occurrence_evidence`
- `birding_agent.xeno_canto_media_evidence`

Soda contracts added under `soda/contracts/birding_agent/` for the four SQLMesh planner views.

Physical persistence interfaces are created by `databox.agent_tools.persistence.ensure_birding_agent_persistence_tables(...)`:

- `birding_agent.trip_plans`
- `birding_agent.trip_plan_recommendations`
- `birding_agent.trip_plan_evidence`
- `birding_agent.trip_plan_tool_traces`

`persist_open_meteo_evidence(...)` now calls the persistence-interface helper before writing Open-Meteo evidence and writes into the widened `trip_plan_evidence` table while preserving the existing Open-Meteo test contract.

## Procedure and results

### SQLMesh model tests

```bash
cd transforms/main && ../../.venv/bin/sqlmesh test
```

Result:

```text
Successfully Ran `6` Tests Against `duckdb`
```

The test suite now includes focused tests for:

- `birding_agent.species_lookup`
- `birding_agent.recent_observation_evidence`
- `birding_agent.gbif_occurrence_evidence`
- `birding_agent.xeno_canto_media_evidence`

### SQLMesh plan explanation

```bash
cd transforms/main && ../../.venv/bin/sqlmesh plan dev --skip-backfill --no-prompts --explain \
  --select-model birding_agent.species_lookup \
  --select-model birding_agent.recent_observation_evidence \
  --select-model birding_agent.gbif_occurrence_evidence \
  --select-model birding_agent.xeno_canto_media_evidence
```

Result: plan explanation succeeded and listed the four added `birding_agent__dev` models with no backfill batches.

### SQLMesh render/info

```bash
cd transforms/main && ../../.venv/bin/sqlmesh render birding_agent.species_lookup
cd transforms/main && ../../.venv/bin/sqlmesh render birding_agent.recent_observation_evidence
cd transforms/main && ../../.venv/bin/sqlmesh render birding_agent.gbif_occurrence_evidence
cd transforms/main && ../../.venv/bin/sqlmesh render birding_agent.xeno_canto_media_evidence
cd transforms/main && ../../.venv/bin/sqlmesh info
```

Result: all four models rendered; `sqlmesh info` reported 14 models and successful warehouse/state connections.

### Open-Meteo persistence helper tests

```bash
.venv/bin/python -m pytest --no-cov tests/test_open_meteo_tool.py -q
```

Result:

```text
5 passed
```

The persistence helper test confirmed creation of all four physical `birding_agent` trip-plan tables and preservation of Open-Meteo evidence writes.

### Dagster definitions

```bash
.venv/bin/dg check defs --use-active-venv
```

Result:

```text
All definitions loaded successfully.
```

### Formatting, linting, typing

```bash
.venv/bin/ruff check packages/databox/databox/agent_tools packages/databox/databox/orchestration/domains/analytics.py scripts/generate_docs.py tests/test_open_meteo_tool.py
.venv/bin/ruff format --check packages/databox/databox/agent_tools packages/databox/databox/orchestration/domains/analytics.py scripts/generate_docs.py tests/test_open_meteo_tool.py
.venv/bin/mypy packages/databox/databox/agent_tools packages/databox/databox/orchestration/domains/analytics.py tests/test_open_meteo_tool.py
```

Result:

```text
All checks passed!
6 files already formatted
Success: no issues found in 5 source files
```

### Documentation generation

```bash
.venv/bin/python scripts/generate_docs.py
.venv/bin/python scripts/generate_docs.py --check
```

Result:

```text
Generated 14 model pages + lineage + index under docs/dictionary/
docs/dictionary/ is in sync (16 files).
```

### Staging check

```bash
git diff --cached --quiet; echo no_staged=$?
```

Result:

```text
no_staged=0
```

## What this supports

- SQLMesh now exposes planner-ready interfaces for species/taxonomy lookup, recent eBird observations, GBIF occurrence evidence, and Xeno-canto media evidence.
- The Open-Meteo tool can persist weather/elevation context into the same stable evidence table family that the future ADK planner and MotherDuck Dive can query.
- The implementation stayed within modeling/persistence-interface scope; no ADK agent, DeepEval suite, or Dive was implemented.

## Limits

- `scripts/verify_dev.py` was not run because the dev environment was not applied in this ticket and the local warehouse does not currently contain live `raw_xeno_canto` tables without a Xeno-canto API key. Contract YAML was parsed by docs generation, and SQLMesh behavior was validated with fixture-based tests.
- Live Xeno-canto-backed materialization still depends on the prior source ticket and a valid `XENO_CANTO_API_KEY`.
