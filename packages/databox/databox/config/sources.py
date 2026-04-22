"""Declarative source registry — the one list every dataset-agnostic code path reads.

Adding a new source means adding one `Source(...)` entry to `SOURCES` below;
`_factories.FRESHNESS_BY_SOURCE`, `settings.sqlmesh_config()` catalog dicts,
`scripts/smoke.py`, and the generated `platform_health.sql` all derive from
this list. No other file should iterate a hardcoded tuple of source names.

The registry is static Python so it can be imported from anywhere — including
SQL codegen and Dagster definition time — without triggering an import of the
domain modules (domain modules may import the registry, not the other way).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import dagster as dg

_DEFAULT_FRESHNESS = dg.FreshnessPolicy.cron(
    deadline_cron="0 8 * * *", lower_bound_delta=timedelta(hours=24)
)


@dataclass(frozen=True)
class Source:
    """One dataset-agnostic source entry.

    Fields:
      name: lowercase snake_case identifier. Must match the domain module name
        (`databox.orchestration.domains.<name>`), the dlt source package
        (`databox_sources.<name>`), and the raw DuckDB catalog (`raw_<name>`).
      raw_tables: dlt-written tables this source populates, used by
        `platform_health.sql` codegen for per-source row counts. Order-stable.
      freshness_policy: Dagster FreshnessPolicy applied to every sqlmesh asset
        derived from this source (via `_factories.apply_freshness`).
      analytics_anchor: if True, this source's freshness policy is inherited
        by cross-domain `analytics.*` marts (the slowest upstream wins).
    """

    name: str
    raw_tables: tuple[str, ...]
    freshness_policy: dg.FreshnessPolicy = _DEFAULT_FRESHNESS
    analytics_anchor: bool = False

    @property
    def raw_catalog(self) -> str:
        return f"raw_{self.name}"


SOURCES: list[Source] = [
    Source(
        name="ebird",
        raw_tables=(
            "recent_observations",
            "notable_observations",
            "hotspots",
            "species_list",
        ),
    ),
    Source(
        name="noaa",
        raw_tables=("daily_weather", "stations"),
        analytics_anchor=True,
    ),
    Source(name="usgs", raw_tables=("daily_values", "sites")),
    Source(name="usgs_earthquakes", raw_tables=("events",)),
]


def by_name(name: str) -> Source | None:
    for src in SOURCES:
        if src.name == name:
            return src
    return None


def raw_catalogs() -> list[str]:
    return [src.raw_catalog for src in SOURCES]
