---
id: ticket:incremental-load-audit
kind: ticket
status: complete_pending_acceptance
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-20T23:34:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 3
---

# Goal

Audit and document the incremental-load behavior of every dlt source. For each resource, write down the write disposition, merge key, idempotency guarantee, and backfill procedure. Add a regression test that re-running a load twice produces the same final row set.

# Why

"Explain your incremental strategy" is the single most common deep-dive question in staff-level data engineering interviews. The code already has a strategy per source — it is just not inspectable. A recruiter who cannot find it will assume it doesn't exist.

# In Scope

- Per source (`ebird`, `noaa`, `usgs`), per resource:
  - document write disposition (`append` / `replace` / `merge`)
  - document primary/merge keys
  - document the high-watermark field (if incremental) and how it is stored
  - document the idempotency guarantee in plain English
- A single `docs/incremental-loading.md` consolidating all of the above
- A pytest-based regression test per source: run pipeline twice against fixture data, assert final row counts and primary-key sets are identical
- A documented backfill procedure per source with the exact command (typer/Dagster) and expected blast radius
- A Dagster "backfill" sensor or scheduled job reference for each source (if not present, stub it with a comment)

# Out of Scope

- Changing existing write dispositions — this ticket is documentation + tests, not a refactor
- Adding new incremental-capable resources
- CDC / log-based replication
- Rewriting dlt state storage

# Acceptance Criteria

- `docs/incremental-loading.md` exists, covers every currently-registered resource, and is linked from README
- Per-source idempotency test passes in CI
- Backfill procedure for each source is tested once manually and the command is pasted into the doc
- A table at the top of `docs/incremental-loading.md` summarizes: source / resource / disposition / key / watermark / backfill command

# Approach Notes

- dlt source configs already encode disposition — generate the summary table from those configs if possible, then hand-edit the prose
- Idempotency test pattern: load fixture → snapshot table → load fixture again → assert no diff
- For `append`-mode resources without natural keys, "idempotent" means "deterministic duplicates" — document that honestly

# Evidence Expectations

- Link to `docs/incremental-loading.md`
- CI run showing the idempotency tests green
- Paste of the summary table in the ticket close notes
