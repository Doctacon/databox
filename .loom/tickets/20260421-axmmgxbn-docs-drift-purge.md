---
id: ticket:docs-drift-purge
kind: ticket
status: ready
created_at: 2026-04-21T21:00:00Z
updated_at: 2026-04-21T21:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 5
depends_on: []
---

# Goal

Eliminate every stale command, phantom file path, and out-of-date diagram node from the repo so a cold reader never catches the project contradicting itself.

# Why

Doc drift is the single cheapest way to blow staff-level credibility. A recruiter opens `CLAUDE.md` first (Anthropic-culture signal) and sees a full block of `databox list` / `databox run ebird` / `databox transform plan` commands — that CLI was ripped out before the Dagster-centric orchestration landed. `transforms/CLAUDE.md` describes a multi-project layout (`transformations/<source>/`, `_shared/`, `home_team/`, `away_team/`) that no longer exists. The root README mermaid diagrams still render "Notebooks via metrics helper" nodes ten minutes after the notebook folder was deleted. ADR-0005 and `docs/incremental-loading.md` reference the ripped-out CLI. These contradictions each look small; together they imply the author doesn't re-read their own repo.

# In Scope

- Root `CLAUDE.md`: delete the `### CLI` command block (lines ~52-64). Leave the `### Task` block. Keep the "Memories" and "Architecture Decisions" sections.
- Delete `transforms/CLAUDE.md` entirely (describes phantom `transformations/<source>/` layout that contradicts ADR-0003's single-project reality). Superseded by `transforms/main/` being self-explanatory.
- Root `README.md` mermaid diagrams: remove `notebook["Notebooks via metrics helper"]` node (line 67), remove `metrics --> notebook` edge (line 85), change `Dive dashboards + notebooks` to `Dive dashboards` (line 107).
- `docs/adr/0005-dagster-as-sole-orchestrator.md`: references to `databox run ebird` / `databox transform run` are historical — verify they are framed as "previous CLI" (fine) vs "current" (fix). The line 9 reference is correctly historical; line 47 uses past tense.
- `docs/incremental-loading.md:95`: replace `databox transform run` with the current Dagster-centric equivalent (`task full-refresh` or `dagster asset materialize`).
- Repo-wide grep: `rg -n 'databox (run|list|validate|transform|status)\b'` and confirm zero remaining **current-tense** references.

# Out of Scope

- Rewriting ADRs (they encode the decision; historical CLI references are fine when clearly past-tense)
- Adding a docs-drift-gate — ticket:docs-drift-gate already exists and is closed; this cleanup is the one-time purge that gate should then keep clean going forward
- Documentation of the `task` equivalents to the old CLI (already covered by `docs/commands.md`)

# Acceptance Criteria

- `rg -n 'databox (run|list|validate|transform plan|transform run|transform test|status)' README.md CLAUDE.md docs/` returns zero matches outside clearly historical/past-tense prose in ADRs
- `transforms/CLAUDE.md` is deleted
- README mermaid diagrams render without any notebook nodes or edges (grep `rg -n 'notebook' README.md` returns zero hits)
- `task docs:build` still passes strict MkDocs build
- `task ci` still green

# Approach Notes

- Do this as one tight commit — `chore(docs): purge stale CLI and notebook references`
- Do not introduce a CI grep rule for the phantom CLI — ticket:docs-drift-gate already runs `generate_docs.py --check` on dictionary drift; CLI-command drift is a one-time debt, not an ongoing regression risk (the CLI is deleted from the codebase)

# Evidence Expectations

- Commit hash showing the purge
- Fresh `rg` output proving zero residual current-tense references
