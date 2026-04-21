---
id: ticket:new-source-generator
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T19:30:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  plan: plan:scaffold-polish
  phase: 2
depends_on:
  - ticket:source-layout-convention
  - ticket:fork-friendly-bootstrap
---

# Goal

`task new-source -- <name> [--shape rest|file|database]` creates the full per-source directory tree and Dagster domain file stub. The output passes `source-layout-lint` on first commit. A forker goes from "I want to ingest X" to "I have a running empty pipeline scaffold" in under 60 seconds.

# Why

Today, adding a source means five manual steps spread across four directories and two package roots. The step list lives in `CLAUDE.md` and is easy to miss something. The layout convention (ticket:source-layout-convention) knows exactly what shape is required — the generator should produce exactly that shape.

At 20 sources, whether the generator exists is the difference between onboarding new sources being a half-hour task or a half-day task. At 3 sources it is merely convenient. But Phase 2 is the right time because the convention has stabilised.

# In Scope

- `scripts/new_source.py` (invokable via `task new-source -- <name>`):
  - args: `name` (required), `--shape rest|file|database` (default `rest`), `--dry-run`
  - creates:
    - `packages/databox-sources/databox_sources/<name>/__init__.py`
    - `packages/databox-sources/databox_sources/<name>/source.py` — dlt source stub with at least one `@dlt.resource` and TODO markers
    - `packages/databox-sources/databox_sources/<name>/config.yaml` — minimal pipeline config
    - `transforms/main/models/<name>/staging/.gitkeep`
    - `transforms/main/models/<name>/marts/.gitkeep`
    - `soda/contracts/<name>_staging/.gitkeep`
    - `soda/contracts/<name>/.gitkeep`
    - `packages/databox/databox/orchestration/domains/<name>.py` — stub with empty `assets`, `asset_checks`, `schedules`, `sensors` exports
  - wires the new domain module into `packages/databox/databox/orchestration/definitions.py` imports
  - adds `API_KEY_<NAME_UPPER>=` stub to `.env.example` if `--shape rest`
  - prints a 5-step next-steps list (add resources, write staging SQL, add Soda contracts, materialize, configure schedule)
- Templates live in `scripts/templates/source/` — one subdir per shape
- Shape-specific template differences:
  - `rest`: RestClient-based dlt source scaffold + token env var in config
  - `file`: filesystem/S3 source stub
  - `database`: SQL database connector stub
- Unit tests using `tmp_path` to materialise a scaffold and assert it passes `check_source_layout.py` (with the `scaffold-lint: skip=scaffolded` marker while empty, which the linter permits)
- `docs/new-source.md` walk-through: generator → fill in resources → first contract → first mart

# Out of Scope

- Automatic API-schema inference (pointing at an OpenAPI spec and generating resources) — noble but out of scope
- A GUI / TUI wrapper
- Generating unit tests for the new source (forker writes those as they fill in logic)

# Acceptance Criteria

- `task new-source -- demo --shape rest` produces a tree that:
  - passes `scripts/check_source_layout.py` with the scaffolded-skip marker
  - compiles (`uv run mypy packages/databox-sources/databox_sources/demo/`)
  - doesn't break Dagster load (`uv run dagster definitions list -m databox.orchestration.definitions` shows the demo domain with zero assets)
- Running the same command twice without `--force` refuses to overwrite; with `--force` it regenerates
- `--dry-run` prints the file tree that would be created, no writes
- `docs/new-source.md` walks through the whole first-source flow from generator to first green Soda contract
- Generator runs in ≤2 seconds on a warm uv env
- At least one happy-path unit test per shape

# Approach Notes

- Prefer Jinja2 for templates; keep template files as valid Python/YAML/SQL so editor tooling works on them (token delimiters `{{ }}` are fine because Python doesn't mind)
- The domain-module template imports the dlt source and SQLMesh assets from their eventual locations, even if empty — wire goes in now, removes surgical-edit burden later
- For the `.gitkeep` files under model directories: SQLMesh ignores empty dirs, so these are for git's benefit only; document this
- Use `scaffold.yaml` project identity for any templated identifiers (package name in imports, etc.)

# Evidence Expectations

- Demo PR generating a throwaway source, showing green `source-layout-lint` job on a scaffolded-skip PR
- Screenshot of the printed next-steps list
- `docs/new-source.md` rendered in deployed docs site

# Close Notes

Verified on main 2026-04-21: `scripts/new_source.py` present, `task new-source` target wired, `docs/new-source.md` published. Deliverable landed during earlier scaffold-polish work; ledger reconciled during status audit.
