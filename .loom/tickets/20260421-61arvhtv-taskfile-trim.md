---
id: ticket:taskfile-trim
kind: ticket
status: ready
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  plan: plan:scaffold-polish
  phase: 1
depends_on:
  - ticket:definitions-split
---

# Goal

Cut `Taskfile.yaml` from 224 lines to ≤100. Remove targets that exist only as one-for-one wrappers around `uv run sqlmesh ...` or `uv run dagster ...` — those are strictly overhead. Keep only targets that compose, set env, or encode genuinely useful defaults.

# Why

ADR-0005 says the Taskfile is intentionally thin. The current file is thin in design intent but thick in line count — many targets exist that just forward positional args into a long `uv run ...` command with no added value. Every one of those targets is an extra thing a forker must learn, and every one lies about being a "databox" concept when it is really just sugar over a third-party CLI.

A forker reading a ≤100-line Taskfile sees: "these are the composed workflows that matter." That is the ergonomic win.

# In Scope

- Audit every target in `Taskfile.yaml`; classify each as:
  - **compose** (runs multiple commands, e.g. `full-refresh` = dlt + sqlmesh + soda)
  - **env-setting** (injects `DATABOX_BACKEND=...` or similar before running a command)
  - **wrapper** (pure passthrough to `uv run sqlmesh ...` / `uv run dagster ...` / etc.)
- Delete wrapper targets; document the underlying CLI invocation in a `docs/commands.md` cheatsheet
- Preserve compose and env-setting targets
- Consider consolidating `dagster:dev`, `dagster:materialize`, `dagster:wipe` into one namespace or merging where trivial
- Keep essential forker-facing targets: `setup`, `install`, `full-refresh`, `plan:dev`, `plan:prod` (the last two added in ticket:dev-prod-envs — coordinate)
- Update `README.md` Quickstart if any referenced target is renamed or removed
- Update `CLAUDE.md` command section similarly

# Out of Scope

- Switching from Task to Make / Just / shell scripts
- Adding new targets unrelated to the trim (`plan:dev` / `plan:prod` belong to ticket:dev-prod-envs)
- Restructuring the Taskfile into `includes:` (unless the line budget forces it)

# Acceptance Criteria

- `wc -l Taskfile.yaml` ≤ 100
- Every remaining target has a one-line `desc:` explaining why it is not a raw CLI call
- `docs/commands.md` exists and lists the underlying commands for anything removed
- `README.md` Quickstart commands still work
- `task --list` output is readable (not overwhelming)
- Full-refresh on a fresh checkout still works: `task install && task full-refresh`

# Approach Notes

- When in doubt, delete — if a forker needs the raw command, `docs/commands.md` has it
- Composed targets (those that chain 2+ commands) are the most valuable; keep them even if individually each step is reachable via CLI
- `dagster:dev` is a legitimate compose target (starts the UI with right env + module path); keep it

# Evidence Expectations

- Before/after line count
- `task --list` output in PR description
- `docs/commands.md` rendered in deployed docs site

# Work Log

## 2026-04-21 — Partial progress noted during ledger audit

- Current `Taskfile.yaml`: 163 lines (was 224). Some trim landed incidentally across other scaffold-polish tickets.
- Target ≤100 still unmet — 63 lines over.
- `docs/commands.md` exists (81 lines).
- Remaining work: classify the ~12 targets still present, delete the pure wrappers, push remainder into `docs/commands.md`.

This ticket stays `ready` — strict acceptance not met; real outstanding scaffold-polish deliverable.
