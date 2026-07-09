"""Local-only runtime settings contract."""

from pathlib import Path

from databox.config.settings import PROJECT_ROOT, settings


def test_sqlmesh_uses_only_local_databox_gateway() -> None:
    config = settings.sqlmesh_config()

    assert config.default_gateway == "local"
    assert set(config.gateways) == {"local"}
    assert config.gateways["local"].connection.catalogs == {
        "databox": str(PROJECT_ROOT / "data" / "databox.duckdb")
    }
    assert Path(settings.database_path) == PROJECT_ROOT / "data" / "databox.duckdb"
