Status: done
Created: 2026-09-02
Updated: 2026-09-02
Parent: None
Depends-On: None

# Connect load-status lineage

## Scope

Represent every registry-managed `_dlt_load_status` Iceberg table as a truthful Dagster asset/materialization so `analytics.platform_health` has complete visible upstream lineage. Reuse existing publication behavior and preserve source schedules, shared-refresh sequencing, provider semantics, and SQLMesh centralization.

## Acceptance criteria

- AVONET, eBird, GBIF, NOAA, USGS, USGS Earthquakes, Xeno-canto, and USFWS load-status keys resolve to declared Dagster assets.
- Routine source runs materialize their status asset only after status publication succeeds and attach useful load/run metadata where available.
- `analytics.platform_health` resolves dependencies to all eight declared status assets.
- Shared ingest jobs remain dlt-only and SQLMesh still runs once centrally after authoritative inspection.
- Focused lineage, registry, source, and parallel-refresh tests pass.

## Explicit exclusions

- Provider-query, raw-schema, scheduling, licensing, target, SQLMesh-model, or public deployment changes.
- A live source refresh.

## References

- `.10x/specs/canonical-dlt-source-registry.md`
- `.10x/specs/superseded/usfws-manual-media-discovery.md`
- `transforms/main/models/analytics/platform_health.sql`

## Evidence expectations

Record resolved dependency keys, focused tests, static checks, review findings, and residual limitations.

## Progress and notes

- 2026-09-02: Opened from user-authorized merge-preparation scope.
- 2026-09-02: Added a shared Dagster load-status asset factory and made publication return materialization metadata. All seven routine sources now publish status in a downstream ingestion asset, include it in ingest jobs, and sequence targeted SQLMesh refreshes after it. USFWS retains its manual modeled-target asset. The resolved graph contains eight materializable status parents for `analytics.platform_health`; focused tests passed (35), as did Ruff and diff checks.
- 2026-09-02: Closure gate passed after adversarial review and documentation repair. Parent rerun: 39 focused tests, Ruff, format, and diff checks passed. Evidence: `.10x/evidence/2026-09-02-load-status-lineage-and-manual-usfws.md`; review: `.10x/reviews/2026-09-02-load-status-refresh-usfws-closure-review.md`. No new reusable procedure or unresolved follow-up was identified.

## Blockers

None.
