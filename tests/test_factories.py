"""Tests for the schema-driven fake data factory."""

from __future__ import annotations

import pytest
from factories import generate_resource_data, generate_row, generate_rows


class TestGenerateRow:
    @pytest.mark.unit
    def test_with_typed_columns(self):
        columns = {
            "howMany": {"data_type": "bigint"},
            "lat": {"data_type": "double"},
            "lng": {"data_type": "double"},
        }
        row = generate_row(columns=columns)
        assert isinstance(row["howMany"], int)
        assert isinstance(row["lat"], float | int)
        assert isinstance(row["lng"], float | int)

    @pytest.mark.unit
    def test_with_name_hints(self):
        row = generate_row(
            columns={"email": {"data_type": "text"}, "count": {"data_type": "bigint"}}
        )
        assert "@" in row["email"]
        assert isinstance(row["count"], int)

    @pytest.mark.unit
    def test_with_extra_fields(self):
        row = generate_row(extra_fields={"_loaded_at": "2025-01-01", "custom": "val"})
        assert row["_loaded_at"] == "2025-01-01"
        assert row["custom"] == "val"

    @pytest.mark.unit
    def test_empty_columns(self):
        row = generate_row()
        assert isinstance(row, dict)


class TestGenerateRows:
    @pytest.mark.unit
    def test_generates_n_rows(self):
        rows = generate_rows(n=25)
        assert len(rows) == 25

    @pytest.mark.unit
    def test_unique_key(self):
        rows = generate_rows(n=50, columns={"id": {"data_type": "text"}}, unique_key="id")
        ids = [r["id"] for r in rows]
        assert len(ids) == len(set(ids))

    @pytest.mark.unit
    def test_all_rows_have_same_keys(self):
        columns = {"name": {"data_type": "text"}, "score": {"data_type": "bigint"}}
        rows = generate_rows(n=10, columns=columns, extra_fields={"_loaded_at": "now"})
        keys = [frozenset(r.keys()) for r in rows]
        assert len(set(keys)) == 1


class TestGenerateResourceData:
    @pytest.mark.integration
    def test_generates_for_ebird_resource(self):
        from databox_sources.ebird.source import ebird_source

        src = ebird_source(region_code="US-AZ", max_results=10, days_back=1)
        resource = src.resources["recent_observations"]
        rows = generate_resource_data(resource, n=5)
        assert len(rows) == 5
        assert all("_loaded_at" in r for r in rows)

    @pytest.mark.integration
    def test_generates_for_hotspots_resource(self):
        from databox_sources.ebird.source import ebird_source

        src = ebird_source(region_code="US-AZ", max_results=10, days_back=1)
        resource = src.resources["hotspots"]
        rows = generate_resource_data(resource, n=3)
        assert len(rows) == 3
        for row in rows:
            assert isinstance(row["lat"], float)
            assert isinstance(row["lng"], float)
            assert isinstance(row["numSpeciesAllTime"], int)
