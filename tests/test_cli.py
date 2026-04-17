"""Tests for the databox CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock

import duckdb
import pytest
from typer.testing import CliRunner

from cli.main import app
from config.pipeline_config import PipelineConfig, PipelineSchedule

runner = CliRunner()


class TestList:
    @pytest.mark.unit
    def test_list_with_pipelines(self, mocker):
        mock_source = MagicMock()
        mock_source.config = PipelineConfig(
            name="test",
            source_module="mod",
            schedule=PipelineSchedule(cron="0 * * * *"),
        )
        mock_source.validate_config.return_value = True

        mocker.patch(
            "sources.registry.get_registry",
            return_value={"test": mock_source},
        )
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "test" in result.output

    @pytest.mark.unit
    def test_list_empty(self, mocker):
        mocker.patch("sources.registry.get_registry", return_value={})
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No pipelines registered" in result.output


class TestRun:
    @pytest.mark.unit
    def test_run_valid_pipeline(self, mocker):
        mock_source = MagicMock()
        mock_source.validate_config.return_value = True
        mocker.patch("sources.registry.get_source", return_value=mock_source)

        result = runner.invoke(app, ["run", "ebird"])
        assert result.exit_code == 0
        mock_source.load.assert_called_once()

    @pytest.mark.unit
    def test_run_invalid_config(self, mocker):
        mock_source = MagicMock()
        mock_source.validate_config.return_value = False
        mocker.patch("sources.registry.get_source", return_value=mock_source)

        result = runner.invoke(app, ["run", "ebird"])
        assert result.exit_code == 1

    @pytest.mark.unit
    def test_run_unknown_pipeline(self, mocker):
        mocker.patch(
            "sources.registry.get_source",
            side_effect=KeyError("Pipeline 'nope' not found."),
        )
        result = runner.invoke(app, ["run", "nope"])
        assert result.exit_code == 1


class TestValidate:
    @pytest.mark.unit
    def test_validate_valid(self, mocker):
        mock_source = MagicMock()
        mock_source.validate_config.return_value = True
        mocker.patch("sources.registry.get_source", return_value=mock_source)

        result = runner.invoke(app, ["validate", "ebird"])
        assert result.exit_code == 0
        assert "valid" in result.output

    @pytest.mark.unit
    def test_validate_invalid(self, mocker):
        mock_source = MagicMock()
        mock_source.validate_config.return_value = False
        mocker.patch("sources.registry.get_source", return_value=mock_source)

        result = runner.invoke(app, ["validate", "ebird"])
        assert result.exit_code == 1


class TestTransform:
    @pytest.mark.unit
    def test_transform_plan_specific_project(self, mocker):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_result)

        result = runner.invoke(app, ["transform", "plan", "ebird"])
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_transform_plan_discovers_all(self, mocker):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_result)

        result = runner.invoke(app, ["transform", "plan"])
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_transform_run_subprocess_failure(self, mocker):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mocker.patch("subprocess.run", return_value=mock_result)

        result = runner.invoke(app, ["transform", "run", "ebird"])
        assert result.exit_code == 1

    @pytest.mark.unit
    def test_transform_test(self, mocker):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_result)

        result = runner.invoke(app, ["transform", "test", "ebird"])
        assert result.exit_code == 0


class TestQuality:
    @pytest.mark.integration
    def test_quality_with_data(self, tmp_db, mocker):
        mocker.patch(
            "config.settings.settings.database_url",
            f"duckdb:///{tmp_db}",
        )

        con = duckdb.connect(str(tmp_db))
        con.execute("CREATE SCHEMA raw_ebird")
        con.execute(
            "CREATE TABLE raw_ebird.observations AS "
            "SELECT 'norcar' as species_code, 3 as count, "
            "'2025-07-20'::timestamp as _loaded_at"
        )
        con.close()

        result = runner.invoke(app, ["quality", "check", "raw_ebird.observations"])
        assert result.exit_code == 0
        assert "Total rows: 1" in result.output

    @pytest.mark.integration
    def test_quality_no_db(self, tmp_path, mocker):
        mocker.patch(
            "config.settings.settings.database_url",
            f"duckdb:///{tmp_path / 'nonexistent.db'}",
        )
        result = runner.invoke(app, ["quality", "check", "raw_ebird.test"])
        assert result.exit_code == 1

    @pytest.mark.integration
    def test_quality_report(self, tmp_db, mocker):
        mocker.patch(
            "config.settings.settings.database_url",
            f"duckdb:///{tmp_db}",
        )

        con = duckdb.connect(str(tmp_db))
        con.execute("CREATE SCHEMA raw_test")
        con.execute(
            "CREATE TABLE raw_test.observations AS "
            "SELECT 'norcar' AS species_code, 3 AS count, "
            "'2025-07-20'::timestamp AS _loaded_at"
        )
        con.close()

        mock_cfg = PipelineConfig(
            name="test",
            source_module="mock.module",
            schedule=PipelineSchedule(cron="0 6 * * *", enabled=True),
            quality_rules=[
                {"column": "species_code", "check": "not_null"},
            ],
        )
        mocker.patch(
            "config.pipeline_config.load_all_pipeline_configs",
            return_value={"test": mock_cfg},
        )

        result = runner.invoke(app, ["quality", "report"])
        assert result.exit_code == 0
        assert "All checks passed" in result.output


class TestStatus:
    @pytest.mark.integration
    def test_status_with_data(self, tmp_db, mocker):
        mocker.patch(
            "config.settings.settings.database_url",
            f"duckdb:///{tmp_db}",
        )

        mock_source = MagicMock()
        mock_source.config = PipelineConfig(name="ebird", source_module="mod")
        mock_source.validate_config.return_value = True
        mocker.patch("sources.registry.get_registry", return_value={"ebird": mock_source})

        con = duckdb.connect(str(tmp_db))
        con.execute("CREATE SCHEMA raw_ebird")
        con.execute(
            "CREATE TABLE raw_ebird.test AS "
            "SELECT 'x' as species_code, '2025-07-20'::timestamp as _loaded_at"
        )
        con.close()

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "raw_ebird" in result.output

    @pytest.mark.integration
    def test_status_no_db(self, tmp_path, mocker):
        mocker.patch(
            "config.settings.settings.database_url",
            f"duckdb:///{tmp_path / 'nonexistent.db'}",
        )
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()


class TestResolveTransformProjects:
    @pytest.mark.unit
    def test_named_project(self):
        from cli.main import _resolve_transform_projects

        result = _resolve_transform_projects("ebird")
        assert result == ["ebird"]

    @pytest.mark.unit
    def test_none_finds_projects_with_config(self, tmp_path, mocker):
        transforms = tmp_path / "transforms"
        transforms.mkdir()
        proj = transforms / "test_proj"
        proj.mkdir()
        (proj / "config.yaml").write_text("key: value")

        mocker.patch("config.settings.PROJECT_ROOT", tmp_path)
        from cli.main import _resolve_transform_projects

        result = _resolve_transform_projects(None)
        assert "test_proj" in result

    @pytest.mark.unit
    def test_none_raises_when_no_projects(self, tmp_path, mocker):
        import typer

        transforms = tmp_path / "transforms"
        transforms.mkdir()

        mocker.patch("config.settings.PROJECT_ROOT", tmp_path)
        from cli.main import _resolve_transform_projects

        with pytest.raises(typer.BadParameter):
            _resolve_transform_projects(None)
