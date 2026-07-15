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

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

import dagster as dg

VerificationProfile = Literal["http", "file_snapshot"]

SOURCE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")

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
        by cross-domain CDM/analytics SQLMesh assets (the slowest upstream wins).
      scheduled: whether the source has a recurring daily pipeline and schedule.
      parallel_refresh: whether the source participates in the shared full refresh.
      verification_profile: profile enforced by the registry-derived source test contract.
    """

    name: str
    raw_tables: tuple[str, ...]
    freshness_policy: dg.FreshnessPolicy = _DEFAULT_FRESHNESS
    analytics_anchor: bool = False
    scheduled: bool = True
    parallel_refresh: bool = True
    verification_profile: VerificationProfile = "http"

    @property
    def raw_catalog(self) -> str:
        return f"raw_{self.name}"

    @property
    def domain_module(self) -> str:
        return f"databox.orchestration.domains.{self.name}"


SOURCES: list[Source] = [
    Source(
        name="ebird",
        raw_tables=(
            "recent_observations",
            "notable_observations",
            "hotspots",
            "species_list",
            "taxonomy",
            "region_stats",
        ),
    ),
    Source(name="gbif", raw_tables=("occurrences",)),
    Source(
        name="avonet",
        raw_tables=("species_traits",),
        scheduled=False,
        parallel_refresh=False,
        verification_profile="file_snapshot",
    ),
    Source(name="xeno_canto", raw_tables=("recordings",)),
    Source(
        name="noaa",
        raw_tables=("daily_weather", "stations", "datasets"),
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
