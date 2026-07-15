"""Canonical domain builder contracts; all checks are construction-only and offline."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from databox.config.sources import SOURCES


@pytest.mark.parametrize("source", SOURCES, ids=lambda source: source.name)
def test_builder_is_callable_singular_and_matches_registered_resources(source) -> None:
    module = importlib.import_module(source.domain_module)
    builder = vars(module)["_build_source"]
    assert callable(builder)
    built = builder()
    assert set(built.resources) == set(source.raw_tables)


def test_avonet_builder_owns_source_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    from databox.orchestration.domains import avonet

    sentinel = object()
    factory = Mock(return_value=sentinel)
    monkeypatch.setattr(avonet, "avonet_source", factory)
    assert avonet._build_source() is sentinel
    factory.assert_called_once_with()


def test_ebird_builder_owns_production_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from databox.orchestration.domains import ebird

    sentinel = object()
    factory = Mock(return_value=sentinel)
    monkeypatch.setattr(ebird, "ebird_source", factory)
    monkeypatch.setattr(ebird, "settings", SimpleNamespace(days_back=lambda name: 17))
    assert ebird._build_source() is sentinel
    factory.assert_called_once_with(region_code="US-AZ", max_results=10000, days_back=17)


def test_gbif_builder_owns_production_defaults_and_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    from databox.orchestration.domains import gbif

    sentinel = object()
    factory = Mock(return_value=sentinel)
    monkeypatch.setattr(gbif, "gbif_source", factory)
    assert gbif._build_source() is sentinel
    factory.assert_called_once_with(
        country_code="US",
        state_province="Arizona",
        taxon_key=212,
        max_records=1000,
        has_coordinate=True,
    )
    factory.reset_mock()
    assert gbif._build_source(max_records=2) is sentinel
    factory.assert_called_once_with(
        country_code="US",
        state_province="Arizona",
        taxon_key=212,
        max_records=2,
        has_coordinate=True,
    )


def test_noaa_builder_owns_production_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from databox.orchestration.domains import noaa

    sentinel = object()
    factory = Mock(return_value=sentinel)
    monkeypatch.setattr(noaa, "noaa_source", factory)
    monkeypatch.setattr(noaa, "settings", SimpleNamespace(days_back=lambda name: 23))
    assert noaa._build_source() is sentinel
    factory.assert_called_once_with(
        location_id="FIPS:04",
        dataset_id="GHCND",
        days_back=23,
        datatypes="TMAX,TMIN,PRCP,SNOW,AWND",
    )


def test_usgs_builder_owns_production_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from databox.orchestration.domains import usgs

    sentinel = object()
    factory = Mock(return_value=sentinel)
    monkeypatch.setattr(usgs, "usgs_source", factory)
    monkeypatch.setattr(usgs, "settings", SimpleNamespace(days_back=lambda name: 31))
    assert usgs._build_source() is sentinel
    factory.assert_called_once_with(
        state_cd="AZ",
        parameter_cds="00060,00065,00010",
        days_back=31,
    )


def test_usgs_earthquakes_builder_owns_source_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    from databox.orchestration.domains import usgs_earthquakes

    sentinel = object()
    factory = Mock(return_value=sentinel)
    monkeypatch.setattr(usgs_earthquakes, "usgs_earthquakes_source", factory)
    assert usgs_earthquakes._build_source() is sentinel
    factory.assert_called_once_with()


def test_xeno_canto_builder_owns_production_defaults_and_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from databox.orchestration.domains import xeno_canto

    sentinel = object()
    factory = Mock(return_value=sentinel)
    monkeypatch.setattr(xeno_canto, "xeno_canto_source", factory)
    assert xeno_canto._build_source() is sentinel
    factory.assert_called_once_with(
        query=xeno_canto.XENO_CANTO_DEFAULT_QUERY,
        max_records=1000,
        per_page=100,
    )
    factory.reset_mock()
    assert xeno_canto._build_source(max_records=2, per_page=2) is sentinel
    factory.assert_called_once_with(
        query=xeno_canto.XENO_CANTO_DEFAULT_QUERY,
        max_records=2,
        per_page=2,
    )
