Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-08-build-birding-trip-copilot.md, .10x/specs/birding-trip-copilot.md, .10x/specs/birding-agent-data-integrations.md, .10x/specs/superseded/birding-trip-plan-dive.md, .10x/specs/birding-agent-evaluations.md

# Evidence: Birding Trip Copilot aggregate validation

## What was observed

The full Birding Trip Copilot parent plan was implemented across child tickets and validated after review fixes.

Implemented slices:

- GBIF dlt/Dagster source pipeline.
- Xeno-canto metadata-only dlt/Dagster source pipeline.
- Open-Meteo request-time weather/elevation tool and evidence persistence.
- `birding_agent` SQLMesh planner evidence views and persistence interfaces.
- Python/Google ADK trip-planner runtime using a deterministic custom ADK `BaseAgent` through `InMemoryRunner`.
- DeepEval suite for deterministic agent/tool-use behavior.
- MotherDuck Dive-as-code artifact over persisted trip-plan SQL artifacts.

## Procedure and results

### Full CI

```bash
task ci
```

Result:

```text
Ruff check: passed
Ruff format --check: passed
mypy packages/: passed
pytest: 145 passed, 35 warnings
coverage: 77.99% >= 70%
check_secrets.py: passed
generate_staging.py --check: passed
generate_platform_health.py --check: passed
```

During earlier CI repair, DeepEval's unpinned `aiohttp` dependency had resolved to `aiohttp 3.14.1`, which broke `pytest-recording`/`vcrpy` setup with `AsyncStreamReaderMixin` missing. The repair pinned `aiohttp<3.14` in the dev dependency group; final CI passed with that pin.

### DeepEval suite

```bash
task eval:agent
```

Result:

```text
2 passed
DeepEval pass rate: 100.0%
token cost: None
```

Covered scenarios:

- `golden-thumb-butte-morning-trip-plan`
- `sparse-location-source-unavailable-caveats`

The suite checks expected tool sequence, persisted evidence/provenance, unavailable-source caveats, and absence of personal life-list/history assumptions.

### Documentation build

```bash
task docs:build
```

Result:

```text
Generated 14 model pages + lineage + index under docs/dictionary/
mkdocs build --strict: passed
```

MkDocs emitted its existing informational warning about MkDocs 2.0 and existing unnaved dictionary pages; build completed successfully.

### Dive build

```bash
cd .dive-preview
npm install
npm run build
```

Result:

```text
vite build: passed
1715 modules transformed
built in 939ms
```

Generated `node_modules`, `dist`, cache, and documentation build artifacts were removed afterward via cleanup.

### Review

Fresh-context review found two correctness issues:

1. The first ADK implementation exposed ADK descriptors but did not execute the main trip-planning path through ADK.
2. The Dive rendered successful persisted tool traces as failures because the planner persisted `ok` while the Dive expected `success`.

Both were fixed:

- High-level `plan_trip(...)` and CLI now run through a Google ADK `BaseAgent` wrapper via `InMemoryRunner` while preserving deterministic local execution.
- Dive trace rendering and SQL fixtures now use the real persisted `ok` status.

Follow-up review passed both prior findings.

## What this supports

- The implemented work satisfies the active Birding Trip Copilot specs at local deterministic MVP depth.
- CI, evals, docs, and Dive bundling all pass after integration fixes.
- The planner uses/persists bounded tool traces and runs through a Google ADK runtime path without requiring LLM credentials.
- The Dive visualizes persisted SQL artifacts rather than running the Python agent in browser.

### Live Xeno-canto smoke after key was added

After the user added `XENO_CANTO_API_KEY` to local `.env`, live Xeno-canto verification was run without printing or recording the key.

```bash
DATABOX_BACKEND=quack DATABOX_SMOKE=1 \
  .venv/bin/dg launch --target-path packages/databox --job xeno_canto_ingest

task verify
```

Results:

```text
xeno_canto_ingest RUN_SUCCESS
run_id=4cc58188-a7bd-4ae6-92fa-188e94cd8be7
task verify passed: .logs/verify-20260708-203153.log
raw_xeno_canto.recordings=5
birding_agent.xeno_canto_media_evidence=5
birding_agent.species_lookup=17896
raw_xeno_canto._dlt_loads BASE TABLE
raw_xeno_canto._dlt_version BASE TABLE
main._dlt* relations=0
```

The first `task verify` attempt failed after successful source ingests because `scripts/sqlmesh_plan_prod.sh` tried to restate `*` before newly added `birding_agent` models existed in the existing prod SQLMesh environment. That was repaired by applying prod metadata/snapshot changes first, then restating all models. The second `task verify` passed.

## Limits

- Live Xeno-canto was verified in smoke mode only (`DATABOX_SMOKE=1`, 5 rows), not a full source load.
- The ADK runtime is a deterministic custom `BaseAgent` wrapper through `InMemoryRunner`, not an LLM-backed ADK session.
- The MotherDuck Dive was built locally as Dives-as-code; it was not saved to a live MotherDuck workspace because live MCP/save tooling was unavailable.
- GBIF live smoke was intentionally small in its child-ticket evidence to avoid unnecessary API usage.
