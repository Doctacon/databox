---
id: ticket:dual-consumer-surface
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

Pick one canonical consumer surface for the flagship mart, document that decision, and make the other surface either obviously supplementary or delete it.

# Why

Today the repo ships two consumer surfaces for `analytics.fct_species_environment_daily`:

1. `app/main.py` — a Streamlit data explorer, wired into `task streamlit`, documented in `docs/analytics-examples.md`
2. MotherDuck **Dive** dashboards — referenced in the README system-architecture diagram (`dashboard["MotherDuck Dive dashboards"]`) and in `docs/` references, with preview scaffolding under `.dive-preview/`

A reviewer asks: *"which one is the actual demo?"* Neither is obviously canonical. Streamlit is runnable locally but has no deployed URL; Dive is proprietary MotherDuck tooling which conflicts with the CLAUDE.md open-source-first principle unless explicitly justified. The global `personal/CLAUDE.md` says:

> **ALWAYS choose Open Source over Proprietary/Managed Solutions.**
> Any SaaS with closed source → ❌

Dive is closed-source. Its use needs either an explicit carve-out ADR or removal.

# In Scope

- Decide between:
  - **Option A — Streamlit wins.** Delete Dive references, delete `.dive-preview/`, update the README architecture diagram to show Streamlit as the sole consumer. Deploy the Streamlit app alongside the Dagster deploy (see ticket:dagster-deploy-live). Canonical URL in the README.
  - **Option B — Dive wins.** Delete `app/main.py`, delete `task streamlit`, delete `docs/analytics-examples.md`'s Streamlit section. Write a carve-out ADR (`docs/adr/0008-dive-dashboards.md`) explaining why the open-source-first principle is overridden here (argument: MotherDuck is already the chosen cloud path, Dive is its native viz, reimplementing it in open-source would require a separate deploy that dilutes the portfolio message). Add a live Dive URL to the README.
  - **Option C — Both, explicitly tiered.** Streamlit is the local-dev explorer; Dive is the deployed demo. The ADR documents both roles. README architecture diagram shows both with a clear "local vs deployed" caption.
- Whichever option wins, the README's architecture diagram is updated to match exactly.
- If Option B or C: ADR documents the open-source-first override.
- If Option A or C: Streamlit is deployed (Fly.io / Render / Streamlit Community Cloud free tier) with a public URL.

# Out of Scope

- Building a third consumer surface (Superset, Grafana, etc.)
- Rewriting the Streamlit app for production polish beyond auth/config basics needed to deploy it
- Rebuilding Dive dashboards from scratch (they live in MotherDuck's web UI; they're not in-repo)

# Acceptance Criteria

- One ADR under `docs/adr/` records the consumer-surface decision (Option A, B, or C)
- README architecture diagram matches the decision — no "both in the diagram, one in reality" drift
- If Streamlit is kept: public URL in the README
- If Dive is kept: public URL in the README, and the open-source-first override is explicitly justified in the ADR
- `rg -n 'dive\|streamlit' README.md docs/` post-PR returns only references consistent with the chosen option

# Approach Notes

- Staff-level interviewer will weigh the open-source-first vs "pick tools that match your deploy target" tradeoff — the ADR should show that awareness, not hide behind it
- Streamlit Community Cloud is free and deploys from GitHub — low-cost way to make Option A credible
- Option C is the safest middle ground; the risk is that it reads as "I couldn't decide." An honest ADR makes Option C defensible.
- Dive being proprietary doesn't automatically kill it for this context — MotherDuck is already the cloud backend, and forcing an open-source viz layer when the warehouse is already on a managed service is arguably worse (two different compromises). Own that tradeoff in the ADR.

# Evidence Expectations

- Merged ADR
- Diff updating the README architecture diagram
- Public URL for whichever surface is canonical
