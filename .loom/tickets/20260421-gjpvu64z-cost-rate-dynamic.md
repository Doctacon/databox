---
id: ticket:cost-rate-dynamic
kind: ticket
status: closed
created_at: 2026-04-21T21:00:00Z
updated_at: 2026-04-22T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 5
depends_on: []
---

# Goal

Make the MotherDuck compute-cost rate a first-class configuration value with a staleness signal, instead of a hardcoded magic number that a future maintainer will silently outlive.

# Why

`packages/databox/databox/orchestration/domains/analytics.py:59`:

```python
MOTHERDUCK_COST_PER_COMPUTE_SECOND = 0.25 / 3600  # $0.25/hour
```

Comment says "Forkers must update when MotherDuck's published per-compute-second price changes — no pricing API." That note is correct — but the enforcement is a human reading source code. Rates go out of date quietly. The cost chart on `docs/cost.md` silently diverges from reality. A staff-level reviewer reads this and asks: "how does this code know when it's lying?"

# In Scope

- Move the rate out of `analytics.py` into a structured config record. Options, in order of preference:
  1. `packages/databox/databox/config/cost_rates.py` — a dataclass with `provider`, `plan`, `usd_per_compute_second`, `effective_from: date`, `last_verified: date`, `source_url`. One entry per provider/plan combo.
  2. A YAML file under `packages/databox/databox/config/` if Python-object lifecycle matters less than human editability. (Probably (1) — Python stays.)
- Add a Soda-style assertion (or a plain Dagster asset check) that fails when `today - last_verified > 90 days`. Warning, not error — the stack still works, it just loudly reminds the operator.
- Update `docs/cost.md`:
  - Display the `last_verified` date visibly
  - Add a small "how to update" paragraph with a pointer to MotherDuck's pricing page
- The `mart_cost_summary` asset reads the rate from the new config, not from a module-level constant

# Out of Scope

- Pulling the rate from a live pricing API (MotherDuck does not publish one; this is the whole reason the constant is hardcoded today)
- Supporting arbitrary cloud providers — this is one stack, one provider, one plan
- Retroactively backfilling `last_verified` for historical rate changes — only the current effective rate needs the field

# Acceptance Criteria

- `rg -n 'COST_PER_COMPUTE_SECOND' packages/` returns only references to the new config module (not magic numbers scattered in business logic)
- `docs/cost.md` renders with the `last_verified` date visible
- An asset check or scheduled sensor emits a warning when `last_verified` is older than 90 days
- `task ci` includes a unit test asserting the stale-rate warning fires (time-travelled input)

# Approach Notes

- Keep the config dataclass immutable (`@dataclass(frozen=True)`) — rate changes should produce a new entry, not mutate an existing one
- A future 2nd rate tier (e.g. a "Standard" vs "Business" plan) is a straight append, not a refactor
- The warning mechanism: simplest is a pure asset check on `mart_cost_summary` that reads the rate record's `last_verified` and emits `AssetCheckResult(passed=..., severity=WARN, description=...)`. Do not spin up a separate sensor.

# Evidence Expectations

- Commit moving the rate into the config module
- CI run showing the stale-rate test passing
- Rendered `docs/cost.md` showing the visible "rate verified on YYYY-MM-DD" line

# Closure — 2026-04-22

Closed without implementation. Operator confirmed this workspace runs on MotherDuck's free tier, where no per-compute-second charge applies. The `motherduck_cost_usd` column in `mart_cost_summary` is therefore always $0 or meaningless regardless of the hardcoded rate, and the staleness-warning machinery this ticket would introduce would be tracking a number that does not bill the operator.

Premise of the ticket (rate must stay truthful for the cost chart to be useful) no longer holds for the actual deployment. Implementing it would add a dataclass, asset check, and doc scaffolding to support a warning about a number nobody pays.

Follow-up question still open: whether the `mart_cost_summary` asset itself should be removed or explicitly relabeled as free-tier. Tracked separately — this ticket closes rather than morphing into a different scope.
