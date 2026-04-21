---
id: ticket:scaffold-settings-codegen
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T17:00:00Z
scope:
  kind: workspace
links:
  parent: ticket:add-usgs-earthquakes-source
---

# Goal

Extend `scripts/new_source.py` to patch `packages/databox/databox/config/settings.py`
with the three entries every new source requires:

1. a `raw_<source>_path` property on `DataboxSettings`
2. a `"raw_<source>": str(DATA_DIR / "raw_<source>.duckdb"),` entry in `local_gateway.catalogs`
3. a `"raw_<source>": "md:raw_<source>",` entry in `motherduck_gateway.catalogs`

# Why

Friction point #1 in `ticket:add-usgs-earthquakes-source` close notes. Today the scaffold
generates 8 files but does not touch `settings.py`. The Dagster domain file relies on
`settings.raw_<source>_path`, and SQLMesh's per-source catalog attach needs both catalog
entries. A forker who follows `CLAUDE.md` step-by-step will hit `AttributeError` on their
first `task dagster:dev` run.

# In Scope

- `scripts/new_source.py` gains a `wire_settings(name)` function, called after
  `wire_definitions` in `main()`.
- Idempotent: running the scaffold twice is a no-op on `settings.py`.
- `print_next_steps` no longer asks the operator to manually edit `settings.py`.
- Tests (at least a dry-run + a real run against a temp settings file) verify the patch
  is well-formed and that re-running does not duplicate entries.

# Out of Scope

- Reworking `DataboxSettings` into a data-driven catalog (one ticket at a time).
- Touching the dlt_data_dir / env-token plumbing for the new source.

# Acceptance

- `python scripts/new_source.py foo && rg '"raw_foo"' packages/databox/databox/config/settings.py`
  shows both catalog entries.
- `rg 'def raw_foo_path' packages/databox/databox/config/settings.py` shows the property.
- Re-running the scaffold does not double-patch.
- `task ci` passes.

# Close Notes — 2026-04-21

`wire_settings(name)` added to `scripts/new_source.py`; called from `main()` after
`wire_definitions`. Idempotent via three string-anchor checks (property name,
`local_gateway` catalog entry, `motherduck_gateway` catalog entry). Test harness
now seeds a stub `settings.py` with the exact anchors; new test
`test_settings_wired_idempotently` verifies first-run patching and that
`--force` re-scaffolding does not double-patch.

14/14 `tests/test_new_source.py` green.
