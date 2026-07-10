# Commands Cheatsheet

`Taskfile.yaml` only keeps targets that **compose multiple commands**,
**inject environment variables**, or **encode a non-obvious default**.
Everything else is a direct call into a third-party CLI — listed below
so a forker can run the underlying command without learning a Task
target that merely renamed it.

All `uv run` commands assume you are at the repo root.

## Linting + formatting

```bash
uv run ruff check .                  # lint
uv run ruff check . --fix            # lint + auto-fix
uv run ruff format .                 # format in place
uv run ruff format --check .         # format check (no write)
uv run mypy . --ignore-missing-imports
```

`task ci` composes all four gates plus pytest + secret scan.

## Testing

```bash
uv run pytest                        # full suite
uv run pytest -m unit                # unit tests only
uv run pytest -m integration         # integration tests
uv run pytest -m e2e                 # end-to-end tests
uv run pytest --cov=. --cov-report=html
```

Test markers are defined in `pyproject.toml` under `[tool.pytest.ini_options]`.

## Agent evaluations

```bash
task eval:agent
```

This runs the deterministic DeepEval suite at
`tests/evals/test_birding_trip_copilot_deepeval.py`. The target opts out of
DeepEval telemetry, keeps the cache under the ignored `.cache/` tree, disables
browser opening, and sets `PYTEST_ADDOPTS=--no-cov` so the focused eval run is
not affected by the repository-wide coverage gate. It uses a fake model client
and makes no live Cloudflare request.

Opt in to one live credential/model check with:

```bash
task smoke:cloudflare-ai
```

The smoke command uses only `@cf/zai-org/glm-5.2` and never prints
Cloudflare credentials.

## Local Trip Planner

```bash
task app:dev           # FastAPI :8000 + Vite :5173 with hot reload
task app:check         # typecheck + tests + build + configured bundle audit
task app:audit-bundle  # audit an existing build for configured names and values
task app               # build and serve the complete app at http://127.0.0.1:8000
```

Both launch paths bind to loopback. Run `task verify` first to populate the
local warehouse. The Trip Planner remains at `/`; the read-only Arizona Birds
catalog is available at `/birds`, with direct modeled profiles at
`/birds/{species_code}`. Native browser history supports direct reload,
back, and forward without a routing dependency. Catalog search, species/hybrid
filtering, and 24-row pagination operate entirely on the bounded 706-row API
snapshot; profile pages use only persisted modeled facts and public Arizona
locations, with no request-time discovery or mutation. A public modeled location
whose name includes `(private)` is shown with an access-restriction warning;
eBird's modeled privacy flag, not the display-name suffix, governs observation
privacy. The private local collection UI is available at `/my-birds` with Life
List, Observations, Wishlist, and Watches surfaces. Species profiles expose only
explicit collection mutations. Watch centers are per-watch Arizona selections;
the browser stores no global home location, and none of these controls evaluate
matches or trigger weather, model, calendar, or SMTP work.

The local personal-collection API stores runtime-owned tables in
`birding_personal` inside the same DuckDB file. It exposes observation CRUD at
`/api/observations`, the derived `/api/life-list`, idempotent `/api/wishlist`,
per-species `/api/watches`, and `/api/birds/{species_code}/collection-state`.
Observation deletion requires `confirm=true`; life-list membership is never an
independent stored flag. Collection reads are network-free, and collection
mutations do not evaluate watches or call weather, models, calendar, or SMTP.

The browser calls `/api/*`; only the Python process can access
DuckDB or Cloudflare credentials. After any standalone build, the copy-pasteable
`task app:audit-bundle` command checks the compiled files for all configured
Cloudflare variable names and non-empty local values without printing secrets.

Location autocomplete calls Open-Meteo geocoding through the local Python API;
the browser never calls the upstream service directly. Search results and manual
coordinates are restricted with a compact official US Census TIGERweb-derived
Arizona polygon because the current bird evidence is Arizona-scoped. A missing
negative longitude such as `34.54,112.50` is rejected
before weather, evidence, model, or persistence work; valid Arizona coordinates
such as `34.54,-112.50` remain available when geocoding is unavailable. Selected
location identity and all completed plan artifacts persist in the single local
`data/databox.duckdb` warehouse.

GBIF planner evidence is conformed to the eBird-first species dimension by an
authority-free scientific-name key, so available common names lead result cards
while the scientific name remains visible underneath. Open-Meteo measurements
are reloaded from the persisted trip-plan evidence payload and displayed in both
US customary and metric units; the browser does not refetch or ask the model to
convert weather values.

Xeno-canto metadata, URLs, recordist attribution, and licenses are reloaded from
persisted DuckDB evidence. The API exposes a separate typed media projection and
activates source/audio URLs only for exact HTTPS Xeno-canto hosts, matching
recording IDs, and expected `/{id}` or `/{id}/download` paths. The React app uses
native audio controls with `preload="none"` and no autoplay. Audio bytes stream
directly from Xeno-canto only after user interaction; Databox does not proxy,
download, cache, or store audio.

Existing persisted recommendations are enriched only by an explicit local
maintenance command. Stop source refresh and the local API writer first, inspect
the bounded target set, then apply once:

```bash
task media:backfill -- --dry-run
task media:backfill -- --apply
```

Dry-run opens `data/databox.duckdb` read-only and performs no discovery. Apply
uses DuckDB's single-writer transaction and the same validated GBIF/Xeno-canto
selector used for new plans. It inserts only missing photo/call JSON metadata,
including durable unavailable results; a one-time compatibility repair replaces
only exact `media_backfill_v2_` GBIF rows having the defective unavailable status
and caveat from before the reviewed HTTP-license and `United States of America`
normalization fix. It does not invoke the model,
alter plan content, or download/proxy media bytes. Re-running apply is a no-op after
every recommendation has one current photo and one call result. `--database-path` may target a
test copy; it does not create a missing database.

## SQLMesh

Run from `transforms/main/` — SQLMesh picks up `config.py` there.
Logs land in `.logs/sqlmesh/` via the local `transforms/main/logs`
symlink (gitignored; created by `task install`).

```bash
cd transforms/main
uv run sqlmesh plan --auto-apply     # plan + apply changes
uv run sqlmesh run                   # run scheduled models
uv run sqlmesh test                  # run SQLMesh unit tests
uv run sqlmesh ui                    # start SQLMesh UI
uv run sqlmesh plan dev              # plan into dev env
```

## Dagster (beyond `dagster:dev` / `full-refresh` / `verify`)

```bash
export DAGSTER_HOME="$PWD/.dagster"
export PYTHONPATH="$PWD"

uv run dagster asset materialize --select <key> \
  -f packages/databox/databox/orchestration/definitions.py

uv run dagster asset wipe --all \
  -f packages/databox/databox/orchestration/definitions.py
```

## Pre-commit

```bash
uv run pre-commit run --all-files    # run every hook across every file
uv run pre-commit run ruff           # run one hook
```

## Secret scan

```bash
python scripts/check_secrets.py      # scan repo root
python scripts/check_secrets.py path/to/file.py
```

## Source layout + staging codegen

```bash
python scripts/check_source_layout.py        # lint per-source directory layout
python scripts/generate_staging.py           # regenerate trivial-rename stg_* SQL
python scripts/generate_staging.py --check   # fail on drift (also runs in task ci)
```

## Watching

Task's built-in watch mode works without a dedicated target:

```bash
task -w ci                           # re-run ci on file change
```
