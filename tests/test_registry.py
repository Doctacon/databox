"""Tests for pipeline registry and PipelineSource protocol."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from config.pipeline_config import PipelineConfig
from pipelines.base import PipelineSource


class TestPipelineSourceProtocol:
    @pytest.mark.unit
    def test_compliant_class(self):
        class GoodSource:
            name = "test"
            config = MagicMock()

            def resources(self) -> list:
                return []

            def load(self) -> Any:
                return MagicMock()

            def validate_config(self) -> bool:
                return True

        assert isinstance(GoodSource(), PipelineSource)

    @pytest.mark.unit
    def test_non_compliant_class_missing_name(self):
        class BadSource:
            config = MagicMock()

            def resources(self) -> list:
                return []

            def load(self) -> Any:
                return None

            def validate_config(self) -> bool:
                return False

        assert not isinstance(BadSource(), PipelineSource)

    @pytest.mark.unit
    def test_non_compliant_class_missing_methods(self):
        class Empty:
            name = "x"

        assert not isinstance(Empty(), PipelineSource)

    @pytest.mark.unit
    def test_ebird_source_is_compliant(self, mock_ebird_api_token):
        from pipelines.sources.ebird_api import create_pipeline

        cfg = PipelineConfig(
            name="ebird",
            source_module="pipelines.sources.ebird_api",
            params={"region_code": "US-AZ"},
        )
        source = create_pipeline(cfg)
        assert isinstance(source, PipelineSource)


class TestRegistry:
    @pytest.mark.unit
    def test_get_registry_discovers_ebird(self):
        from pipelines.registry import get_registry

        registry = get_registry(refresh=True)
        assert "ebird" in registry
        assert isinstance(registry["ebird"], PipelineSource)

    @pytest.mark.unit
    def test_get_source_existing(self):
        from pipelines.registry import get_source

        source = get_source("ebird")
        assert source.name == "ebird"

    @pytest.mark.unit
    def test_get_source_missing(self):
        from pipelines.registry import get_source

        with pytest.raises(KeyError, match="no_exist"):
            get_source("no_exist")

    @pytest.mark.unit
    def test_get_source_missing_message(self):
        from pipelines.registry import get_source

        with pytest.raises(KeyError, match="not found"):
            get_source("anything")

    @pytest.mark.unit
    def test_registry_caching(self):
        import pipelines.registry as reg

        reg._REGISTRY = None
        r1 = reg.get_registry()
        r2 = reg.get_registry()
        assert r1 is r2

    @pytest.mark.unit
    def test_registry_refresh(self):
        import pipelines.registry as reg

        reg._REGISTRY = None
        r1 = reg.get_registry()
        r2 = reg.get_registry(refresh=True)
        assert r1 is not r2

    @pytest.mark.unit
    def test_build_source_missing_module(self):
        from pipelines.registry import _build_source

        cfg = PipelineConfig(
            name="bad",
            source_module="nonexistent.module",
        )
        with pytest.raises(ModuleNotFoundError):
            _build_source(cfg)

    @pytest.mark.unit
    def test_build_source_missing_factory(self):
        from pipelines.registry import _build_source

        cfg = PipelineConfig(
            name="bad",
            source_module="config.settings",
        )
        with pytest.raises(AttributeError, match="create_pipeline"):
            _build_source(cfg)

    @pytest.mark.unit
    def test_bad_source_skipped(self, monkeypatch):
        from unittest.mock import patch

        import pipelines.registry as reg
        from config.pipeline_config import PipelineConfig, PipelineSchedule

        bad_cfg = PipelineConfig(
            name="broken",
            source_module="nonexistent.module",
            schedule=PipelineSchedule(enabled=False),
        )

        with patch.object(reg, "load_all_pipeline_configs", return_value={"broken": bad_cfg}):
            registry = reg.get_registry(refresh=True)
            assert "broken" not in registry
