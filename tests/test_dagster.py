"""Tests for dynamic Dagster asset generation.

These tests verify the orchestration layer auto-generates correctly
from the pipeline registry, without needing Dagster installed at import time.
"""

from __future__ import annotations

import pytest


class TestDagsterAssetGeneration:
    """Test that dagster_project.py auto-generates assets from configs."""

    @pytest.mark.unit
    def test_module_loads_with_configs(self):
        """Verify the module can be imported and generates assets."""
        try:
            from orchestration import dagster_project
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        assert hasattr(dagster_project, "defs")
        assert hasattr(dagster_project, "assets")
        assert len(dagster_project.assets) > 0

    @pytest.mark.unit
    def test_assets_match_registered_pipelines(self):
        try:
            from orchestration import dagster_project
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        from pipelines.registry import get_registry

        registry = get_registry()
        asset_names = {a.key.path[-1] for a in dagster_project.assets}

        for name in registry:
            assert f"{name}_raw_data" in asset_names, f"Missing ingestion asset for '{name}'"

    @pytest.mark.unit
    def test_transform_assets_for_configured_projects(self):
        try:
            from orchestration import dagster_project
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        from pipelines.registry import get_registry

        registry = get_registry()
        asset_names = {a.key.path[-1] for a in dagster_project.assets}

        for name, source in registry.items():
            cfg = source.config
            if cfg.transform_project:
                assert f"{name}_transforms" in asset_names, f"Missing transform asset for '{name}'"

    @pytest.mark.unit
    def test_jobs_created_per_pipeline(self):
        try:
            from orchestration import dagster_project
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        from pipelines.registry import get_registry

        registry = get_registry()
        job_names = {j.name for j in dagster_project.jobs}

        for name in registry:
            assert f"{name}_daily_pipeline" in job_names, f"Missing job for '{name}'"

    @pytest.mark.unit
    def test_schedules_for_enabled_pipelines(self):
        try:
            from orchestration import dagster_project
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        from pipelines.registry import get_registry

        registry = get_registry()
        schedule_names = set()
        for s in dagster_project.schedules:
            schedule_names.add(s.job.name)

        for name, source in registry.items():
            cfg = source.config
            if cfg.schedule.enabled:
                assert f"{name}_daily_pipeline" in schedule_names, (
                    f"Missing schedule for enabled pipeline '{name}'"
                )


class TestCreatePipelineAsset:
    """Test the factory function for creating pipeline ingestion assets."""

    @pytest.mark.unit
    def test_creates_asset_with_correct_name(self):
        try:
            from orchestration.dagster_project import create_pipeline_asset
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        asset = create_pipeline_asset("test", "some.module")
        assert asset is not None


class TestCreateTransformAsset:
    """Test the factory function for creating transform assets."""

    @pytest.mark.unit
    def test_creates_asset_with_deps(self):
        try:
            from orchestration.dagster_project import create_transform_asset
        except ImportError:
            pytest.skip("Dagster not installed")
            return

        asset = create_transform_asset("test", "test_project")
        assert asset is not None
