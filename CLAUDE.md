# Databox Project Guide

## Project Overview
Databox is a dataset-agnostic data platform for a single operator, using zero-cost open-source tooling:
- **dlt (data load tool)** for flexible, Python-native data ingestion
- **sqlmesh** for SQL-based data transformations with built-in testing
- **DuckDB** as the analytical database (single file, no server)
- **Dagster** for orchestration (scheduling, sensors, asset lineage)
- **Typer CLI** (`databox`) for unified command-line interface
- **Streamlit** for a generic DuckDB data explorer

## Project Structure
```
databox/
├── cli/                     # `databox` CLI (Typer)
│   └── main.py              # Commands: run, list, validate, transform, quality, status
├── config/                  # Central configuration
│   ├── settings.py          # Pydantic settings (DB URL, paths, secrets)
│   └── pipeline_config.py   # Per-pipeline YAML config loader + QualityRule
├── sources/                 # dlt data ingestion + source configs
│   ├── base.py              # PipelineSource protocol
│   ├── registry.py          # Auto-discovers sources from sources/<name>/config.yaml
│   ├── ebird/
│   │   ├── config.yaml      # eBird pipeline config
│   │   └── source.py        # eBird dlt source (6 resources)
│   └── noaa/
│       ├── config.yaml      # NOAA pipeline config
│       └── source.py        # NOAA dlt source (daily_weather, stations, datasets)
├── transforms/              # sqlmesh projects
│   ├── ebird/               # eBird transforms (staging → intermediate → marts)
│   ├── noaa/                # NOAA transforms (staging + marts)
│   └── _shared/             # Shared macros, audits, seeds
├── quality/                 # Data quality engine
│   └── engine.py            # check_table() and run_report() pure functions
├── orchestration/           # Dagster orchestration
│   └── definitions.py       # Auto-generated from pipeline registry
├── app/                     # Generic DuckDB data explorer (Streamlit)
│   └── main.py
├── data/                    # Data storage (gitignored)
│   └── databox.db           # DuckDB database
└── scripts/                 # Utility scripts
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
task setup                    # Setup environment
task install                  # Install dependencies
task pipeline:list            # List pipelines
task pipeline:run -- ebird    # Run a pipeline
task transform:plan           # SQLMesh plan
task transform:run            # SQLMesh run
task full-refresh             # Run everything
task streamlit                # Launch data explorer
```

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

## Adding a New Data Source

1. **Create source directory**: `sources/<source>/`
   - `source.py`: dlt resources using `@dlt.source` / `@dlt.resource`, a class implementing `PipelineSource`, and a `create_pipeline(config: PipelineConfig)` factory
   - `config.yaml`: pipeline config (see template below)

2. **Pipeline config template**: `sources/<source>/config.yaml`
   ```yaml
   source_module: "sources.<source>.source"
   description: "Description of the data source"
   schedule:
     cron: "0 6 * * *"
     enabled: true
   params:
     key: value
   quality_rules:
     - column: id
       check: not_null
     - column: status
       check: accepted_values
       values: ["active", "inactive"]
     - column: amount
       check: range
       threshold: 1000000
   transform_project: "<source>"
   ```

3. **Create transform project**: `transforms/<source>/`
   - Copy structure from `transforms/ebird/` as a template
   - Update `config.yaml` to point to `../../data/databox.db`
   - Read from `raw_<source>.*` schemas (auto-created by dlt)
   - Write to `<source>.*` schema

4. **Add secrets to `.env`**: `API_KEY_<SOURCE>=your_key_here`

5. **Test**: `databox run <source>` then `databox transform plan <source>`

No changes needed to orchestration, CLI, or Taskfile — they auto-discover from the registry.

## Data Quality Framework

Quality rules are defined per-source in `sources/<name>/config.yaml` and enforced by `databox quality report`.

Supported checks:
- **not_null**: Column must not contain NULLs
- **unique**: Column values must be unique
- **range**: Column must not exceed `threshold`
- **accepted_values**: Column must be one of `values` list

## Architecture Decisions

1. **Source Co-location**: Each source's config, ingestion code, and tests live together under `sources/<name>/`. The registry auto-discovers sources by scanning for `sources/*/config.yaml`.

2. **Per-Source Transforms**: Each data source gets its own sqlmesh project under `transforms/`. No cross-domain projects.

3. **Schema Isolation**: Pipelines load into `raw_<source>` schemas. Transforms read from `raw_*` and write to `<source>` schemas.

4. **Single Database**: One DuckDB at `data/databox.db`, configured in `config/settings.py`.

5. **Dynamic Orchestration**: Dagster assets are auto-generated from the pipeline registry. No hardcoded asset definitions.

6. **Generic Explorer**: The Streamlit app auto-discovers all schemas/tables from DuckDB. No per-source dashboards needed.

## Security

Never commit secrets. Use `.env` for API keys. Pre-commit hooks catch hardcoded values:
```bash
./scripts/setup_pre_commit.sh
```

## Memories
- This project only has a prod environment (no dev/docker-compose)
- Use `uv` for all package management
- dlt state lives in `.dlt_state/` at project root (not in `data/`)
- Dagster is a core dependency (not optional)

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
