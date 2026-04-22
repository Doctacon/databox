---
id: ticket:loom-ledger-audit
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

Reconcile Loom ledger state so that `status:` fields across initiatives, plans, and tickets tell one coherent story: no `active` plan pointing at a `closed` initiative, no `active` initiative without at least one in-flight child ticket, no stale `active` records describing work that already landed.

# Why

A visitor browsing `.loom/` sees the project's operating process. Today:

- `initiative:scaffold-polish` is `closed`, but its plan `plan:scaffold-polish` is still `status: active`
- `initiative:staff-portfolio-readiness` is `active`, its plan is `active`, but all 34 children are `closed` — so the initiative is *effectively* closed and should either be closed or have new in-flight work attached
- `research:semantic-metrics-approach` is `active` — either it's still informing work (fine) or it's settled and should be marked `accepted` or superseded
- 35 tickets total, 34 `closed`, 1 `superseded` — the signal-to-noise of the tickets folder is low for someone trying to see *what is happening now*

Loom's own truth-and-authority rules say: "If two artifacts disagree, do not average them together. Find which layer is supposed to own that fact, then reconcile." The ledger is out of compliance with its own rule.

# In Scope

- Walk every record in `.loom/initiatives/`, `.loom/plans/`, `.loom/research/`, `.loom/specs/`, `.loom/critique/`, `.loom/wiki/` and confirm each `status:` field matches reality:
  - If closed → every child ticket is closed
  - If active → at least one child ticket is in `ready`, `active`, `blocked`, or `review_required`
  - If superseded → a newer record exists and is linked via `supersedes:` / superseding ticket's frontmatter
- Reconcile `plan:scaffold-polish`: either close it (initiative is closed) or document why it outlives the initiative
- Decide the state of `initiative:staff-portfolio-readiness`: if the Phase 5 cleanup tickets count as its continuation, leave it `active` and note Phase 5 in the plan; if Phase 5 should live under a new `initiative:hardening-pass`, create that initiative and reassign the five cleanup tickets to it
- Audit `research:semantic-metrics-approach`: mark `accepted` if its recommendations are live, or `superseded` if a later record replaces it
- Add a Loom-state validator script: `scripts/check_loom_state.py` (or extend an existing one) that enforces these cross-layer invariants and fails CI if they drift. Run nightly or on every PR that touches `.loom/**`.
- Document the reconciliation as a single commit: `chore(loom): reconcile ledger state across initiatives, plans, tickets`

# Out of Scope

- Rewriting old tickets' bodies (close notes stand as the historical record)
- Migrating to a different ledger system
- Consolidating the 35 tickets into a smaller set — they are fine as individual records; the problem is the state fields, not the volume
- Hiding `.loom/` from the root listing (it is visible and that is correct — it is part of the project's operating process)

# Acceptance Criteria

- `rg -rn '^status: active' .loom/initiatives .loom/plans` corresponds exactly to work in-flight (verifiable by listing open ticket children)
- `rg -rn '^status:' .loom/tickets` distribution shows at minimum one `ready` or `active` ticket per active plan
- `scripts/check_loom_state.py --check` runs in CI on PRs that touch `.loom/**`, passes on main
- `plan:scaffold-polish` is `closed` (or explicitly superseded with a reason)
- `research:semantic-metrics-approach` has an explicit terminal state
- A single commit encapsulates the reconciliation, with a summary in the commit body of which records flipped state and why

# Approach Notes

- Do the walk manually once — scripting discovery before the first reconciliation would create the script against a broken baseline
- The validator script should not be harder than 100 lines; parsing frontmatter with `yaml.safe_load` after the `awk` fence filter is the standard pattern (see `/Users/crlough/.claude/rules/loom/06-filesystem-and-tooling.md`)
- CI integration: add as a new job in `.github/workflows/ci.yaml` gated on the existing `ci_config` + a new `.loom/**` path filter; cheap, always-on

# Evidence Expectations

- Commit hash of the reconciliation
- Output of `scripts/check_loom_state.py --check` run in CI showing green
- Before/after snapshot of `.loom/` status distribution in the commit body
