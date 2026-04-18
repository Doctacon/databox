"""Tests for the databox CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from databox_cli.main import app
from databox_config.pipeline_config import PipelineConfig, PipelineSchedule
from typer.testing import CliRunner

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
            "databox_sources.registry.get_registry",
            return_value={"test": mock_source},
        )
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "test" in result.output

    @pytest.mark.unit
    def test_list_empty(self, mocker):
        mocker.patch("databox_sources.registry.get_registry", return_value={})
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No pipelines registered" in result.output


class TestRun:
    @pytest.mark.unit
    def test_run_valid_pipeline(self, mocker):
        mock_source = MagicMock()
        mock_source.validate_config.return_value = True
        mocker.patch("databox_sources.registry.get_source", return_value=mock_source)

        result = runner.invoke(app, ["run", "ebird"])
        assert result.exit_code == 0
        mock_source.load.assert_called_once()

    @pytest.mark.unit
    def test_run_invalid_config(self, mocker):
        mock_source = MagicMock()
        mock_source.validate_config.return_value = False
        mocker.patch("databox_sources.registry.get_source", return_value=mock_source)

        result = runner.invoke(app, ["run", "ebird"])
        assert result.exit_code == 1

    @pytest.mark.unit
    def test_run_unknown_pipeline(self, mocker):
        mocker.patch(
            "databox_sources.registry.get_source",
            side_effect=KeyError("Pipeline 'nope' not found."),
        )
        result = runner.invoke(app, ["run", "nope"])
        assert result.exit_code == 1


class TestValidate:
    @pytest.mark.unit
    def test_validate_valid(self, mocker):
        mock_source = MagicMock()
        mock_source.validate_config.return_value = True
        mocker.patch("databox_sources.registry.get_source", return_value=mock_source)

        result = runner.invoke(app, ["validate", "ebird"])
        assert result.exit_code == 0
        assert "valid" in result.output

    @pytest.mark.unit
    def test_validate_invalid(self, mocker):
        mock_source = MagicMock()
        mock_source.validate_config.return_value = False
        mocker.patch("databox_sources.registry.get_source", return_value=mock_source)

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
    def test_quality_with_data(self, pg_con, mocker):
        from tests.conftest import _TEST_DATABASE_URL

        mocker.patch("databox_config.settings.settings.database_url", _TEST_DATABASE_URL)

        cur = pg_con.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw_ebird_cli_test")
        cur.execute("DROP TABLE IF EXISTS raw_ebird_cli_test.observations")
        cur.execute(
            "CREATE TABLE raw_ebird_cli_test.observations ("
            "species_code TEXT, count INTEGER, _loaded_at TIMESTAMP)"
        )
        cur.execute(
            "INSERT INTO raw_ebird_cli_test.observations VALUES "
            "('norcar', 3, '2025-07-20'::timestamp)"
        )
        pg_con.commit()

        try:
            result = runner.invoke(app, ["quality", "check", "raw_ebird_cli_test.observations"])
            assert result.exit_code == 0
            assert "Total rows: 1" in result.output
        finally:
            cur.execute("DROP TABLE IF EXISTS raw_ebird_cli_test.observations")
            cur.execute("DROP SCHEMA IF EXISTS raw_ebird_cli_test")
            pg_con.commit()

    @pytest.mark.integration
    def test_quality_no_db(self, mocker):
        mocker.patch(
            "databox_config.settings.settings.database_url",
            "postgresql://invalid:invalid@localhost:9999/nonexistent",
        )
        result = runner.invoke(app, ["quality", "check", "raw_ebird.test"])
        assert result.exit_code == 1

    @pytest.mark.integration
    def test_quality_report(self, pg_con, mocker):
        from tests.conftest import _TEST_DATABASE_URL

        mocker.patch("databox_config.settings.settings.database_url", _TEST_DATABASE_URL)

        cur = pg_con.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw_test_cli")
        cur.execute("DROP TABLE IF EXISTS raw_test_cli.observations")
        cur.execute(
            "CREATE TABLE raw_test_cli.observations ("
            "species_code TEXT, count INTEGER, _loaded_at TIMESTAMP)"
        )
        cur.execute(
            "INSERT INTO raw_test_cli.observations VALUES ('norcar', 3, '2025-07-20'::timestamp)"
        )
        pg_con.commit()

        mock_cfg = PipelineConfig(
            name="test",
            source_module="mock.module",
            schedule=PipelineSchedule(cron="0 6 * * *", enabled=True),
            quality_rules=[
                {"column": "species_code", "check": "not_null"},
            ],
        )
        mocker.patch(
            "databox_config.pipeline_config.load_all_pipeline_configs",
            return_value={"test": mock_cfg},
        )

        try:
            result = runner.invoke(app, ["quality", "report"])
            assert result.exit_code == 0
            assert "All checks passed" in result.output
        finally:
            cur.execute("DROP TABLE IF EXISTS raw_test_cli.observations")
            cur.execute("DROP SCHEMA IF EXISTS raw_test_cli")
            pg_con.commit()


class TestStatus:
    @pytest.mark.integration
    def test_status_with_data(self, pg_con, mocker):
        from tests.conftest import _TEST_DATABASE_URL

        mocker.patch("databox_config.settings.settings.database_url", _TEST_DATABASE_URL)

        mock_source = MagicMock()
        mock_source.config = PipelineConfig(name="ebird", source_module="mod")
        mock_source.validate_config.return_value = True
        mocker.patch("databox_sources.registry.get_registry", return_value={"ebird": mock_source})

        cur = pg_con.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw_ebird_status_test")
        cur.execute("DROP TABLE IF EXISTS raw_ebird_status_test.test")
        cur.execute(
            "CREATE TABLE raw_ebird_status_test.test (species_code TEXT, _loaded_at TIMESTAMP)"
        )
        cur.execute("INSERT INTO raw_ebird_status_test.test VALUES ('x', '2025-07-20'::timestamp)")
        pg_con.commit()

        try:
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0
            assert "raw_ebird_status_test" in result.output
        finally:
            cur.execute("DROP TABLE IF EXISTS raw_ebird_status_test.test")
            cur.execute("DROP SCHEMA IF EXISTS raw_ebird_status_test")
            pg_con.commit()

    @pytest.mark.integration
    def test_status_no_db(self, mocker):
        mocker.patch(
            "databox_config.settings.settings.database_url",
            "postgresql://invalid:invalid@localhost:9999/nonexistent",
        )
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()


class TestResolveTransformProjects:
    @pytest.mark.unit
    def test_named_project(self):
        from databox_cli.main import _resolve_transform_projects

        result = _resolve_transform_projects("ebird")
        assert result == ["ebird"]

    @pytest.mark.unit
    def test_none_finds_projects_with_config(self, tmp_path, mocker):
        transforms = tmp_path / "transforms"
        transforms.mkdir()
        proj = transforms / "test_proj"
        proj.mkdir()
        (proj / "config.yaml").write_text("key: value")

        mocker.patch("databox_config.settings.PROJECT_ROOT", tmp_path)
        from databox_cli.main import _resolve_transform_projects

        result = _resolve_transform_projects(None)
        assert "test_proj" in result

    @pytest.mark.unit
    def test_none_raises_when_no_projects(self, tmp_path, mocker):
        import typer

        transforms = tmp_path / "transforms"
        transforms.mkdir()

        mocker.patch("databox_config.settings.PROJECT_ROOT", tmp_path)
        from databox_cli.main import _resolve_transform_projects

        with pytest.raises(typer.BadParameter):
            _resolve_transform_projects(None)
