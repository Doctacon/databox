Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: commit a70af1c and .10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md
Verdict: fail

# Map, wheel, and refresh correctness review

## Findings

- **Blocker:** existing evidence does not establish all final aggregate suites or an exact fake six-source API-to-one-Quack-to-SQLMesh lifecycle.
- **Significant:** POST publishes `running_sources` before a PID exists, so an immediate GET can falsely persist terminal failure.
- **Significant:** after app restart, a successfully completed detached child is treated as failed because only PID liveness survives.
- **Significant:** reload loses persistent failure detail and UI omits source/phase progress.
- **Significant:** preview layer order can overlay the authoritative selected Field Map style.
- **Minor:** explicit smooth wheel scrolling is not disabled for reduced motion.

Current source membership/orchestration ordering, map snapshot read-only cardinality, and one-active wheel preview were sound.

## Verdict

Fail. Code findings are owned by `.10x/tickets/done/2026-07-12-repair-map-wheel-refresh-review-findings.md`; aggregate evidence remains owned by the verification ticket.

## Residual risk

No live refresh, physical browser, real MapLibre rendering, process-restart integration, or assistive-technology run was performed.

## Evidence inspected

Governing records; commit `a70af1c`; refresh/map/wheel implementation and tests. Focused Python tests: 32 passed with coverage disabled. Focused frontend tests: 34 passed. No repository mutation or live workflow occurred.
