Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: commit a70af1c and .10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md
Verdict: fail

# Map, wheel, and refresh architecture review

## Findings

- **Significant:** `packages/databox/databox/source_refresh_api.py` and `app/src/sourceRefreshApi.ts` duplicate the canonical routine-source registry in `packages/databox/databox/config/sources.py`; the launched command dynamically derives scope, so execution, status, and browser validation can drift.
- **Significant:** refresh status models only a source-name list and aggregate phase, not required per-source progress or source-attributed failure. Existing focused tests do not cover the complete lifecycle.
- **Significant:** aggregate evidence predates final hardening for the full Python run and does not record all required Soda/docs/hooks/fake-lifecycle gates.

Map GET ownership, catalog-media reuse, one-Quack orchestration ownership, and current AVONET exclusion were architecturally sound.

## Verdict

Fail. Code findings are owned by `.10x/tickets/done/2026-07-12-repair-map-wheel-refresh-review-findings.md`; final aggregate evidence remains owned by `.10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md`.

## Residual risk

No live refresh, physical browser, or assistive-technology run was performed. The in-process lock assumes the documented single-worker app. PID-liveness-only recovery is unsafe until repaired.

## Evidence inspected

Governing records; commit `a70af1c`; refresh registry/API/orchestrator/frontend; map API/media path; focused refresh tests (11 passed with coverage disabled). The reviewer made no repository changes and ran no live workflow.
