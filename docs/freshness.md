# Freshness SLAs

Dagster freshness now lives on asset specs via `FreshnessPolicy`; Databox no
longer builds separate freshness asset checks. The
`freshness_violation_sensor` still watches asset-check failures from Soda or
other checks, while Dagster's UI owns freshness-status display.

## Declared policy

Source-derived SQLMesh assets inherit freshness from
`databox.config.sources.SOURCES` through `_factories.freshness_policy_for_key`.
The cross-domain CDM schema `environmental_observations` inherits the analytics
anchor source policy. Today that anchor is NOAA because NOAA is the slowest
regular upstream source.

| Asset family | Policy source | Reason |
|---|---|---|
| `sqlmesh/raw_*/*` | matching source registry entry | Raw dlt assets follow their source cadence. |
| `sqlmesh/environmental_observations/*` | analytics anchor source | CDM facts/dimensions depend on multiple sources and should not claim freshness faster than the slowest anchor. |
| `sqlmesh/analytics/platform_health` | analytics anchor source | Operational model over standard parallel-refresh source load metadata; explicit static/bootstrap jobs are excluded. |

## Violation sensor

`freshness_violation_sensor` scans `ASSET_CHECK_EVALUATION` events since the
last tick and logs one warning line per failed check:

```text
freshness_violation asset=["sqlmesh","environmental_observations","fact_bird_observation"] check=... timestamp=...
```

Ships disabled (`DefaultSensorStatus.STOPPED`) so a fresh checkout does not spam
an operator who has not picked an alert channel. Enable in the Dagster UI once
you have wired the log line to Slack / Email / PagerDuty. The sensor owns the
transport — the log is the contract.

## Overriding per fork

Edit the `freshness_policy` on the relevant `Source(...)` in
`packages/databox/databox/config/sources.py`. Cross-domain CDM assets inherit
from the one source marked `analytics_anchor=True`.
