---
id: ticket:dagster-deploy-live
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

A recruiter clicks one link in the README and sees a live Dagster UI running against real MotherDuck data, with schedules active and at least 30 days of successful materializations visible.

# Why

The README argues for a reliability-minded platform: schedules, sensors, freshness SLAs, cost observability, asset checks. Today, none of that is actually running anywhere a reviewer can verify. The docs site (`doctacon.github.io/databox`) renders cleanly, but it's static — no proof the orchestrator executes. A staff-level candidate who says "I built a data platform" without a running instance is not differentiable from one who pushed nicely formatted YAML to GitHub. One live deployment closes that gap completely.

# In Scope

- Pick one deploy target, in preference order:
  1. **Dagster Cloud Serverless** (free tier for a single location) — least ops, official Dagster product, credible
  2. **Fly.io** free-tier VM running `dagster-webserver` + `dagster-daemon` in one container
  3. **Render** free-tier web service (similar trade-offs to Fly)
  4. **A local always-on Mac Mini** — last resort, hard to prove to a cold reviewer
- Point the deployment at MotherDuck (`DATABOX_BACKEND=motherduck`) using a scoped MotherDuck token provisioned for the deploy only
- Confirm all schedules are enabled and fire at least once per day
- Add a README badge: "Live Dagster · {url}" near the existing CI/Docs/Python badges
- Document the deploy in `docs/deploy.md`: target chosen, why, secret-management story, teardown cost, how to rotate the MotherDuck token
- Set up a basic uptime ping (UptimeRobot free tier → emails on failure); link the public status page from `docs/deploy.md`

# Out of Scope

- Multi-environment deploys (one prod deploy is the whole story)
- Kubernetes / ECS / Docker Compose production-grade orchestration — the platform is explicitly zero-infra-default; the deploy should preserve that ethos
- Any custom UI beyond what Dagster ships
- Running the Streamlit app in the same deployment (separate consumer surface; decide in ticket:dual-consumer-surface)

# Acceptance Criteria

- One URL in the README that opens a Dagster UI with the actual `all_pipelines` job visible
- At least one scheduled run has executed successfully against MotherDuck within the last 24 hours, viewable in the UI
- `docs/deploy.md` exists and explains: hosting provider, monthly cost ($0 target), secret rotation, teardown
- UptimeRobot (or equivalent) public status page linked from `docs/deploy.md`
- If the deploy is Dagster Cloud: confirm the "guest" access mode or public deployment setting is on, so reviewers don't hit an auth wall

# Approach Notes

- **Security gate before starting**: provision a *new* MotherDuck token scoped to only the databases this stack uses; do not reuse the local dev token. Put it behind the deploy platform's secret store, not in a committed file.
- Dagster Cloud Serverless is the lowest-friction choice; it supports public deployments with an unlisted URL that's fine for portfolio purposes. Confirm the free tier covers this use case at the time of work (rules change).
- Fly.io alternative: single `fly.toml`, one process running `dagster dev -h 0.0.0.0` behind their TLS edge. Downside: `dagster dev` isn't meant for prod; use `dagster-webserver` + `dagster-daemon` as separate processes.
- The schedules are already defined in `packages/databox/databox/orchestration/definitions.py` — they'll fire automatically once the daemon is running.
- Add a small "live" section to the README near Quickstart, positioned above the `task install` block so a drive-by reader clicks the live URL before reading installation docs.

# Evidence Expectations

- Public URL pasted in the ticket close notes
- Screenshot of Dagster UI showing `all_pipelines` and at least one green run
- `docs/deploy.md` linked from the README
- Monthly cost receipt (or confirmation the provider charged $0) at 30-day mark
