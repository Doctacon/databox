---
id: ticket:observability-pass
kind: ticket
status: closed
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-21T19:20:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 1
---

# Goal

Make the platform observable past "did Dagster turn green." Every asset has a declared freshness policy, structured logs flow through every source, and key pipeline health metrics are queryable from the warehouse itself.

# Why

Staff-level signal: treating the pipeline as a product with SLAs, not a cron job. Dagster already supports this; the repo does not use it. Recruiters reviewing Dagster UI screenshots will immediately notice freshness policies and asset checks — or their absence.

# In Scope

- Declare `FreshnessPolicy` on every SQLMesh-backed asset and every dlt source asset in `databox-orchestration`
- Declare `AutoMaterializePolicy` (or `AutomationCondition` in newer Dagster) where sensible
- Add `AssetCheckSpec` wrappers around existing Soda contracts so their results surface in the Asset Checks UI (may already exist — verify and close the gap)
- Replace `print` / naked `logging.info` in sources with structured logs via `structlog` or `logging` with JSON formatter
- Standard log fields: `pipeline`, `source`, `resource`, `load_id`, `duration_ms`, `rows`
- A `platform_health` SQLMesh view (or raw DuckDB view) over `dlt` system tables exposing per-run row counts, durations, failure flags
- A Dagster sensor or scheduled asset that alerts on freshness-policy violations (console log sufficient for single-operator; structured failure event captured)

# Out of Scope

- External alerting (PagerDuty/Slack/email) — log-level surface is enough
- OpenTelemetry/Prometheus export — deferred
- Replacing Dagster's built-in run storage with an external backend
- Cost tracking (separate, deferred initiative)

# Acceptance Criteria

- Every asset in `packages/databox-orchestration/databox_orchestration/definitions.py` has a `FreshnessPolicy` matching its source cadence
- Every Soda contract has a visible `AssetCheck` in the Dagster UI
- `sources/*/source.py` emit structured logs with the standard fields above
- `platform_health` view exists and answers: "what ran in the last 24h, how long did it take, did it succeed?"
- README screenshot shows the Asset Checks panel with green checks

# Approach Notes

- Freshness cadences: eBird recent observations — daily; NOAA CDO — daily with several-day lag tolerance; USGS — daily
- Use dlt's `pipeline.last_trace` to populate the health view after each load
- Don't invent a custom log schema — map to OpenTelemetry semantic conventions where possible so later OTel export is cheap

# Evidence Expectations

- Dagster UI screenshots: asset graph with freshness chips, asset checks panel
- Sample structured log line per source
- `SELECT * FROM platform_health ORDER BY started_at DESC LIMIT 5;` output
