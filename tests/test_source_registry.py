"""Bidirectional coherence between the source registry and domain modules.

The registry at `databox.config.sources.SOURCES` is the single declaration of
every active source. Every registered source must have a matching domain
module that exports `dlt_asset_keys`, `sqlmesh_asset_keys`, `daily_pipeline`,
and `schedule` — and every orchestration domain module (minus `analytics`)
must have a registry entry. This test fails the build when one side drifts.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest
from databox.config.sources import SOURCES

EXPECTED_DOMAIN_EXPORTS = (
    "dlt_asset_keys",
    "sqlmesh_asset_keys",
    "daily_pipeline",
    "schedule",
)


@pytest.mark.parametrize("source_name", [s.name for s in SOURCES])
def test_every_registered_source_has_a_domain_module(source_name: str) -> None:
    module = importlib.import_module(f"databox.orchestration.domains.{source_name}")
    for attr in EXPECTED_DOMAIN_EXPORTS:
        assert hasattr(module, attr), f"{source_name}.py missing `{attr}`"
    assert hasattr(module, f"{source_name}_dlt_assets"), (
        f"{source_name}.py must export `{source_name}_dlt_assets` for smoke + definitions wiring"
    )


def test_every_domain_module_is_registered() -> None:
    import databox.orchestration.domains as domains_pkg

    found: set[str] = set()
    for info in pkgutil.iter_modules(domains_pkg.__path__):
        if info.name.startswith("_") or info.name == "analytics":
            continue
        found.add(info.name)

    registered = {src.name for src in SOURCES}
    missing_in_registry = found - registered
    missing_on_disk = registered - found
    assert not missing_in_registry, f"domain modules not in SOURCES: {sorted(missing_in_registry)}"
    assert not missing_on_disk, (
        f"SOURCES entries without a domain module: {sorted(missing_on_disk)}"
    )


def test_source_names_unique() -> None:
    names = [s.name for s in SOURCES]
    assert len(names) == len(set(names)), f"duplicate source names in registry: {names}"


def test_raw_catalogs_match_name() -> None:
    for src in SOURCES:
        assert src.raw_catalog == f"raw_{src.name}"


def test_analytics_anchor_is_single() -> None:
    anchors = [s for s in SOURCES if s.analytics_anchor]
    assert len(anchors) <= 1, (
        f"at most one source may be analytics_anchor=True; got {[s.name for s in anchors]}"
    )
