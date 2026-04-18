"""Tests for databox_config.settings and databox_config.pipeline_config."""

from __future__ import annotations

import pytest
from databox_config.pipeline_config import (
    PipelineConfig,
    PipelineSchedule,
    QualityRule,
    load_all_pipeline_configs,
    load_pipeline_config,
)


class TestDataboxSettings:
    @pytest.mark.unit
    def test_default_database_url(self):
        from databox_config.settings import DataboxSettings

        s = DataboxSettings()
        assert s.database_url.startswith("postgresql://")
        assert "databox" in s.database_url

    @pytest.mark.unit
    def test_default_log_level(self):
        from databox_config.settings import settings

        assert settings.log_level == "INFO"

    @pytest.mark.unit
    def test_custom_database_url(self):
        from databox_config.settings import DataboxSettings

        s = DataboxSettings(database_url="postgresql://user:pass@host:5432/mydb")
        assert s.database_url == "postgresql://user:pass@host:5432/mydb"

    @pytest.mark.unit
    def test_env_override(self, monkeypatch):
        from databox_config.settings import DataboxSettings

        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        s = DataboxSettings()
        assert s.log_level == "DEBUG"


class TestPipelineSchedule:
    @pytest.mark.unit
    def test_defaults(self):
        sched = PipelineSchedule()
        assert sched.cron == "0 6 * * *"
        assert sched.enabled is True

    @pytest.mark.unit
    def test_custom(self):
        sched = PipelineSchedule(cron="0 */2 * * *", enabled=False)
        assert sched.cron == "0 */2 * * *"
        assert sched.enabled is False


class TestQualityRule:
    @pytest.mark.unit
    def test_basic_rule(self):
        rule = QualityRule(column="id", check="not_null")
        assert rule.column == "id"
        assert rule.check == "not_null"
        assert rule.threshold is None

    @pytest.mark.unit
    def test_rule_with_threshold(self):
        rule = QualityRule(column="score", check="gt", threshold=0.95)
        assert rule.threshold == 0.95


class TestPipelineConfig:
    @pytest.mark.unit
    def test_resolve_schema_explicit(self):
        cfg = PipelineConfig(name="test", source_module="mod", schema_name="custom")
        assert cfg.resolve_schema_name() == "custom"

    @pytest.mark.unit
    def test_resolve_schema_default(self):
        cfg = PipelineConfig(name="ebird", source_module="mod")
        assert cfg.resolve_schema_name() == "raw_ebird"

    @pytest.mark.unit
    def test_resolve_schema_empty_string(self):
        cfg = PipelineConfig(name="weather", source_module="mod", schema_name="")
        assert cfg.resolve_schema_name() == "raw_weather"

    @pytest.mark.unit
    def test_full_config(self):
        cfg = PipelineConfig(
            name="ebird",
            source_module="databox_sources.ebird.source",
            description="eBird data",
            schedule=PipelineSchedule(cron="0 6 * * *"),
            params={"region_code": "US-AZ"},
            quality_rules=[QualityRule(column="speciesCode", check="not_null")],
            transform_project="ebird",
        )
        assert cfg.name == "ebird"
        assert cfg.transform_project == "ebird"
        assert len(cfg.quality_rules) == 1


class TestLoadPipelineConfig:
    @pytest.mark.unit
    def test_load_valid_config(self, mock_sources_dir, monkeypatch):
        import databox_config.pipeline_config as pc_mod

        monkeypatch.setattr(pc_mod, "SOURCES_DIR", mock_sources_dir)
        cfg = load_pipeline_config("ebird")
        assert cfg.name == "ebird"
        assert cfg.source_module == "databox_sources.ebird.source"
        assert cfg.params["region_code"] == "US-AZ"

    @pytest.mark.unit
    def test_load_missing_config(self, mock_sources_dir, monkeypatch):
        import databox_config.pipeline_config as pc_mod

        monkeypatch.setattr(pc_mod, "SOURCES_DIR", mock_sources_dir)
        with pytest.raises(FileNotFoundError, match="no_exist"):
            load_pipeline_config("no_exist")

    @pytest.mark.unit
    def test_load_all_empty_dir(self, tmp_path, monkeypatch):
        import databox_config.pipeline_config as pc_mod

        monkeypatch.setattr(pc_mod, "SOURCES_DIR", tmp_path / "empty")
        result = load_all_pipeline_configs()
        assert result == {}

    @pytest.mark.unit
    def test_load_all_multiple(self, mock_sources_dir, monkeypatch):
        import databox_config.pipeline_config as pc_mod

        weather_dir = mock_sources_dir / "weather"
        weather_dir.mkdir()
        (weather_dir / "config.yaml").write_text('source_module: "mod"\ndescription: "Weather"')
        monkeypatch.setattr(pc_mod, "SOURCES_DIR", mock_sources_dir)
        result = load_all_pipeline_configs()
        assert "ebird" in result
        assert "weather" in result
