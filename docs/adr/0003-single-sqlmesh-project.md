# ADR-0003: Single SQLMesh project across all sources

**Status:** Accepted · 2026-02

## Context

The platform ingests from three sources (eBird, NOAA, USGS) with distinct
staging layers. An earlier iteration used one SQLMesh project per source
under `transformations/ebird/`, `transformations/noaa/`, `transformations/usgs/`,
each with its own `config.yaml` and its own state.

This worked until the first cross-domain mart. Joining observations across
multiple source-scoped projects requires either:

1. materializing each source into a shared catalog and running a fourth
   "home-team" project on top, or
2. treating each cross-domain query as a single-use script outside the
   transformation framework, or
3. collapsing everything into one project.

Option 1 duplicates state. SQLMesh maintains its own snapshot/state table
per project; keeping four projects in sync mid-refresh was fragile. Option
2 surrenders every benefit of SQLMesh (tests, lineage, environments) for
cross-domain models, which are exactly where the interesting analytics
live.

## Decision

Collapse all source-specific projects into a **single SQLMesh project**
at `transforms/main/`. Models are namespaced by source schema
(`ebird.*`, `ebird_staging.*`, `noaa.*`, `usgs.*`, `analytics.*`) but share
one project, one state, one `sqlmesh plan`.

## Consequences

**Positive:**
- One DAG. Cross-domain marts (`analytics.fct_species_environment_daily`)
  are first-class, not a bolt-on.
- One `sqlmesh plan` shows every downstream impact of a change,
  regardless of source boundary.
- One environment promotion gates the entire graph consistently.
- The Dagster asset graph maps 1:1 to SQLMesh models — simpler
  orchestration wiring.

**Negative:**
- A single-source change forces re-planning against the whole project.
  Plans stay fast (~seconds) at current scale but this would start to
  hurt past low-hundreds of models.
- No hard wall between source teams. At a real organization with
  independent owners per source, separate projects (with explicit
  contracts between them) might be worth the state-management cost.

**Neutral:**
- Folder structure under `transforms/main/models/` still organizes by
  source for humans — the single-project decision is about SQLMesh state,
  not repo layout.
