# Freshness SLAs

Every mart asset declares a staleness tolerance. If a mart's latest
materialization is older than its SLA, its freshness check fails and the
`freshness_violation_sensor` logs a structured warning line one tick later
(sensor default interval: 300s).

## Declared SLAs

| Asset | Max staleness | Reason |
|-------|---------------|--------|
| `sqlmesh/ebird/fct_daily_bird_observations` | 30 hours | Daily ingest at 06:00; 30h gives one day + 6h headroom. |
| `sqlmesh/ebird/dim_species` | 7 days | Taxonomy refreshes rarely; weekly cadence is fine. |
| `sqlmesh/ebird/fct_hotspot_species_diversity` | 30 hours | Derived from daily observation feed. |
| `sqlmesh/noaa/fct_daily_weather` | 48 hours | NOAA GHCND lags ~24h; 48h absorbs common delays. |
| `sqlmesh/usgs/fct_daily_streamflow` | 30 hours | USGS NWIS is near-real-time; 30h flags true stalls. |
| `sqlmesh/analytics/fct_species_environment_daily` | 48 hours | Cross-domain mart inherits NOAA's slower cadence. |
| `sqlmesh/analytics/platform_health` | 2 hours | Self-reporting health view; should be near-live. |

## Two complementary mechanisms

Databox uses both declarative policy **and** runtime validation:

1. **`FreshnessPolicy` (declarative)** — `apply_freshness` tags each
   source-derived spec with a cron-based expectation so Dagster's UI
   can signal "overdue" even without runs. Configured in
   `_factories.py:FRESHNESS_BY_SOURCE`.
2. **`build_last_update_freshness_checks` (runtime)** — per-asset
   `AssetCheck` that compares the latest materialization timestamp to
   a `timedelta`. Wired via `freshness_checks(SLAS)` inside each
   domain file.

The check is what actually fails and emits an asset-check evaluation
event; the policy is what tells operators the expected cadence up front.

## Violation sensor

`freshness_violation_sensor` scans `ASSET_CHECK_EVALUATION` events since
the last tick and logs one warning line per failure:

```
freshness_violation asset=["sqlmesh","noaa","fct_daily_weather"] check=... timestamp=...
```

Ships disabled (`DefaultSensorStatus.STOPPED`) so a fresh checkout does
not spam an operator who has not picked an alert channel. Enable in the
Dagster UI once you have wired the log line to Slack / Email /
PagerDuty. The sensor owns the transport — the log is the contract.

### Wiring to an alert channel

Pick one:

- **Slack** — filter Dagster logs where message starts with
  `freshness_violation`; post into `#data-alerts`.
- **Email** — same filter via your log-to-email forwarder.
- **PagerDuty** — only for SLAs short enough to be genuinely urgent
  (e.g., `platform_health` at 2h). Most forkers will not need this.

## Overriding per fork

Every SLA lives in a per-domain `FRESHNESS_SLAS` dict
(`packages/databox/databox/orchestration/domains/<source>.py`). Edit the
`timedelta` or remove the entry to relax / tighten a check; no
cross-cutting config needed.

To add a new mart:

```python
FRESHNESS_SLAS: dict[dg.AssetKey, timedelta] = {
    ...,
    dg.AssetKey(["sqlmesh", "<schema>", "<table>"]): timedelta(hours=24),
}
```

`freshness_checks(FRESHNESS_SLAS)` in `asset_checks` picks it up
automatically.

## Why not one global SLA

Source cadence varies by orders of magnitude. A global `24h` would
either false-alarm on NOAA (which legitimately lags) or miss
`platform_health` stalls (which should fire in minutes). Per-asset
SLAs keep the signal honest.
