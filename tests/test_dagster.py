"""Tests for dynamic Dagster asset generation.

These tests verify the orchestration layer auto-generates correctly
from the pipeline registry, without needing Dagster installed at import time.
"""

from __future__ import annotations

import pytest


class TestDagsterAssetGeneration:
    """Test that definitions.py auto-generates assets from configs."""

    @pytest.mark.unit
    def test_module_loads_with_configs(self):
        """Verify the module can be imported and generates assets."""
        try:
            from databox_orchestration import definitions
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        assert hasattr(definitions, "defs")
        assert hasattr(definitions, "assets")
        assert len(definitions.assets) > 0

    @pytest.mark.unit
    def test_ebird_dlt_assets_exist(self):
        """Verify fine-grained eBird dlt assets are generated."""
        try:
            from databox_orchestration import definitions
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        all_keys = {spec.key for a in definitions.assets for spec in a.specs}
        ebird_resources = [
            "recent_observations",
            "notable_observations",
            "species_list",
            "hotspots",
            "taxonomy",
            "region_stats",
        ]
        for resource in ebird_resources:
            matching = [k for k in all_keys if resource in k.path[-1]]
            assert matching, f"No asset found for eBird resource '{resource}'"

    @pytest.mark.unit
    def test_noaa_dlt_assets_exist(self):
        """Verify fine-grained NOAA dlt assets are generated."""
        try:
            from databox_orchestration import definitions
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        all_keys = {spec.key for a in definitions.assets for spec in a.specs}
        noaa_resources = ["daily_weather", "stations", "datasets"]
        for resource in noaa_resources:
            matching = [k for k in all_keys if resource in k.path[-1]]
            assert matching, f"No asset found for NOAA resource '{resource}'"

    @pytest.mark.unit
    def test_transform_assets_for_configured_projects(self):
        try:
            from databox_orchestration import definitions
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        all_keys = {spec.key for a in definitions.assets for spec in a.specs}
        expected_sqlmesh_models = [
            ("sqlmesh", "ebird", "stg_ebird_observations"),
            ("sqlmesh", "ebird", "stg_ebird_taxonomy"),
            ("sqlmesh", "ebird", "stg_ebird_hotspots"),
            ("sqlmesh", "ebird", "int_ebird_enriched_observations"),
            ("sqlmesh", "ebird", "fct_daily_bird_observations"),
            ("sqlmesh", "noaa", "stg_noaa_daily_weather"),
            ("sqlmesh", "noaa", "stg_noaa_stations"),
            ("sqlmesh", "noaa", "fct_daily_weather"),
        ]
        import dagster as dg

        for parts in expected_sqlmesh_models:
            key = dg.AssetKey(list(parts))
            assert key in all_keys, f"Missing sqlmesh asset: {parts}"

    @pytest.mark.unit
    def test_jobs_created_per_pipeline(self):
        try:
            from databox_orchestration import definitions
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        from databox_sources.registry import get_registry

        registry = get_registry()
        job_names = {j.name for j in definitions.jobs}

        for name in registry:
            assert f"{name}_daily_pipeline" in job_names, f"Missing job for '{name}'"

    @pytest.mark.unit
    def test_schedules_for_enabled_pipelines(self):
        try:
            from databox_orchestration import definitions
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        from databox_sources.registry import get_registry

        registry = get_registry()
        schedule_names = set()
        for s in definitions.schedules:
            schedule_names.add(s.job.name)

        for name, source in registry.items():
            cfg = source.config
            if cfg.schedule.enabled:
                assert f"{name}_daily_pipeline" in schedule_names, (
                    f"Missing schedule for enabled pipeline '{name}'"
                )


class TestSqlmeshModelAsset:
    """Test the factory function for creating per-model sqlmesh assets."""

    @pytest.mark.unit
    def test_creates_asset_with_correct_key(self):
        try:
            import dagster as dg
            from databox_orchestration.definitions import create_sqlmesh_model_asset
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        asset = create_sqlmesh_model_asset("ebird.stg_ebird_observations", "ebird_staging", [])
        assert asset is not None
        assert asset.key == dg.AssetKey(["sqlmesh", "ebird", "stg_ebird_observations"])


class TestJobsAndSchedules:
    """Test jobs and schedules are created correctly."""

    @pytest.mark.unit
    def test_all_pipelines_job_exists(self):
        try:
            from databox_orchestration import definitions
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        job_names = {j.name for j in definitions.jobs}
        assert "all_pipelines" in job_names

    @pytest.mark.unit
    def test_per_source_jobs_exist(self):
        try:
            from databox_orchestration import definitions
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        job_names = {j.name for j in definitions.jobs}
        assert "ebird_daily_pipeline" in job_names
        assert "noaa_daily_pipeline" in job_names

    @pytest.mark.unit
    def test_total_asset_count(self):
        """Verify we have ~17 fine-grained assets (9 dlt + 8 sqlmesh)."""
        try:
            from databox_orchestration import definitions
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        all_specs = [spec for a in definitions.assets for spec in a.specs]
        # 6 ebird dlt + 3 noaa dlt + 8 sqlmesh = 17
        assert len(all_specs) >= 17, (
            f"Expected at least 17 fine-grained assets, got {len(all_specs)}"
        )
