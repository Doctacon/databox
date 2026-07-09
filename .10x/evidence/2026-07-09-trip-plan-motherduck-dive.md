Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-08-build-trip-plan-motherduck-dive.md, .10x/specs/birding-trip-plan-dive.md

# Evidence: Birding Trip Copilot MotherDuck Dive

## What was observed

Implemented the first MotherDuck Dive-as-code surface for persisted Birding Trip Copilot outputs. The Dive queries the `databox.birding_agent` trip-plan persistence tables/views and renders the selected/latest plan, field-plan narrative, ranked recommendations, Open-Meteo weather/elevation evidence, Xeno-canto media/license context, source evidence/provenance, and agent tool traces. A later review fix aligned the Dive tool-trace badge logic and SQL test fixture with the real planner-persisted success status `ok`.

The Dive does not run the Python/Google ADK planner in-browser and does not contain browser-side API secrets.

## Procedure and results

### SQL validation

Validated the section queries against a seeded attached DuckDB catalog shaped like MotherDuck's three-part names:

```bash
.venv/bin/python -m pytest --no-cov tests/test_trip_plan_dive_sql.py -q
```

Result:

```text
1 passed
```

The test validated these query families against `"databox"."birding_agent".*` and seeds tool traces with the planner's real success status `ok`:

- latest plan selector query over `trip_plans`,
- selected plan detail query,
- recommendations query with evidence counts and sources,
- evidence/provenance query,
- Open-Meteo weather/elevation query,
- Xeno-canto media/license query,
- tool trace query.

### Local Dive build/preview validation

Installed local preview dependencies and built the Vite preview bundle:

```bash
cd .dive-preview && npm install
cd .dive-preview && npm run build
```

Result:

```text
vite v6.4.2 building for production...
✓ 1715 modules transformed.
✓ built in 1.28s
```

The preview scaffold now re-exports `dives/birding-trip-plan/birding-trip-plan.tsx` from `.dive-preview/src/dive.tsx`.

### Style/static checks

```bash
.venv/bin/ruff check tests/test_trip_plan_dive_sql.py
.venv/bin/ruff format --check tests/test_trip_plan_dive_sql.py
git diff --check
git diff --cached --quiet
```

Results:

```text
ruff check: All checks passed
ruff format --check: 1 file already formatted
git diff --check: passed
no staged files: yes
```

## What this supports

- The Dive can render from persisted SQL artifacts instead of running the ADK planner in-browser.
- The Dive includes loading, empty, and error states around query sections.
- The Dive exposes evidence/provenance and tool traces, not only final generated prose.
- Successful persisted planner tool traces with status `ok` render as successful/green badges.
- The local preview artifact can be bundled without live MotherDuck save/MCP access.
- The save/update path is documented in `dives/birding-trip-plan/README.md`.

## Limits

- Live MotherDuck MCP/save tooling was unavailable in this run, so no workspace Dive was created or updated.
- `npm install` reported 2 audit findings (1 low, 1 high) in the existing `.dive-preview` dependency tree; resolving preview dependency advisories is outside this ticket's scope.
- The local Vite build validates the preview bundle, not a browser screenshot or live MotherDuck query execution.
