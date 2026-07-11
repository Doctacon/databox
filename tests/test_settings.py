"""Local-only runtime settings contract."""

from pathlib import Path

from databox.config.settings import PROJECT_ROOT, DataboxSettings, settings


def test_sqlmesh_uses_only_local_databox_gateway() -> None:
    config = settings.sqlmesh_config()

    assert config.default_gateway == "local"
    assert set(config.gateways) == {"local"}
    assert config.gateways["local"].connection.catalogs == {
        "databox": str(PROJECT_ROOT / "data" / "databox.duckdb")
    }
    assert Path(settings.database_path) == PROJECT_ROOT / "data" / "databox.duckdb"


def test_alert_smtp_settings_are_secret_in_runtime_repr() -> None:
    configured = DataboxSettings(
        _env_file=None,
        BIRD_ALERT_SMTP_ENABLED="true",
        BIRD_ALERT_SMTP_SECURITY="starttls",
        BIRD_ALERT_SMTP_HOST="127.0.0.1",
        BIRD_ALERT_SMTP_PORT="1025",
        BIRD_ALERT_SMTP_USERNAME="synthetic-user",
        BIRD_ALERT_SMTP_PASSWORD="synthetic-password",
        BIRD_ALERT_FROM_EMAIL="synthetic-organizer",
        BIRD_ALERT_RECIPIENT_EMAIL="synthetic-recipient",
        BIRD_ALERT_SMTP_CA_FILE="synthetic-certificate-path",
    )
    rendered = repr(configured)
    for value in (
        "127.0.0.1",
        "1025",
        "synthetic-user",
        "synthetic-password",
        "synthetic-organizer",
        "synthetic-recipient",
        "synthetic-certificate-path",
    ):
        assert value not in rendered
