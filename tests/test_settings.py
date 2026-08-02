"""Local-only runtime settings contract."""

from pathlib import Path

import pytest
from databox.config.settings import PROJECT_ROOT, DataboxSettings, settings
from pydantic import ValidationError


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


@pytest.mark.parametrize("days_back", [0, 31])
def test_ebird_window_rejects_values_outside_provider_limit(days_back: int) -> None:
    with pytest.raises(ValidationError):
        DataboxSettings(_env_file=None, DATABOX_EBIRD_DAYS_BACK=days_back)


@pytest.mark.parametrize("max_records", [0, 10_001])
def test_gbif_record_cap_rejects_unbounded_values(max_records: int) -> None:
    with pytest.raises(ValidationError):
        DataboxSettings(_env_file=None, DATABOX_GBIF_MAX_RECORDS=max_records)


def test_gbif_public_release_is_explicit_and_disabled_by_default() -> None:
    assert DataboxSettings(_env_file=None).gbif_public_release is False
    assert (
        DataboxSettings(_env_file=None, DATABOX_GBIF_PUBLIC_RELEASE="true").gbif_public_release
        is True
    )
