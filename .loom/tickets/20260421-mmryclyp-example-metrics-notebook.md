---
id: ticket:example-metrics-notebook
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
depends_on: []
---

# Goal

`notebooks/metrics_demo.ipynb` runs end-to-end against the flagship mart (`analytics.fct_species_environment_daily`) using the metrics helper shipped with ticket:semantic-metrics-layer. Produces at least three charts: a time-series of a core metric, a cross-domain slice, and a comparative breakdown. Rendered output is published under `docs/examples/metrics-demo/` as part of the docs site.

# Why

`docs/metrics.md` explains the metrics layer in prose. A forker reading it has to assemble a mental model of how to consume it. A runnable notebook is a far better teacher — paste-and-modify is the actual onboarding path for a data consumer. Today there is no runnable example; the metrics layer exists but its consumption surface is abstract.

Also: the deployed dashboard (Dive) is a different class of consumer — a visualisation tool. A notebook shows the programmatic path that any analyst or downstream application would take.

# In Scope

- `notebooks/metrics_demo.ipynb` in committed form (with outputs cleared or stripped in pre-commit; rendered versions live under `docs/`)
- Notebook structure:
  - Markdown intro: what the flagship mart is, what the notebook shows
  - Config cell: reads `DATABOX_BACKEND` via unified settings (works on local DuckDB or MotherDuck)
  - Load cell: connects to the warehouse
  - Metric invocation cell: uses the metrics helper (e.g. `from databox.metrics import hot_day_count`) to query a core metric
  - Chart 1: daily time-series of the metric
  - Chart 2: cross-domain slice (species × weather band)
  - Chart 3: comparative breakdown (top N hotspots by the metric)
  - Markdown close: pointers to the metrics spec and ADR-0002 explaining SQLMesh metrics
- Plotting library: `matplotlib` (zero-config, works in the docs rendering) — no Plotly, no Altair (too many deps)
- `nbconvert`-rendered HTML under `docs/examples/metrics-demo/index.html`
- `scripts/render_notebooks.py` — runs the notebook headlessly and exports HTML; wired into `task docs:build`
- Link from `docs/metrics.md` and from the root `docs/index.md` "What's here" list
- MkDocs nav entry under an "Examples" section

# Out of Scope

- Teaching pandas (the notebook assumes reader knows pandas basics)
- Multiple notebooks for multiple metrics (one is enough; the pattern is the lesson)
- Making the notebook runnable without the full stack (it assumes the flagship mart exists; run after `task full-refresh`)
- A Dive / Streamlit equivalent (separate concern)

# Acceptance Criteria

- `notebooks/metrics_demo.ipynb` executes cleanly end-to-end via `uv run jupyter nbconvert --to notebook --execute`
- Execution works on both backends (`DATABOX_BACKEND=local` and `DATABOX_BACKEND=motherduck`)
- `scripts/render_notebooks.py` produces `docs/examples/metrics-demo/index.html` deterministically
- `task docs:build` regenerates the rendered notebook
- MkDocs strict build includes the rendered notebook page, link from metrics.md works
- Three charts render with axis labels, titles, and a consistent colour theme
- CI includes an optional `notebooks` job that executes the notebook on main merges (keeps it from rotting)

# Approach Notes

- Prefer `%matplotlib inline` + explicit `plt.savefig(...)` in cells if embedding into HTML needs deterministic image paths; `nbconvert` handles inline outputs fine for most cases
- Keep the notebook short (≤30 cells) — readability matters more than feature coverage
- Use SQL-first queries where possible (`conn.execute("SELECT ...")` returning a DataFrame); showcases DuckDB's strength
- Clear outputs in the committed `.ipynb` to keep diffs clean (pre-commit hook via `nbstripout`)

# Evidence Expectations

- Rendered notebook HTML linked from the deployed docs site
- CI `notebooks` job run showing clean execution on both backends
- The three charts inline in the ticket close-out (or linked in the PR description)

# Close Notes

Verified on main 2026-04-21: `notebooks/metrics_demo.ipynb` present, `docs/examples/metrics-demo/` rendered, docs site links active. Deliverable landed during earlier scaffold-polish work; ledger reconciled during status audit.
