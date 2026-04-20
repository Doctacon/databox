---
id: ticket:one-command-demo
kind: ticket
status: ready
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-20T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 4
depends_on:
  - ticket:flagship-cross-domain-mart
  - ticket:data-dictionary-site
---

# Goal

One command — `task demo` — brings up the full local stack, seeds it with a small committed fixture dataset, runs the transforms, launches Dagster on `:3000`, launches the Dive/Streamlit dashboard for the flagship mart on a well-known port, and prints both URLs.

# Why

The difference between "interesting repo" and "I ran it myself in five minutes" is huge for a recruiter. Every barrier (API keys, manual seeding, waiting for live ingests) is a reason they close the tab. A committed fixture path bypasses all of it.

# In Scope

- A small fixture dataset committed under `fixtures/demo/` containing enough rows of each raw source to materialize the flagship mart meaningfully (one H3 cell, 30 days, a handful of species)
- A `databox.demo` code path that loads fixtures directly into `raw_<source>` DuckDB files (no API calls)
- `task demo` target that: wipes local DuckDB state, runs fixture load, runs SQLMesh, launches Dagster (background), launches dashboard (background), prints URLs
- `task demo:down` target that kills background processes and cleans state
- A dashboard view of the flagship mart — Dive-preview or Streamlit, whichever is already wired — that renders at least one map (H3 choropleth) and one time series from the mart
- Docker Compose alternative (`docker compose up`) for operators who don't want `uv` locally, producing the same two URLs

# Out of Scope

- Production-grade Docker image (multi-stage, minimal base, CVE scanning)
- Seeding the MotherDuck backend
- Hot-reload on fixture changes
- Auth on the local dashboards

# Acceptance Criteria

- Fresh clone → `uv sync` → `task demo` → two URLs print → both load successfully → mart has rows
- `docker compose up` produces the same two URLs without requiring `uv` on the host
- Total cold-start time from `task demo` to live dashboard is under three minutes on a reasonable laptop
- Fixtures are under 10 MB total (so repo clones stay fast)
- README quickstart lives on top of this target

# Approach Notes

- Fixtures should be real recorded responses redacted to one H3 cell's worth of entities — not synthetic — so the demo is narratively honest
- Dashboard: choose Dive if the flagship mart is already wired there; otherwise a minimal Streamlit app under `app/` is fine
- For Docker Compose, one `python` service running `task demo` is enough — no need to split orchestrator and dashboard into separate containers for a demo
- Skip Motherduck entirely in the demo path — local DuckDB keeps it hermetic

# Evidence Expectations

- Screen recording (linked GIF or video) of fresh clone → `task demo` → live dashboard
- Screenshots in the README
- `task demo:down` leaves the working tree clean (verified with `git status`)
