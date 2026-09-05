import json
import os
import subprocess
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


readiness = _load("catalog_backup_readiness", "catalog-backup-readiness.py")
recovery = _load("catalog_recovery", "catalog_recovery.py")

_BACKUP_ENV = {
    "PGBACKREST_REPO1_CIPHER_PASS": "not-a-real-secret",  # secret-scan: allow
    "PGBACKREST_REPO1_S3_KEY": "temporary-access-key",  # secret-scan: allow
    "PGBACKREST_REPO1_S3_KEY_SECRET": "temporary-secret-key",  # secret-scan: allow
    "PGBACKREST_REPO1_S3_TOKEN": "temporary-session-token",  # secret-scan: allow
    "PGBACKREST_REPO1_S3_BUCKET": "catalog-backups",
    "PGBACKREST_REPO1_S3_REGION": "us-west-1",
    "PGBACKREST_REPO1_S3_ENDPOINT": "s3.us-west-1.amazonaws.com",
}


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


@pytest.mark.parametrize(
    "missing_name",
    (
        "PGBACKREST_REPO1_S3_KEY",
        "PGBACKREST_REPO1_S3_KEY_SECRET",
        "PGBACKREST_REPO1_S3_TOKEN",
    ),
)
def test_readiness_gate_rejects_missing_temporary_credential(missing_name: str) -> None:
    env = {name: value for name, value in _BACKUP_ENV.items() if name != missing_name}
    with patch.dict(readiness.os.environ, env, clear=True):
        with pytest.raises(readiness.ReadinessError, match=missing_name):
            readiness.ensure_catalog_backup_ready()


def test_pgbackrest_wrapper_rejects_partial_credentials_without_printing_values() -> None:
    secret_value = "must-not-appear-in-output"  # secret-scan: allow
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PGBACKREST_REPO1_CIPHER_PASS": secret_value,
        "PGBACKREST_REPO1_S3_KEY": secret_value,
        "PGBACKREST_REPO1_S3_KEY_SECRET": secret_value,
    }
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/platform/run-pgbackrest.sh"), "info"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "temporary backup session token" in result.stderr
    assert secret_value not in result.stdout + result.stderr


def test_readiness_gate_checks_wal_and_creates_initial_backup(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []
    info_results = iter(
        [
            json.dumps([{"name": "polaris", "status": {"code": 0}, "backup": []}]),
            json.dumps(
                [
                    {
                        "name": "polaris",
                        "status": {"code": 0},
                        "backup": [{"label": "full"}],
                    }
                ]
            ),
        ]
    )

    def runner(command):
        calls.append(tuple(command))
        stdout = next(info_results) if command[-1] == "info" else ""
        return Mock(stdout=stdout, returncode=0)

    with patch.dict(readiness.os.environ, _BACKUP_ENV, clear=True):
        readiness.ensure_catalog_backup_ready(runner=runner)
    assert [call[-1] for call in calls] == [
        "polaris",
        "stanza-create",
        "check",
        "info",
        "backup",
        "info",
    ]
    assert calls[2] == (readiness._PGBACKREST, "--stanza=polaris", "check")


def test_readiness_gate_does_not_replace_existing_backup(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def runner(command):
        calls.append(tuple(command))
        stdout = (
            json.dumps(
                [
                    {
                        "name": "polaris",
                        "status": {"code": 0},
                        "backup": [{"label": "existing"}],
                    }
                ]
            )
            if command[-1] == "info"
            else ""
        )
        return Mock(stdout=stdout, returncode=0)

    with patch.dict(readiness.os.environ, _BACKUP_ENV, clear=True):
        readiness.ensure_catalog_backup_ready(runner=runner)

    assert "backup" not in [call[-1] for call in calls]


def test_pgbackrest_contract_has_fail_closed_gate_archive_and_retention() -> None:
    config = (ROOT / "infra/recovery/pgbackrest.conf.example").read_text()
    compose = (ROOT / "compose.iceberg.yml").read_text()
    dockerfile = (ROOT / "scripts/platform/polaris-postgres.Dockerfile").read_text()
    assert "repo1-retention-full=30" in config
    assert "repo1-cipher-type=aes-256-cbc" in config
    assert "archive_timeout=300s" in compose
    assert "archive_command" in compose
    assert 'test: ["CMD-SHELL", "pg_isready -U polaris -d polaris"]' in compose
    assert "catalog-backup-readiness:" in compose
    assert 'command: ["python3", "/opt/databox/catalog-backup-readiness.py"]' in compose
    bootstrap = compose.index("  polaris-bootstrap:")
    backup_gate = compose.index("  catalog-backup-readiness:")
    polaris = compose.index("  polaris:\n")
    assert bootstrap < backup_gate < polaris
    gate_block = compose[backup_gate:polaris]
    assert "polaris-bootstrap:" in gate_block
    assert "condition: service_completed_successfully" in gate_block
    polaris_block = compose[polaris : compose.index("  polaris-console:")]
    assert "catalog-backup-readiness:" in polaris_block
    assert "condition: service_completed_successfully" in polaris_block
    run_pgbackrest = (ROOT / "scripts/platform/run-pgbackrest.sh").read_text()
    recovery_script = (ROOT / "scripts/platform/catalog_recovery.py").read_text()
    assert '"authoritative_backup_archive": "disabled"' in recovery_script
    assert "catalog-backup-readiness.py" in dockerfile
    assert "DATABOX_AWS_CREDENTIAL_PROCESS" not in compose
    assert "credential-process" not in dockerfile
    assert "awscli" not in dockerfile.lower()
    assert "PGBACKREST_REPO1_S3_TOKEN" in run_pgbackrest
