---
id: ticket:backfill-dr-runbook
kind: ticket
status: ready
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  plan: plan:scaffold-polish
  phase: 3
depends_on: []
---

# Goal

`docs/runbook.md` covers four production-failure scenarios with copy-pasteable commands: blown DuckDB file, partial backfill of a single source, MotherDuck point-in-time recovery, and paused-schedule resumption. Each scenario gives the exact commands, expected outputs, and rollback instructions. A forker handling an incident at 3am should not need to reverse-engineer the stack.

# Why

Today the closest thing to operational guidance is `CLAUDE.md` command snippets. Those are for getting started, not recovering from incidents. A scaffold claiming "production-quality" without an incident runbook is not the ultimate starting point.

Four scenarios cover the realistic failure modes of this stack:

1. **Blown DuckDB file** (local): file corrupt, disk full mid-write, SQLMesh state desynced from table data
2. **Partial backfill** of a single source: one source had a bad day; need to replace 2025-04-18..2025-04-20 without touching other sources
3. **MotherDuck PIT recovery**: MotherDuck retains point-in-time snapshots — document how to restore and validate
4. **Paused schedule resumption**: schedule was off for days; need to catch up without double-materialising

# In Scope

- `docs/runbook.md` with one section per scenario. Each section has:
  - **Symptoms**: what a forker sees when this has happened
  - **Diagnosis**: one or two commands to confirm the diagnosis
  - **Recovery**: numbered steps with exact commands
  - **Validation**: how to confirm recovery succeeded (usually a Soda contract re-run + a freshness check pass)
  - **Rollback**: how to undo if the recovery itself goes wrong
- Cross-references to existing docs: `docs/environments.md` (for dev → prod), `docs/freshness.md` (for SLA resume)
- A "prevention" appendix listing pre-commit / CI checks that each scenario's underlying class of error would be caught by
- Link from README
- Link from `CLAUDE.md` memories block so future sessions remember the runbook exists

# Out of Scope

- Automated DR tooling (this is doc-first; automation is a follow-up if scenarios get frequent)
- Multi-region failover (single-operator scaffold — YAGNI)
- Source-specific recovery guides (the generic partial-backfill pattern is enough; sources follow it)
- Incident review / post-mortem templates (separate concern)

# Acceptance Criteria

- `docs/runbook.md` covers all four scenarios with the full symptoms / diagnosis / recovery / validation / rollback structure
- Each scenario has been manually rehearsed at least once on a throwaway dataset; the recorded commands in the doc are the commands that worked
- Total length is ≤400 lines (runbook should be scannable; deep dives link out)
- MkDocs strict build clean
- Linked from README and CLAUDE.md
- Prevention appendix maps each scenario to an existing check or flags missing checks as follow-up tickets

# Approach Notes

- Write each scenario against the current reality of the stack (DuckDB, MotherDuck, SQLMesh virtual envs, Dagster schedules)
- For the "blown file" scenario, the canonical recovery is usually: restore from git-ignored backup OR full-refresh from raw dlt state. Document both paths
- For partial backfill: SQLMesh `plan --start <date> --end <date> --restate-models <model>` is the right primitive — show it working end-to-end
- For MotherDuck PIT recovery: depends on MotherDuck's documented snapshot semantics (verify current API/UI surface before writing)
- For paused schedules: Dagster `daemon tick` behaviour + `dagster run launch --backfill` is the right tool

# Evidence Expectations

- `docs/runbook.md` rendered in deployed docs site
- Evidence-of-rehearsal: a short note per scenario in the PR description summarising the throwaway-dataset test
- Follow-up ticket(s) created for any prevention-appendix gap (and linked from this ticket's close notes)
