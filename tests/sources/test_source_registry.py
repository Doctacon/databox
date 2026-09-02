"""Bidirectional coherence between the source registry and domain modules.

The registry at `databox.config.sources.SOURCES` is the single declaration of
every active source. Every registered source must have a matching domain
module, and every orchestration domain module (minus `analytics`) must have a
registry entry. Explicit-target sources expose only manually launched, modeled-target Dagster
workflows and remain excluded from schedules and shared refresh.
"""

from __future__ import annotations

import importlib
import pkgutil

import dagster as dg
import pytest
from databox.config.settings import settings
from databox.config.sources import SOURCES
from databox.quality.platform_health_codegen import render as render_platform_health

EXPECTED_DOMAIN_EXPORTS = (
    "assets",
    "dlt_asset_keys",
    "sqlmesh_asset_keys",
    "ingest_job",
    "_build_source",
)
EXPECTED_SOURCES = {
    "avonet",
    "ebird",
    "gbif",
    "noaa",
    "usgs",
    "usgs_earthquakes",
    "usfws",
    "xeno_canto",
}


@pytest.mark.parametrize("source", SOURCES, ids=lambda source: source.name)
def test_every_registered_source_has_a_domain_module(source) -> None:
    source_name = source.name
    module = importlib.import_module(f"databox.orchestration.domains.{source_name}")
    for attr in EXPECTED_DOMAIN_EXPORTS:
        assert hasattr(module, attr), f"{source_name}.py missing `{attr}`"
    if source.orchestration_mode == "explicit_targets":
        assert module.assets
        assert module.dlt_asset_keys
        assert module.ingest_job.name == f"{source_name}_ingest"
        assert hasattr(module, f"{source_name}_dlt_assets")
    else:
        assert hasattr(module, f"{source_name}_dlt_assets"), (
            f"{source_name}.py must export `{source_name}_dlt_assets` "
            "for smoke + definitions wiring"
        )
    assert hasattr(module, "daily_pipeline") is source.scheduled
    assert hasattr(module, "schedule") is source.scheduled


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


def test_source_names_unique_and_complete() -> None:
    names = [s.name for s in SOURCES]
    assert len(names) == len(set(names)), f"duplicate source names in registry: {names}"
    assert set(names) == EXPECTED_SOURCES


def test_domain_identity_and_verification_profiles() -> None:
    for source in SOURCES:
        assert source.domain_module == f"databox.orchestration.domains.{source.name}"
        expected = "file_snapshot" if source.name == "avonet" else "http"
        assert source.verification_profile == expected


def test_source_complete_raw_table_inventory() -> None:
    sources = {source.name: source for source in SOURCES}
    assert sources["ebird"].raw_tables == (
        "recent_observations",
        "notable_observations",
        "hotspots",
        "species_list",
        "taxonomy",
        "region_stats",
    )
    assert sources["noaa"].raw_tables == ("daily_weather", "stations", "datasets")


def test_raw_catalogs_match_name() -> None:
    for src in SOURCES:
        assert src.raw_catalog == f"raw_{src.name}"


def test_raw_dataset_matches_source_schema() -> None:
    assert settings.raw_dataset_name("usgs") == "raw_usgs"


def test_every_raw_catalog_uses_single_local_database() -> None:
    assert {settings.raw_catalog_path(src.name) for src in SOURCES} == {settings.database_path}


def test_nonrecurring_sources_are_not_scheduled_or_parallel() -> None:
    nonrecurring = {source.name: source for source in SOURCES if source.name in {"avonet", "usfws"}}
    assert set(nonrecurring) == {"avonet", "usfws"}
    assert all(source.scheduled is False for source in nonrecurring.values())
    assert all(source.parallel_refresh is False for source in nonrecurring.values())


def test_explicit_target_source_is_declared_manual_and_unscheduled() -> None:
    explicit = {
        source.name: source for source in SOURCES if source.orchestration_mode == "explicit_targets"
    }
    assert set(explicit) == {"usfws"}
    assert all(source.scheduled is False for source in explicit.values())
    assert all(source.parallel_refresh is False for source in explicit.values())
    assert all(source.iceberg_authoritative is True for source in explicit.values())
    module = importlib.import_module(explicit["usfws"].domain_module)
    assert module.ingest_job.name == "usfws_ingest"
    assert not hasattr(module, "daily_pipeline")
    assert not hasattr(module, "schedule")
    assert {
        "sqlmesh/raw_usfws/image_search_runs",
        "sqlmesh/raw_usfws/image_records",
        "sqlmesh/raw_usfws/_dlt_load_status",
    } == {key.to_user_string() for key in module.dlt_asset_keys}
    platform_health = render_platform_health()
    assert "polaris_aws.raw_usfws._dlt_load_status" in platform_health


def test_platform_health_load_status_dependencies_are_materializable_assets() -> None:
    from databox.orchestration.definitions import defs

    graph = defs.resolve_asset_graph()
    platform_health = graph.get(dg.AssetKey(["sqlmesh", "analytics", "platform_health"]))
    status_parents = {
        parent.key.to_user_string()
        for parent in graph.get_parents(platform_health)
        if parent.key.path[-1] == "_dlt_load_status"
    }
    expected = {f"sqlmesh/raw_{source.name}/_dlt_load_status" for source in SOURCES}
    assert status_parents == expected
    assert all(graph.get(dg.AssetKey.from_user_string(key)).is_materializable for key in expected)


def test_analytics_anchor_is_single() -> None:
    anchors = [s for s in SOURCES if s.analytics_anchor]
    assert len(anchors) <= 1, (
        f"at most one source may be analytics_anchor=True; got {[s.name for s in anchors]}"
    )
