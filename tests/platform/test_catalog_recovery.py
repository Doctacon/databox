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


def test_interactive_credentials_require_tty_before_aws() -> None:
    runner = Mock(side_effect=AssertionError("AWS invoked without an operator TTY"))

    with pytest.raises(recovery.RecoveryError, match="operator TTY"):
        recovery.acquire_backup_role_environment(
            environ=_BACKUP_ENV,
            runner=runner,
            stdin_isatty=False,
            stderr_isatty=True,
        )

    runner.assert_not_called()


def test_interactive_credentials_flow_from_aws_pipe_to_memory_only() -> None:
    secret = "temporary-exported-secret"  # secret-scan: allow
    token = "temporary-exported-token"  # secret-scan: allow
    calls = []

    def runner(command, **kwargs):
        calls.append((tuple(command), kwargs))
        if command[:2] == ("aws", "login"):
            return subprocess.CompletedProcess(command, 0)
        payload = json.dumps(
            {
                "Version": 1,
                "AccessKeyId": "ASIA" + "ABCDEFGHIJKLMNOP",  # secret-scan: allow
                "SecretAccessKey": secret,  # secret-scan: allow
                "SessionToken": token,  # secret-scan: allow
                "Expiration": "2026-09-09T13:00:00Z",
            }
        )
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    environment = recovery.acquire_backup_role_environment(
        environ=_BACKUP_ENV,
        runner=runner,
        stdin_isatty=True,
        stderr_isatty=True,
        now=lambda: datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert calls[0] == (
        ("aws", "login", "--remote", "--profile", "databox-recovery-operator"),
        {"check": False, "text": True},
    )
    assert calls[1][0] == (
        "aws",
        "configure",
        "export-credentials",
        "--profile",
        "databox-polaris-catalog-backup",
        "--format",
        "process",
    )
    assert calls[1][1] == {
        "check": False,
        "stdout": subprocess.PIPE,
        "text": True,
    }
    assert "stderr" not in calls[1][1]
    assert environment["PGBACKREST_REPO1_S3_KEY_SECRET"] == secret
    assert environment["PGBACKREST_REPO1_S3_TOKEN"] == token
    rendered_commands = json.dumps([command for command, _kwargs in calls])
    assert secret not in rendered_commands
    assert token not in rendered_commands


def test_interactive_credential_export_failure_is_secret_redacted() -> None:
    secret = "must-never-appear"  # secret-scan: allow

    def runner(command, **_kwargs):
        if command[:2] == ("aws", "login"):
            return subprocess.CompletedProcess(command, 0)
        payload = json.dumps({"SecretAccessKey": secret})  # secret-scan: allow
        return subprocess.CompletedProcess(command, 1, stdout=payload, stderr="MFA failed")

    with pytest.raises(recovery.RecoveryError, match="credential export failed") as error:
        recovery.acquire_backup_role_environment(
            environ=_BACKUP_ENV,
            runner=runner,
            stdin_isatty=True,
            stderr_isatty=True,
        )

    assert secret not in str(error.value)
    assert '"SecretAccessKey": "[REDACTED]"' in str(error.value)  # secret-scan: allow


def test_interactive_credentials_reject_expired_session() -> None:
    def runner(command, **_kwargs):
        if command[:2] == ("aws", "login"):
            return subprocess.CompletedProcess(command, 0)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "Version": 1,
                    "AccessKeyId": "ASIA" + "ABCDEFGHIJKLMNOP",  # secret-scan: allow
                    "SecretAccessKey": "temporary-secret",  # secret-scan: allow
                    "SessionToken": "temporary-token",  # secret-scan: allow
                    "Expiration": "2026-09-09T12:00:00Z",
                }
            ),
            stderr="",
        )

    with pytest.raises(recovery.RecoveryError, match="expired session"):
        recovery.acquire_backup_role_environment(
            environ=_BACKUP_ENV,
            runner=runner,
            stdin_isatty=True,
            stderr_isatty=True,
            now=lambda: datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        )


@pytest.mark.parametrize("expiration", [None, 123, {}, []])
def test_interactive_credentials_reject_non_string_expiration(expiration) -> None:
    def runner(command, **_kwargs):
        if command[:2] == ("aws", "login"):
            return subprocess.CompletedProcess(command, 0)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "Version": 1,
                    "AccessKeyId": "ASIA" + "ABCDEFGHIJKLMNOP",  # secret-scan: allow
                    "SecretAccessKey": "temporary-secret",  # secret-scan: allow
                    "SessionToken": "temporary-token",  # secret-scan: allow
                    "Expiration": expiration,
                }
            ),
        )

    with pytest.raises(recovery.RecoveryError, match="invalid response"):
        recovery.acquire_backup_role_environment(
            environ=_BACKUP_ENV,
            runner=runner,
            stdin_isatty=True,
            stderr_isatty=True,
        )


def test_recovery_target_must_be_zoned() -> None:
    with pytest.raises(ValueError, match="timezone"):
        recovery.recovery_target("2026-09-04T12:00:00")


@pytest.mark.parametrize("name", ("", "x", "bad name", "/active", "../escape"))
def test_restore_runner_rejects_invalid_volume_names(name: str) -> None:
    with pytest.raises(ValueError, match="volume name"):
        recovery.prepare_or_execute_restore(
            target_volume=name,
            active_volume="databox_polaris_postgres",
            recover_to=recovery.recovery_target("2026-09-05T12:00:00Z"),
            execute=False,
            environ=_BACKUP_ENV,
        )


def test_restore_runner_rejects_active_or_existing_volume() -> None:
    recover_to = recovery.recovery_target("2026-09-05T12:00:00Z")
    with pytest.raises(recovery.RecoveryError, match="active"):
        recovery.prepare_or_execute_restore(
            target_volume="databox_polaris_postgres",
            active_volume="databox_polaris_postgres",
            recover_to=recover_to,
            execute=False,
            environ=_BACKUP_ENV,
        )

    def existing(command):
        return subprocess.CompletedProcess(command, 0, stdout="databox_recovery\n", stderr="")

    with pytest.raises(recovery.RecoveryError, match="already exists"):
        recovery.prepare_or_execute_restore(
            target_volume="databox_recovery",
            active_volume="databox_polaris_postgres",
            recover_to=recover_to,
            execute=False,
            environ=_BACKUP_ENV,
            runner=existing,
        )


def test_restore_runner_requires_secrets_without_exposing_values() -> None:
    secret = "must-never-appear"  # secret-scan: allow
    environment = dict(_BACKUP_ENV)
    environment["PGBACKREST_REPO1_CIPHER_PASS"] = secret
    del environment["PGBACKREST_REPO1_S3_TOKEN"]
    with pytest.raises(recovery.RecoveryError, match="PGBACKREST_REPO1_S3_TOKEN") as error:
        recovery.prepare_or_execute_restore(
            target_volume="databox_recovery",
            active_volume="databox_polaris_postgres",
            recover_to=recovery.recovery_target("2026-09-05T12:00:00Z"),
            execute=False,
            environ=environment,
        )
    assert secret not in str(error.value)


def test_prepare_only_plans_safe_isolated_restore_without_mutation() -> None:
    calls: list[tuple[str, ...]] = []

    def runner(command):
        calls.append(tuple(command))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    token_factory = Mock(side_effect=AssertionError("prepare-only generated ownership token"))
    result = recovery.prepare_or_execute_restore(
        target_volume="databox_recovery",
        active_volume="databox_polaris_postgres",
        recover_to=recovery.recovery_target("2026-09-05T12:00:00-07:00"),
        execute=False,
        environ=_BACKUP_ENV,
        runner=runner,
        ownership_token_factory=token_factory,
    )
    assert result["mode"] == "prepare-only"
    assert calls == [("docker", "volume", "ls", "--quiet", "--filter", "name=^databox_recovery$")]
    token_factory.assert_not_called()


@pytest.mark.parametrize(
    ("recover_to", "expected"),
    [
        ("2026-09-05T16:25:13Z", "--target=2026-09-05 16:25:13+00"),
        ("2026-09-05T12:00:00-07:00", "--target=2026-09-05 19:00:00+00"),
    ],
)
def test_restore_command_renders_pgbackrest_utc_timestamp(recover_to: str, expected: str) -> None:
    _, restore = recovery._restore_commands(
        "databox_recovery", recovery.recovery_target(recover_to)
    )
    assert expected in restore


def test_execute_uses_only_owned_new_volume_and_secret_variable_names() -> None:
    calls: list[tuple[str, ...]] = []
    ownership_token = "unguessable-test-token"  # secret-scan: allow

    def runner(command):
        calls.append(tuple(command))
        stdout = ownership_token if command[1:3] == ("volume", "inspect") else ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    result = recovery.prepare_or_execute_restore(
        target_volume="databox_recovery",
        active_volume="databox_polaris_postgres",
        recover_to=recovery.recovery_target("2026-09-05T12:00:00-07:00"),
        execute=True,
        environ=_BACKUP_ENV,
        runner=runner,
        ownership_token_factory=lambda: ownership_token,
    )

    assert calls[1] == (
        "docker",
        "volume",
        "create",
        "--label",
        f"{recovery._OWNERSHIP_LABEL}={ownership_token}",
        "databox_recovery",
    )
    assert calls[2] == (
        "docker",
        "volume",
        "inspect",
        "--format",
        f'{{{{ index .Labels "{recovery._OWNERSHIP_LABEL}" }}}}',
        "databox_recovery",
    )
    initialize, restore = calls[3:]
    assert "--network" in initialize and "none" in initialize
    assert "root" in initialize and "chown" in initialize
    assert "--network" in restore and "bridge" in restore
    assert "postgres" in restore
    assert "type=volume,src=databox_recovery,dst=/var/lib/postgresql/data" in restore
    assert "databox_polaris_postgres" not in restore
    assert restore[-5:] == (
        "--stanza=polaris",
        "--type=time",
        "--target=2026-09-05 19:00:00+00",
        "--target-action=promote",
        "restore",
    )
    rendered = " ".join(part for call in calls for part in call)
    assert all(value not in rendered for value in _BACKUP_ENV.values())
    assert all(f"--env {name}" in rendered for name in _BACKUP_ENV)
    assert ownership_token not in json.dumps(result)
    for forbidden in ("archive-push", "--delta", "volume rm", "prune", "bootstrap", "--publish"):
        assert forbidden not in rendered
    assert "-p" not in restore


@pytest.mark.parametrize("observed_label", ("", "different-owner"))
def test_execute_refuses_volume_create_race_without_mounting_or_deleting(
    observed_label: str,
) -> None:
    calls: list[tuple[str, ...]] = []
    ownership_token = "unguessable-test-token"  # secret-scan: allow

    def runner(command):
        calls.append(tuple(command))
        stdout = observed_label if command[1:3] == ("volume", "inspect") else ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    with pytest.raises(recovery.RecoveryError, match="ownership") as error:
        recovery.prepare_or_execute_restore(
            target_volume="databox_recovery",
            active_volume="databox_polaris_postgres",
            recover_to=recovery.recovery_target("2026-09-05T12:00:00Z"),
            execute=True,
            environ=_BACKUP_ENV,
            runner=runner,
            ownership_token_factory=lambda: ownership_token,
        )

    assert ownership_token not in str(error.value)
    assert not any(call[:2] == ("docker", "run") for call in calls)
    assert not any(call[:3] == ("docker", "volume", "rm") for call in calls)


def test_failed_restore_preserves_target_and_reports_bounded_redacted_diagnostic() -> None:
    calls: list[tuple[str, ...]] = []
    ownership_token = "unguessable-test-token"  # secret-scan: allow
    access_key = "ASIA" + "ABCDEFGHIJKLMNOP"  # secret-scan: allow
    session_token = "IQoJb3JpZ2luX2VjABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"  # secret-scan: allow
    repository_secret = _BACKUP_ENV["PGBACKREST_REPO1_CIPHER_PASS"]

    def runner(command):
        calls.append(tuple(command))
        if command[-1] == "restore":
            stderr = (
                "x" * (recovery._DIAGNOSTIC_LIMIT + 100)
                + f"\nrestore-marker key={access_key} token={session_token} "
                + f"cipher={repository_secret} sessionToken=unlisted-token"  # secret-scan: allow
            )
            raise subprocess.CalledProcessError(1, command, output="stdout-marker", stderr=stderr)
        stdout = ownership_token if command[1:3] == ("volume", "inspect") else ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    with pytest.raises(recovery.RecoveryError, match="restore-marker") as error:
        recovery.prepare_or_execute_restore(
            target_volume="databox_recovery",
            active_volume="databox_polaris_postgres",
            recover_to=recovery.recovery_target("2026-09-05T12:00:00Z"),
            execute=True,
            environ=_BACKUP_ENV,
            runner=runner,
            ownership_token_factory=lambda: ownership_token,
        )
    message = str(error.value)
    assert "target volume databox_recovery" in message
    assert "[truncated]" in message
    assert "[REDACTED-AWS-ACCESS-KEY]" in message
    assert "[REDACTED-AWS-SESSION-TOKEN]" in message
    assert "sessionToken=[REDACTED]" in message
    assert access_key not in message
    assert session_token not in message
    assert repository_secret not in message
    assert len(message) <= recovery._DIAGNOSTIC_LIMIT + 200
    rendered = " ".join(part for call in calls for part in call)
    assert "volume rm" not in rendered


class _HermeticPgBackRestRepository:
    """Model backup selection and archive lookup at the Docker runner seam."""

    def __init__(
        self,
        *,
        ownership_token: str,
        backup_stop_times: tuple[str, ...],
        required_wal: str,
        archived_wal: frozenset[str],
    ) -> None:
        self.ownership_token = ownership_token
        self.backup_stop_times = backup_stop_times
        self.required_wal = required_wal
        self.archived_wal = archived_wal
        self.calls: list[tuple[str, ...]] = []
        self.selected_backup: str | None = None
        self.wal_lookups: list[str] = []
        self.restore_attempts = 0
        self.restore_exit_codes: list[int] = []

    def _restore_failure(self, command: tuple[str, ...], diagnostic: str) -> None:
        return_code = 37
        self.restore_exit_codes.append(return_code)
        repository_secret = _BACKUP_ENV["PGBACKREST_REPO1_CIPHER_PASS"]
        stderr = (
            "x" * (recovery._DIAGNOSTIC_LIMIT + 100) + f"\n{diagnostic}; cipher={repository_secret}"
        )
        raise subprocess.CalledProcessError(return_code, command, stderr=stderr)

    def __call__(self, command):
        command = tuple(command)
        self.calls.append(command)
        if command[1:3] == ("volume", "inspect"):
            return subprocess.CompletedProcess(command, 0, stdout=self.ownership_token, stderr="")
        if command[-1] != "restore":
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        self.restore_attempts += 1
        target = next(
            part.removeprefix("--target=") for part in command if part.startswith("--target=")
        )
        selectable = [stop for stop in self.backup_stop_times if stop < target]
        if not selectable:
            self._restore_failure(
                command, "unable to find backup set with stop time less than recovery target"
            )
        self.selected_backup = max(selectable)
        self.wal_lookups.append(self.required_wal)
        if self.required_wal not in self.archived_wal:
            self._restore_failure(
                command, f"unable to find required WAL segment {self.required_wal} in archive"
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


def _execute_expected_repository_failure(fake: _HermeticPgBackRestRepository) -> str:
    target_volume = "databox_missing_archive_recovery"
    with pytest.raises(recovery.RecoveryError) as error:
        recovery.prepare_or_execute_restore(
            target_volume=target_volume,
            active_volume="databox_polaris_postgres",
            recover_to=recovery.recovery_target("2026-09-05T12:00:00Z"),
            execute=True,
            environ=_BACKUP_ENV,
            runner=fake,
            ownership_token_factory=lambda: fake.ownership_token,
        )

    message = str(error.value)
    repository_secret = _BACKUP_ENV["PGBACKREST_REPO1_CIPHER_PASS"]
    assert repository_secret not in message
    assert "[REDACTED]" in message
    assert "[truncated]" in message
    assert len(message) <= recovery._DIAGNOSTIC_LIMIT + 200
    assert fake.restore_attempts == 1
    assert fake.restore_exit_codes == [37]
    assert sum(call[1:3] == ("volume", "create") for call in fake.calls) == 1
    assert sum(call[1:3] == ("volume", "inspect") for call in fake.calls) == 1
    assert sum(call[-1] == "restore" for call in fake.calls) == 1
    rendered = " ".join(part for call in fake.calls for part in call)
    assert f"{recovery._OWNERSHIP_LABEL}={fake.ownership_token}" in rendered
    assert f"type=volume,src={target_volume},dst=/var/lib/postgresql/data" in rendered
    assert "type=volume,src=databox_polaris_postgres" not in rendered
    assert "volume rm" not in rendered
    return message


def test_restore_fails_closed_when_repository_has_no_base_backup() -> None:
    fake = _HermeticPgBackRestRepository(
        ownership_token="owned-no-base-volume",  # secret-scan: allow
        backup_stop_times=(),
        required_wal="00000001000000000000000A",
        archived_wal=frozenset({"00000001000000000000000A"}),
    )

    message = _execute_expected_repository_failure(fake)

    assert "unable to find backup set with stop time less than recovery target" in message
    assert fake.selected_backup is None
    assert fake.wal_lookups == []


def test_restore_fails_closed_when_required_wal_segment_is_missing() -> None:
    fake = _HermeticPgBackRestRepository(
        ownership_token="owned-missing-wal-volume",  # secret-scan: allow
        backup_stop_times=("2026-09-05 11:59:00+00",),
        required_wal="00000001000000000000000A",
        archived_wal=frozenset({"000000010000000000000009"}),
    )

    message = _execute_expected_repository_failure(fake)

    assert "unable to find required WAL segment 00000001000000000000000A" in message
    assert fake.selected_backup == "2026-09-05 11:59:00+00"
    assert fake.wal_lookups == ["00000001000000000000000A"]


def test_diagnostic_redacts_quoted_credential_process_json() -> None:
    secret_key = "not-configured-secret-key"  # secret-scan: allow
    non_iqo_token = "FwoGZXIvYXdzEXAMPLE-not-an-iqo-token"  # secret-scan: allow
    stderr = json.dumps(
        {
            "Version": 1,
            "AccessKeyId": "not-sensitive-for-this-test",  # secret-scan: allow
            "SecretAccessKey": secret_key,  # secret-scan: allow
            "SessionToken": non_iqo_token,  # secret-scan: allow
            "Expiration": "2026-09-08T20:00:00Z",
        },
        separators=(",", ":"),
    )
    error = subprocess.CalledProcessError(1, ("credential-process",), stderr=stderr)

    diagnostic = recovery._redacted_diagnostic(error, {})

    assert '"SecretAccessKey":"[REDACTED]"' in diagnostic  # secret-scan: allow
    assert '"SessionToken":"[REDACTED]"' in diagnostic  # secret-scan: allow
    assert '"Expiration":"2026-09-08T20:00:00Z"' in diagnostic
    assert secret_key not in diagnostic
    assert non_iqo_token not in diagnostic


class _FakeDrillOperations:
    def __init__(self, fail_at: str | None = None) -> None:
        self.fail_at = fail_at
        self.calls: list[str] = []
        self.before = datetime(2026, 9, 9, 12, 0, 0, tzinfo=UTC)
        self.target = self.before + timedelta(seconds=2)
        self.after = self.target + timedelta(seconds=1)

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if self.fail_at == name:
            raise recovery.RecoveryError(f"{name} refused")

    def preflight(self, _environ) -> None:
        self._call("preflight")

    def insert_marker(self, _marker, phase):
        self._call(phase)
        return self.before if phase == "before" else self.after

    def database_now(self):
        self._call("target")
        return self.target

    def archive_marker_wal(self, _environ) -> None:
        self._call("archive_marker")

    def restore(self, **_kwargs) -> None:
        self._call("restore")

    def start_postgres(self, **_kwargs) -> None:
        self._call("start_postgres")

    def validate_postgres(self, **_kwargs) -> None:
        self._call("validate_postgres")

    def start_polaris(self, **_kwargs) -> None:
        self._call("start_polaris")

    def validate_polaris(self, **_kwargs) -> None:
        self._call("validate_polaris")

    def validate_catalog(self, **_kwargs):
        self._call("validate_catalog")
        return {"status": "pass", "counts": {"validatedTables": 25}}

    def cleanup_marker(self, _marker) -> None:
        self._call("cleanup")

    def archive_cleanup_wal(self, _environ) -> None:
        self._call("archive_cleanup")


def test_timed_drill_state_machine_orders_effects_and_measures_only_restore_path() -> None:
    operations = _FakeDrillOperations()
    times = iter((100.0, 160.5))

    result = recovery.orchestrate_timed_drill(
        operations=operations,
        environ=_BACKUP_ENV,
        monotonic=lambda: next(times),
        token_factory=lambda: "abcdef1234567890",
    )

    assert operations.calls == [
        "preflight",
        "before",
        "target",
        "after",
        "archive_marker",
        "restore",
        "start_postgres",
        "validate_postgres",
        "start_polaris",
        "validate_polaris",
        "validate_catalog",
        "cleanup",
        "archive_cleanup",
    ]
    assert result["achieved_rpo_seconds"] == 2
    assert result["achieved_rto_seconds"] == 60.5
    assert result["resources"]["preserved"] is True
    assert result["catalog"]["counts"]["validatedTables"] == 25
    assert result["cutover"] == "not_performed"


@pytest.mark.parametrize(
    "failure",
    (
        "restore",
        "start_postgres",
        "validate_postgres",
        "start_polaris",
        "validate_polaris",
        "validate_catalog",
    ),
)
def test_timed_drill_failure_cleans_marker_and_preserves_primary_stage(failure: str) -> None:
    operations = _FakeDrillOperations(fail_at=failure)

    with pytest.raises(recovery.RecoveryError, match=f"{failure} refused"):
        recovery.orchestrate_timed_drill(
            operations=operations,
            environ=_BACKUP_ENV,
            monotonic=lambda: 100.0,
            token_factory=lambda: "abcdef1234567890",
        )

    assert operations.calls[-2:] == ["cleanup", "archive_cleanup"]
    assert "volume rm" not in " ".join(operations.calls)


def test_timed_drill_preserves_primary_error_when_cleanup_fails() -> None:
    operations = _FakeDrillOperations(fail_at="restore")
    original_cleanup = operations.cleanup_marker

    def failed_cleanup(marker):
        original_cleanup(marker)
        raise RuntimeError("unsafe detail")

    operations.cleanup_marker = failed_cleanup
    with pytest.raises(recovery.RecoveryError, match="failed during restore.*cleanup also failed"):
        recovery.orchestrate_timed_drill(
            operations=operations,
            environ=_BACKUP_ENV,
            monotonic=lambda: 100.0,
            token_factory=lambda: "abcdef1234567890",
        )


def test_timed_drill_refuses_unbracketed_target_before_restore() -> None:
    operations = _FakeDrillOperations()
    operations.target = operations.after

    with pytest.raises(recovery.RecoveryError, match="do not bracket"):
        recovery.orchestrate_timed_drill(
            operations=operations,
            environ=_BACKUP_ENV,
            monotonic=lambda: 100.0,
            token_factory=lambda: "abcdef1234567890",
        )

    assert "restore" not in operations.calls
    assert operations.calls[-2:] == ["cleanup", "archive_cleanup"]


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
        "PGBACKREST_REPO1_CIPHER_PASS",
        "PGBACKREST_REPO1_S3_KEY",
        "PGBACKREST_REPO1_S3_KEY_SECRET",
        "PGBACKREST_REPO1_S3_TOKEN",
    ),
)
def test_readiness_gate_rejects_missing_backup_secret(missing_name: str) -> None:
    env = {name: value for name, value in _BACKUP_ENV.items() if name != missing_name}
    with patch.dict(readiness.os.environ, env, clear=True):
        with pytest.raises(readiness.ReadinessError, match=missing_name) as error:
            readiness.ensure_catalog_backup_ready()
    assert all(value not in str(error.value) for value in env.values())


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


def _backup_info(*backups: dict, status_code: int = 0) -> str:
    return json.dumps(
        [{"name": "polaris", "status": {"code": status_code}, "backup": list(backups)}]
    )


def _backup(label: str, backup_type: str, stopped_at: datetime) -> dict:
    return {
        "label": label,
        "type": backup_type,
        "timestamp": {"stop": int(stopped_at.timestamp())},
        "error": False,
    }


def test_readiness_gate_checks_wal_and_creates_initial_backup() -> None:
    now = datetime(2026, 9, 4, tzinfo=UTC)
    calls: list[tuple[str, ...]] = []
    info_results = iter(
        [_backup_info(status_code=2), _backup_info(_backup("new-full", "full", now))]
    )

    def runner(command):
        calls.append(tuple(command))
        stdout = next(info_results) if command[-1] == "info" else ""
        return Mock(stdout=stdout, returncode=0)

    with patch.dict(readiness.os.environ, _BACKUP_ENV, clear=True):
        readiness.ensure_catalog_backup_ready(runner=runner, now=now)
    assert [call[-1] for call in calls] == [
        "polaris",
        "stanza-create",
        "check",
        "info",
        "backup",
        "info",
    ]
    assert "--type=full" in calls[4]
    assert calls[2] == (readiness._PGBACKREST, "--stanza=polaris", "check")


def test_readiness_gate_skips_current_backup() -> None:
    now = datetime(2026, 9, 4, tzinfo=UTC)
    calls: list[tuple[str, ...]] = []

    def runner(command):
        calls.append(tuple(command))
        stdout = _backup_info(_backup("current", "full", now - timedelta(hours=23)))
        return Mock(stdout=stdout if command[-1] == "info" else "", returncode=0)

    with patch.dict(readiness.os.environ, _BACKUP_ENV, clear=True):
        readiness.ensure_catalog_backup_ready(runner=runner, now=now)

    assert "backup" not in [call[-1] for call in calls]


@pytest.mark.parametrize(
    ("full_age", "latest_age", "expected"),
    [
        (timedelta(days=7), timedelta(hours=1), "full"),
        (timedelta(days=6), timedelta(days=1), "diff"),
        (timedelta(days=6), timedelta(hours=23, minutes=59), None),
    ],
)
def test_backup_cadence_boundaries(full_age, latest_age, expected) -> None:
    now = datetime(2026, 9, 4, tzinfo=UTC)
    backups = [
        readiness.Backup("full", "full", now - full_age),
        readiness.Backup("latest", "diff", now - latest_age),
    ]
    assert readiness._required_backup_type(backups, now) == expected


def test_readiness_gate_rejects_malformed_backup_metadata() -> None:
    malformed = _backup_info({"label": "broken", "type": "full", "timestamp": {}})

    def runner(command):
        return Mock(stdout=malformed if command[-1] == "info" else "", returncode=0)

    with patch.dict(readiness.os.environ, _BACKUP_ENV, clear=True):
        with pytest.raises(readiness.ReadinessError, match="invalid label, type, or timestamp"):
            readiness.ensure_catalog_backup_ready(runner=runner)


def test_readiness_gate_requests_and_verifies_differential_backup() -> None:
    now = datetime(2026, 9, 4, tzinfo=UTC)
    full = _backup("recent-full", "full", now - timedelta(days=2))
    old_diff = _backup("old-diff", "diff", now - timedelta(days=1))
    new_diff = _backup("new-diff", "diff", now)
    info_results = iter([_backup_info(full, old_diff), _backup_info(full, old_diff, new_diff)])
    calls: list[tuple[str, ...]] = []

    def runner(command):
        calls.append(tuple(command))
        return Mock(stdout=next(info_results) if command[-1] == "info" else "", returncode=0)

    with patch.dict(readiness.os.environ, _BACKUP_ENV, clear=True):
        readiness.ensure_catalog_backup_ready(runner=runner, now=now)

    assert "--type=diff" in calls[4]


def test_readiness_gate_requires_fresh_requested_backup() -> None:
    now = datetime(2026, 9, 4, tzinfo=UTC)
    old = _backup("old-full", "full", now - timedelta(days=8))
    info_results = iter([_backup_info(old), _backup_info(old)])

    def runner(command):
        return Mock(stdout=next(info_results) if command[-1] == "info" else "", returncode=0)

    with patch.dict(readiness.os.environ, _BACKUP_ENV, clear=True):
        with pytest.raises(readiness.ReadinessError, match="new successful full"):
            readiness.ensure_catalog_backup_ready(runner=runner, now=now)


def test_pgbackrest_contract_has_fail_closed_gate_archive_and_retention() -> None:
    config = (ROOT / "infra/recovery/pgbackrest.conf.example").read_text()
    compose = (ROOT / "compose.iceberg.yml").read_text()
    dockerfile = (ROOT / "scripts/platform/polaris-postgres.Dockerfile").read_text()
    assert "repo1-retention-full=30" in config
    assert "repo1-cipher-type=aes-256-cbc" in config
    assert "pg1-user=polaris" in config
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
    assert compose.count("databox-polaris-postgres:17.6-pgbackrest-2.59.1") == 2
    assert "ARG PGBACKREST_VERSION=2.59.1" in dockerfile
    assert "ca-certificates pgbackrest python3" in dockerfile
    assert "test -s /etc/ssl/certs/ca-certificates.crt" in dockerfile
    assert "DATABOX_AWS_CREDENTIAL_PROCESS" not in compose
    assert "credential-process" not in dockerfile
    assert "awscli" not in dockerfile.lower()
    assert "PGBACKREST_REPO1_S3_TOKEN" in run_pgbackrest


def test_manual_pgbackrest_tasks_run_as_postgres_with_fixed_repository_path() -> None:
    taskfile = (ROOT / "Taskfile.yaml").read_text()
    config = (ROOT / "infra/recovery/pgbackrest.conf.example").read_text()
    assert taskfile.count("exec --user postgres postgres /usr/local/bin/run-pgbackrest") == 4
    assert "repo1-path=/polaris" in config
