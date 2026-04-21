# Databox Project Guide

## Project Overview
Databox is a dataset-agnostic data platform for a single operator, using zero-cost open-source tooling:
- **dlt (data load tool)** for flexible, Python-native data ingestion
- **sqlmesh** for SQL-based data transformations with built-in testing
- **DuckDB** as the primary database (file-based, zero-infra)
- **Dagster** for orchestration (scheduling, sensors, asset lineage)
- **Typer CLI** (`databox`) for unified command-line interface
- **Soda Core** for data quality contracts per SQLMesh model

## Project Structure
```
databox/
├── packages/                # uv workspace — all Python code lives here
│   ├── databox/             # Shared library
│   │   ├── config/          # Pydantic settings, pipeline config loader
│   │   ├── quality/         # Data quality engine (Soda integration)
│   │   └── orchestration/   # Dagster definitions (assets, jobs, schedules)
│   └── databox-sources/     # dlt sources (ebird, noaa, usgs) + registry
├── transforms/
│   └── main/                # Single SQLMesh project for all sources
│       ├── models/ebird/    # staging → intermediate → marts
│       ├── models/noaa/     # staging → marts
│       ├── models/usgs/     # staging → marts
│       ├── models/analytics/ # cross-domain analytics marts
│       └── tests/
├── soda/
│   └── contracts/           # Soda quality contracts per model
│       ├── ebird_staging/
│       ├── noaa_staging/
│       ├── usgs_staging/
│       ├── ebird/
│       ├── noaa/
│       ├── usgs/
│       └── analytics/
├── app/                     # Streamlit data explorer
│   └── main.py
├── scripts/                 # Utility scripts
└── data/databox.duckdb      # DuckDB database file (gitignored)
```

### Schema Layering (DuckDB)
```
raw_ebird / raw_noaa        ← dlt loads (untouched API data)
ebird_staging / noaa_staging ← SQLMesh stg_* views (column renames only)
ebird / noaa                ← SQLMesh int_* and fct_*/dim_* marts
analytics                   ← cross-domain SQLMesh marts
```

## Key Commands

### CLI
```bash
databox list                              # List registered pipelines
databox run ebird                         # Run a pipeline
databox validate ebird                    # Check pipeline config/credentials
databox transform plan                    # Preview SQLMesh changes
databox transform run                     # Apply SQLMesh transforms
databox transform test                    # Run SQLMesh tests
databox quality check ebird.stg_ebird_observations  # Table quality checks
databox quality report                    # Run all configured quality rules
databox status                            # Show pipeline status & freshness
```

### Task
```bash
task setup                    # Create .venv + bootstrap .env
task install                  # uv sync + pre-commit hook install
task full-refresh             # Dagster: all dlt + SQLMesh + Soda
task verify                   # Smoke full-refresh (DATABOX_SMOKE=1)
task ci                       # Ruff + mypy + pytest + secret scan
task dagster:dev              # Launch Dagster UI
task streamlit                # Launch data explorer
```

Raw SQLMesh / Dagster / pytest invocations: [docs/commands.md](docs/commands.md).

## Data Sources

### eBird
- **API**: eBird API v2 (free, requires token)
- **Resources**: recent_observations, notable_observations, species_list, hotspots, taxonomy, region_stats
- **Transforms**: staging (observations, hotspots, taxonomy) → intermediate (enriched with taxonomy + haversine) → marts (daily bird observations)
- **Config**: `sources/ebird/config.yaml`

### NOAA CDO
- **API**: NOAA Climate Data Online v2 (free, requires token)
- **Resources**: daily_weather (TMAX/TMIN/PRCP/SNOW/AWND), stations, datasets
- **Transforms**: staging (daily_weather, stations) → marts (fct_daily_weather with pivoted metrics)
- **Config**: `sources/noaa/config.yaml`

### USGS Water Services
- **API**: NWIS Daily Values (no API key required)
- **Resources**: daily_values (discharge/gage height/water temp), sites
- **Transforms**: staging (daily_values, sites) → marts (fct_daily_streamflow pivoted)
- **Config**: `sources/usgs/config.yaml`

## Adding a New Data Source

1. **Create source package**: `packages/databox-sources/databox_sources/<source>/`
   - `source.py`: dlt resources using `@dlt.source` / `@dlt.resource`
   - `config.yaml`: pipeline config

2. **Add transform models**: `transforms/main/models/<source>/`
   - Copy structure from `transforms/main/models/ebird/` as a template
   - Read from `raw_<source>.*` (dlt writes here)
   - Staging models write to `<source>_staging.*`
   - Mart models write to `<source>.*`

3. **Add Soda contracts**: `soda/contracts/<source>_staging/` and `soda/contracts/<source>/`

4. **Wire Dagster assets** in `packages/databox/databox/orchestration/definitions.py`

5. **Add secrets to `.env`**: `API_KEY_<SOURCE>=your_key_here`

## Architecture Decisions

1. **uv Workspace**: All Python code in `packages/`. Root `pyproject.toml` is a virtual coordinator (`package = false`). Each package has its own `pyproject.toml`.

2. **Single Transform Project**: All sources share one sqlmesh project at `transforms/main/`. Models are organized by source but live in the same sqlmesh environment, avoiding state conflicts.

3. **Schema Layering**: dlt loads into `raw_<source>`. SQLMesh staging views live in `<source>_staging`. Marts live in `<source>` or `analytics`. No data ever flows backwards.

4. **Explicit Dagster Assets**: Each SQLMesh model is a separate Dagster asset. Dependencies are declared explicitly — no magic auto-discovery. This gives clean lineage in the Dagster UI.

5. **Soda Contracts per Asset**: Every SQLMesh model has a corresponding Soda contract that runs as a Dagster asset check after materialization.

## Security

Never commit secrets. Use `.env` for API keys. Pre-commit hooks catch hardcoded values:
```bash
./scripts/setup_pre_commit.sh
```

## Memories
- Use `uv` for all package management
- dlt state lives in `.dlt_state/` at project root (not in `data/`)
- Dagster is a core dependency (not optional)
- After adding new SQLMesh models, run `sqlmesh plan --auto-apply prod` in `transforms/main/` to create prod virtual views before Soda contracts can query them
- Backend switching: set `DATABOX_BACKEND=motherduck` (+ `MOTHERDUCK_TOKEN`) in `.env` to use MotherDuck cloud. Default is `local`. The SQLMesh gateway and Soda datasource derive from `DATABOX_BACKEND` — no separate flag.
- `databox.config.settings` is the single source of truth for runtime config. SQLMesh reads it via `transforms/main/config.py`; Dagster reads it via the `settings` singleton; Soda datasource YAML is rendered from `settings.soda_datasource_yaml`.

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (90-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk vitest run          # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%)
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->
