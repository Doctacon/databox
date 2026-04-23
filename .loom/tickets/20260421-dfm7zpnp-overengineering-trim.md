---
id: ticket:overengineering-trim
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

Make one explicit keep-or-cut decision for every piece of enterprise-flavor tooling in the stack. Write it as an ADR. The goal is not to trim for trimming's sake — it's to stop leaving scale-appropriate-but-unused machinery in the repo for a reviewer to misread as cargo-culting.

# Why

The stack for a single-operator, four-public-API, daily-cadence project currently includes: Dagster + SQLMesh + dlt + Soda Core + MotherDuck + OpenLineage + H3 + VCR + MkDocs-Material + pydantic-settings + Loom + Taskfile. Several items are defensible on their own merit but have no live consumer:

- **OpenLineage** — implemented, sensor ships disabled, no Marquez / DataHub on the other end. Today's effect: zero. Future effect: portability hedge if the stack moves into an org with a catalog. Net: ~50 LOC + one env var + one `lineage` extra. The recent post-mortem (today's conversation) concluded "no real harm in keeping it" — that's a keep decision, but it should live in an ADR so a reviewer doesn't have to infer it.
- **`freshness_violation_sensor`** — custom sensor emitting a structured log line per asset-check failure. Ships disabled. No alerting transport wired. Dagster's built-in freshness UI already shows the same thing. Is this worth the 40 LOC or should it be deleted in favor of the built-in?
- ~~**Dive preview / `scripts/render_cost_page.py` / `analytics.mart_cost_summary`**~~ — cost observability surface removed 2026-04-22. Operator runs on MotherDuck free tier; the chart was reporting phantom dollars. See `ticket:cost-rate-dynamic` closure.
- **`app/main.py` Streamlit explorer** — runnable via `task streamlit`, but the deployed consumer story is MotherDuck Dive, not Streamlit. Two consumer surfaces, unclear canonical. (Covered in ticket:dual-consumer-surface — keep cross-reference, don't duplicate.)
- **`openlineage-python` as root dev dep** instead of package-level optional extra — currently in `[dependency-groups].dev` which pulls it into every `uv sync`. The sensor-module's import is guarded, so the runtime cost is zero, but a fresh install pulls the dep regardless. Could be moved to `packages/databox/pyproject.toml`'s `lineage` extra and referenced in CI via `uv sync --extra lineage`.

Each item has a defensible keep answer. The problem is the absence of an explicit record.

# In Scope

- New ADR: `docs/adr/0007-tooling-scope.md` — for each of the above items, one paragraph explaining: *what it does, why it's here, what it costs, what would remove it, what the decision is today.*
- Act on the decisions:
  - Move `openlineage-python` out of the root dev dep and into `packages/databox/pyproject.toml`'s `lineage` optional extra. Update CI to install that extra only on the test job that exercises `test_openlineage_sensor.py`.
  - Evaluate `freshness_violation_sensor`: if keeping, add a concrete Slack/email transport hook example to `docs/freshness.md` so it's not a half-finished feature. If removing, delete the sensor and rely on Dagster's built-in freshness UI.
  - Evaluate `.dive-preview/` — if it's dev scaffolding, gitignore it (check `.gitignore` — may already be ignored); if it's user-facing, document its purpose.
- Update README's "Stack" section to match the ADR's decisions

# Out of Scope

- Removing Dagster, SQLMesh, Soda, or MotherDuck (those are load-bearing, not trim targets)
- Rewriting the OpenLineage sensor (the implementation is fine; only the *framing* is the question)
- Consumer-surface consolidation (that's ticket:dual-consumer-surface)

# Acceptance Criteria

- `docs/adr/0007-tooling-scope.md` exists, linked from `docs/adr/README.md`
- `openlineage-python` is no longer in root `[dependency-groups].dev`; it's a package-level optional extra
- CI's `test_openlineage_sensor.py` run installs the `lineage` extra explicitly
- `freshness_violation_sensor` is either (a) kept with a concrete wiring example in `docs/freshness.md`, or (b) deleted
- README's Stack section reflects the ADR's decisions (no enterprise-sounding claims that aren't implemented or have been explicitly kept)

# Approach Notes

- The ADR framing matters: this is a "what we decided NOT to delete, and why" record. That framing signals self-awareness about stack scale; it's the opposite of cargo-culting.
- Keep is a valid outcome for every item — the value is the explicit record, not the deletion count.

# Evidence Expectations

- Merged ADR-0007
- PR moving openlineage to optional extra, with CI passing
- Final state of freshness_violation_sensor decision visible in the commit history
