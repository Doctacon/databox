import json
from datetime import UTC, datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).parents[2]


def _load(name: str, filename: str):
    spec = spec_from_file_location(name, ROOT / "scripts/platform" / filename)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


credentials = _load("pgbackrest_credentials", "pgbackrest-credential-process.py")
recovery = _load("catalog_recovery", "catalog_recovery.py")


def test_credential_process_rejects_missing_invalid_and_expired() -> None:
    with pytest.raises(ValueError, match="required"):
        credentials.load_credentials("")
    with patch.object(credentials.subprocess, "run", return_value=Mock(stdout="no", returncode=0)):
        with pytest.raises(ValueError, match="invalid JSON"):
            credentials.load_credentials("credential-helper")
    expired = json.dumps(
        {
            "AccessKeyId": "a",
            "SecretAccessKey": "b",
            "SessionToken": "c",
            "Expiration": "2020-01-01T00:00:00Z",
        }
    )
    with patch.object(
        credentials.subprocess, "run", return_value=Mock(stdout=expired, returncode=0)
    ):
        with pytest.raises(ValueError, match="expired"):
            credentials.load_credentials("credential-helper")


def test_exports_only_pgbackrest_names_and_quotes_values() -> None:
    text = credentials.shell_exports(
        {"AccessKeyId": "a", "SecretAccessKey": "b c", "SessionToken": "d", "Expiration": "x"}
    )
    assert "PGBACKREST_REPO1_S3_KEY" in text
    assert "AWS_SECRET_ACCESS_KEY" not in text
    assert "'b c'" in text


def test_recovery_target_must_be_zoned_and_target_is_isolated(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone"):
        recovery.recovery_target("2026-09-04T12:00:00")
    active = tmp_path / "active"
    active.mkdir()
    with pytest.raises(ValueError, match="active"):
        recovery.require_empty_isolated_target(active, active)
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "PG_VERSION").write_text("17")
    with pytest.raises(ValueError, match="empty"):
        recovery.require_empty_isolated_target(occupied, active)


def test_drill_metrics_do_not_claim_objectives() -> None:
    started = datetime.now(UTC)
    result = recovery.drill_result(
        started, started - timedelta(minutes=4), started + timedelta(minutes=20)
    )
    assert result["achieved_rpo_seconds"] == 240
    assert result["achieved_rto_seconds"] == 1200
    assert result["objectives_proven"] is False


def test_pgbackrest_contract_has_bounded_archive_and_retention() -> None:
    config = (ROOT / "infra/recovery/pgbackrest.conf.example").read_text()
    compose = (ROOT / "compose.iceberg.yml").read_text()
    assert "repo1-retention-full=30" in config
    assert "repo1-cipher-type=aes-256-cbc" in config
    assert "archive_timeout=300s" in compose
    assert "archive_command" in compose
