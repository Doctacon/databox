#!/usr/bin/env python3
"""Fail-closed helpers for an isolated Polaris catalog recovery drill."""

from __future__ import annotations

import argparse
import json
import os
import re
import runpy
import secrets
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple, Protocol

from dotenv import dotenv_values

_IMAGE = "databox-polaris-postgres:17.6-pgbackrest-2.59.1"
_ACTIVE_VOLUME = "databox_polaris_postgres"
_DATA_PATH = "/var/lib/postgresql/data"
_VOLUME_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]+$")
_DRILL_MARKER = re.compile(r"^databox_recovery_drill_[a-z0-9]{12,16}$")
_OWNERSHIP_LABEL = "com.databox.catalog-recovery.owner"
_DIAGNOSTIC_LIMIT = 2_000
_AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_AWS_SESSION_TOKEN = re.compile(r"\bIQoJb3JpZ2luX2Vj[A-Za-z0-9/+=]{20,}\b")
_JSON_AWS_SECRET = re.compile(r'(?i)("(?:SecretAccessKey|SessionToken)"\s*:\s*)"[^"]*"')
_LABELED_AWS_SECRET = re.compile(
    r"(?i)((?:aws[_-]?)?(?:secret[_-]?access[_-]?key|session[_-]?token)|"
    r"secretAccessKey|sessionToken)(\s*[:=]\s*)([^\s,}]+)"
)
_BACKUP_ENV = (
    "PGBACKREST_REPO1_CIPHER_PASS",
    "PGBACKREST_REPO1_S3_KEY",
    "PGBACKREST_REPO1_S3_KEY_SECRET",
    "PGBACKREST_REPO1_S3_TOKEN",
    "PGBACKREST_REPO1_S3_BUCKET",
    "PGBACKREST_REPO1_S3_REGION",
    "PGBACKREST_REPO1_S3_ENDPOINT",
)
_SECRET_ENV = (
    "PGBACKREST_REPO1_CIPHER_PASS",
    "PGBACKREST_REPO1_S3_KEY",
    "PGBACKREST_REPO1_S3_KEY_SECRET",
    "PGBACKREST_REPO1_S3_TOKEN",
    "DATABOX_POLARIS_POSTGRES_PASSWORD",
    "DATABOX_POLARIS_CLIENT_SECRET",
    "DATABOX_AWS_ACCESS_KEY_ID",
    "DATABOX_AWS_SECRET_ACCESS_KEY",
    "DATABOX_AWS_SESSION_TOKEN",
    "QUARKUS_DATASOURCE_PASSWORD",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
)
_COMPOSE_PROJECT = "databox-iceberg"
_COMPOSE_NETWORK = f"{_COMPOSE_PROJECT}_default"
_ACTIVE_PORTS: dict[str, dict[str, list[dict[str, str]]]] = {
    "postgres": {},
    "polaris": {
        "8181/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8181"}],
        "8182/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8182"}],
    },
}
Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
InteractiveRunner = Callable[..., subprocess.CompletedProcess[str]]
TokenFactory = Callable[[], str]
MonotonicClock = Callable[[], float]

_OPERATOR_PROFILE = "databox-recovery-operator"
_BACKUP_ROLE_PROFILE = "databox-polaris-catalog-backup"
_ACTIVE_POSTGRES = "databox-iceberg-postgres-1"
_ACTIVE_POLARIS = "databox-iceberg-polaris-1"
_POLARIS_IMAGE = "apache/polaris:1.7.0"
_RECOVERY_VALIDATION_LABEL = "com.databox.catalog-recovery.validation"
_ROOT = Path(__file__).resolve().parents[2]
_VALIDATOR = _ROOT / "scripts/platform/catalog_recovery_validate.py"
_MINIMUM_CREDENTIAL_LIFETIME = timedelta(minutes=15)
_RPO_OBJECTIVE_SECONDS = 300.0
_RTO_OBJECTIVE_SECONDS = 3600.0


def _resolve_source_revision(requested: str) -> str:
    namespace = runpy.run_path(str(_VALIDATOR), run_name="catalog_recovery_validator")
    resolver = namespace.get("resolve_source_revision")
    if not callable(resolver):
        raise RecoveryError("catalog validator source-revision contract is unavailable")
    try:
        resolved = resolver(requested)
    except Exception as exc:
        raise RecoveryError("source revision failed canonical registry validation") from exc
    if not isinstance(resolved, str):
        raise RecoveryError("source revision failed canonical registry validation")
    return resolved


class RecoveryError(RuntimeError):
    """The requested isolated recovery operation is unsafe or unavailable."""


class DrillOperations(Protocol):
    """Security-bounded effects required by the timed drill state machine."""

    def preflight(self, resources: DrillResources, environ: Mapping[str, str]) -> None: ...

    def insert_marker(self, marker: str, phase: str) -> datetime: ...

    def database_now(self) -> datetime: ...

    def archive_marker_wal(self, environ: Mapping[str, str]) -> None: ...

    def restore(self, *, volume: str, recover_to: datetime, environ: Mapping[str, str]) -> None: ...

    def start_postgres(self, *, container: str, network: str, volume: str) -> None: ...

    def validate_postgres(self, *, container: str, marker: str) -> None: ...

    def restart_postgres_without_credentials(self, *, container: str) -> None: ...

    def quiesce_postgres(self) -> None: ...

    def start_polaris(self, *, container: str, network: str) -> None: ...

    def validate_polaris(self, *, container: str) -> None: ...

    def validate_catalog(self, *, container: str, recover_to: datetime) -> Mapping[str, Any]: ...

    def quiesce_polaris(self) -> None: ...

    def cleanup_marker(self, marker: str) -> None: ...

    def archive_cleanup_wal(self, environ: Mapping[str, str]) -> None: ...


class DrillResources(NamedTuple):
    marker: str
    volume: str
    network: str
    postgres_container: str
    polaris_container: str


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True, errors="replace")


def _redacted_diagnostic(exc: BaseException, environ: Mapping[str, str]) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        parts = [
            part.strip()
            for part in (exc.stderr, exc.stdout)
            if isinstance(part, str) and part.strip()
        ]
        diagnostic = "\n".join(parts)
    else:
        diagnostic = str(exc)
    for name in _SECRET_ENV:
        value = environ.get(name, "")
        if value:
            diagnostic = diagnostic.replace(value, "[REDACTED]")
    diagnostic = _AWS_ACCESS_KEY.sub("[REDACTED-AWS-ACCESS-KEY]", diagnostic)
    diagnostic = _AWS_SESSION_TOKEN.sub("[REDACTED-AWS-SESSION-TOKEN]", diagnostic)
    diagnostic = _JSON_AWS_SECRET.sub(r'\1"[REDACTED]"', diagnostic)
    diagnostic = _LABELED_AWS_SECRET.sub(r"\1\2[REDACTED]", diagnostic)
    if not diagnostic:
        diagnostic = "child process returned no diagnostic output"
    if len(diagnostic) > _DIAGNOSTIC_LIMIT:
        diagnostic = "[truncated]\n" + diagnostic[-_DIAGNOSTIC_LIMIT:]
    return diagnostic


def _report_diagnostic(exc: BaseException, environ: Mapping[str, str]) -> str:
    diagnostic = _redacted_diagnostic(exc, environ)
    limit = 500
    return diagnostic if len(diagnostic) <= limit else "[truncated]\n" + diagnostic[-limit:]


def _new_ownership_token() -> str:
    return secrets.token_urlsafe(32)


def acquire_backup_role_environment(
    *,
    environ: Mapping[str, str],
    runner: InteractiveRunner = subprocess.run,
    stdin_isatty: bool | None = None,
    stderr_isatty: bool | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    operator_profile: str = _OPERATOR_PROFILE,
    backup_role_profile: str = _BACKUP_ROLE_PROFILE,
) -> dict[str, str]:
    """Obtain MFA-issued pgBackRest credentials without persisting or printing them.

    AWS login and MFA remain attached to the operator terminal. Only the role
    export's stdout is captured, parsed, and returned in process memory.
    """
    input_tty = sys.stdin.isatty() if stdin_isatty is None else stdin_isatty
    error_tty = sys.stderr.isatty() if stderr_isatty is None else stderr_isatty
    if not input_tty or not error_tty:
        raise RecoveryError("interactive catalog drill requires an operator TTY")

    login_command = ("aws", "login", "--remote", "--profile", operator_profile)
    export_command = (
        "aws",
        "configure",
        "export-credentials",
        "--profile",
        backup_role_profile,
        "--format",
        "process",
    )
    try:
        login = runner(login_command, check=False, text=True)
    except OSError as exc:
        raise RecoveryError("unable to invoke interactive AWS operator login") from exc
    if login.returncode != 0:
        raise RecoveryError("interactive AWS operator login failed")

    try:
        exported = runner(
            export_command,
            check=False,
            stdout=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise RecoveryError("unable to invoke backup-role credential export") from exc
    if exported.returncode != 0:
        diagnostic = _redacted_diagnostic(
            subprocess.CalledProcessError(
                exported.returncode,
                export_command,
                output=exported.stdout,
                stderr=exported.stderr,
            ),
            environ,
        )
        raise RecoveryError(f"backup-role credential export failed: {diagnostic}")

    try:
        credential = json.loads(exported.stdout)
        access_key = credential["AccessKeyId"]
        secret_key = credential["SecretAccessKey"]
        session_token = credential["SessionToken"]
        expiration = credential["Expiration"]
        if not isinstance(expiration, str):
            raise RecoveryError("backup-role credential export returned an invalid response")
        expires_at = recovery_target(expiration)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RecoveryError("backup-role credential export returned an invalid response") from exc
    if not all(
        isinstance(value, str) and value for value in (access_key, secret_key, session_token)
    ):
        raise RecoveryError("backup-role credential export returned an incomplete session")
    if expires_at - now().astimezone(UTC) < _MINIMUM_CREDENTIAL_LIFETIME:
        raise RecoveryError("backup-role credential session has less than 15 minutes remaining")

    values = dict(environ)
    values.update(
        {
            "PGBACKREST_REPO1_S3_KEY": access_key,
            "PGBACKREST_REPO1_S3_KEY_SECRET": secret_key,
            "PGBACKREST_REPO1_S3_TOKEN": session_token,
        }
    )
    _require_backup_environment(values)
    return values


def recovery_target(value: str) -> datetime:
    target = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if target.tzinfo is None:
        raise ValueError("Recovery target must include a timezone")
    return target.astimezone(UTC)


def _volume_name(value: str) -> str:
    if not _VOLUME_NAME.fullmatch(value):
        raise ValueError("Docker volume name is invalid")
    return value


def _require_backup_environment(environ: Mapping[str, str]) -> None:
    missing = [name for name in _BACKUP_ENV if not environ.get(name, "").strip()]
    if missing:
        raise RecoveryError("missing catalog recovery settings: " + ", ".join(missing))


def _restore_commands(target_volume: str, recover_to: datetime) -> tuple[tuple[str, ...], ...]:
    mount = f"type=volume,src={target_volume},dst={_DATA_PATH}"
    initialize = (
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--user",
        "root",
        "--mount",
        mount,
        _IMAGE,
        "chown",
        "postgres:postgres",
        _DATA_PATH,
    )
    restore: list[str] = [
        "docker",
        "run",
        "--rm",
        "--network",
        "bridge",
        "--user",
        "postgres",
    ]
    for name in _BACKUP_ENV:
        restore.extend(("--env", name))
    restore.extend(
        (
            "--mount",
            mount,
            _IMAGE,
            "/usr/local/bin/run-pgbackrest",
            "--stanza=polaris",
            "--type=time",
            f"--target={recover_to.astimezone(UTC).strftime('%Y-%m-%d %H:%M:%S.%f+00')}",
            "--target-action=promote",
            "restore",
        )
    )
    return initialize, tuple(restore)


def prepare_or_execute_restore(
    *,
    target_volume: str,
    active_volume: str,
    recover_to: datetime,
    execute: bool,
    environ: Mapping[str, str] | None = None,
    runner: Runner = _run,
    ownership_token_factory: TokenFactory = _new_ownership_token,
) -> dict[str, Any]:
    """Validate and optionally restore into a newly created isolated volume."""
    target_volume = _volume_name(target_volume)
    active_volume = _volume_name(active_volume)
    if target_volume == active_volume:
        raise RecoveryError("Recovery target must not be the active PostgreSQL volume")
    values = os.environ if environ is None else environ
    _require_backup_environment(values)

    try:
        existing = runner(
            ("docker", "volume", "ls", "--quiet", "--filter", f"name=^{target_volume}$")
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RecoveryError("unable to verify that the recovery volume is new") from exc
    if existing.stdout.strip():
        raise RecoveryError("Recovery target volume already exists; choose a new name")

    commands = _restore_commands(target_volume, recover_to)
    if execute:
        ownership_token = ownership_token_factory()
        try:
            runner(
                (
                    "docker",
                    "volume",
                    "create",
                    "--label",
                    f"{_OWNERSHIP_LABEL}={ownership_token}",
                    target_volume,
                )
            )
            ownership = runner(
                (
                    "docker",
                    "volume",
                    "inspect",
                    "--format",
                    f'{{{{ index .Labels "{_OWNERSHIP_LABEL}" }}}}',
                    target_volume,
                )
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RecoveryError(
                "unable to prove ownership of the recovery volume; it was preserved"
            ) from exc
        if ownership.stdout.strip() != ownership_token:
            raise RecoveryError(
                "recovery volume ownership does not match this execution; it was preserved"
            )
        try:
            for command in commands:
                runner(command)
        except (OSError, subprocess.CalledProcessError) as exc:
            diagnostic = _redacted_diagnostic(exc, values)
            raise RecoveryError(
                f"isolated catalog restore failed for target volume {target_volume}; "
                f"the volume was preserved for inspection: {diagnostic}"
            ) from exc

    return {
        "target_volume": target_volume,
        "active_volume": active_volume,
        "recover_to": recover_to.isoformat(),
        "mode": "execute" if execute else "prepare-only",
        "writers": "disabled",
        "bootstrap": "forbidden",
        "authoritative_backup_archive": "disabled",
        "target_preserved": True,
        "next": "start reviewed isolated services; do not cut over",
    }


def _drill_resources(token: str) -> DrillResources:
    suffix = re.sub(r"[^a-z0-9]", "", token.lower())[:16]
    if len(suffix) < 12:
        raise RecoveryError("unable to generate unique drill resource names")
    return DrillResources(
        marker=f"databox_recovery_drill_{suffix}",
        volume=f"databox_polaris_recovery_drill_{suffix}",
        network=f"databox_polaris_recovery_drill_{suffix}",
        postgres_container=f"databox-polaris-recovery-drill-postgres-{suffix}",
        polaris_container=f"databox-polaris-recovery-drill-polaris-{suffix}",
    )


def orchestrate_timed_drill(
    *,
    operations: DrillOperations,
    environ: Mapping[str, str],
    monotonic: MonotonicClock,
    token_factory: TokenFactory = _new_ownership_token,
    started_at: float | None = None,
) -> dict[str, Any]:
    """Run the ordered drill state machine around injected, reviewed effects."""
    resources = _drill_resources(token_factory())
    started = monotonic() if started_at is None else started_at
    stage = "preflight"
    marker_cleanup_required = False
    postgres_start_attempted = False
    postgres_may_hold_secrets = False
    polaris_may_hold_secrets = False
    primary: str | None = None
    result: dict[str, Any] | None = None
    cleanup = {"marker_drop": "not-required", "wal_archive": "not-required"}
    postgres_quiesce = "not-required"
    polaris_quiesce = "not-required"
    try:
        operations.preflight(resources, environ)
        stage = "before marker"
        marker_cleanup_required = True
        before_at = operations.insert_marker(resources.marker, "before")
        stage = "target selection"
        recover_to = operations.database_now()
        stage = "after marker"
        after_at = operations.insert_marker(resources.marker, "after")
        if not before_at <= recover_to < after_at:
            raise RecoveryError("marker timestamps do not bracket the selected recovery target")
        stage = "marker WAL archive"
        operations.archive_marker_wal(environ)
        stage = "restore"
        operations.restore(volume=resources.volume, recover_to=recover_to, environ=environ)
        stage = "isolated PostgreSQL recovery startup"
        postgres_start_attempted = True
        postgres_may_hold_secrets = True
        operations.start_postgres(
            container=resources.postgres_container,
            network=resources.network,
            volume=resources.volume,
        )
        stage = "isolated PostgreSQL recovery validation"
        operations.validate_postgres(
            container=resources.postgres_container, marker=resources.marker
        )
        stage = "isolated PostgreSQL credential scrub restart"
        operations.restart_postgres_without_credentials(container=resources.postgres_container)
        postgres_may_hold_secrets = False
        stage = "isolated PostgreSQL post-scrub validation"
        operations.validate_postgres(
            container=resources.postgres_container, marker=resources.marker
        )
        stage = "isolated Polaris startup"
        polaris_may_hold_secrets = True
        operations.start_polaris(container=resources.polaris_container, network=resources.network)
        stage = "isolated Polaris validation"
        operations.validate_polaris(container=resources.polaris_container)
        stage = "catalog validation"
        catalog = dict(
            operations.validate_catalog(
                container=resources.polaris_container, recover_to=recover_to
            )
        )
        if catalog.get("status") != "pass":
            raise RecoveryError("registry-derived catalog validation did not pass")
        finished = monotonic()
        rpo = max(0.0, (recover_to - before_at).total_seconds())
        rto = max(0.0, finished - started)
        objectives = {
            "rpo": {"limit_seconds": _RPO_OBJECTIVE_SECONDS, "met": rpo <= _RPO_OBJECTIVE_SECONDS},
            "rto": {"limit_seconds": _RTO_OBJECTIVE_SECONDS, "met": rto <= _RTO_OBJECTIVE_SECONDS},
        }
        result = {
            "status": "pass" if all(item["met"] for item in objectives.values()) else "fail",
            "recover_to": recover_to.astimezone(UTC).isoformat(),
            "before_marker_at": before_at.astimezone(UTC).isoformat(),
            "after_marker_at": after_at.astimezone(UTC).isoformat(),
            "achieved_rpo_seconds": rpo,
            "achieved_rto_seconds": rto,
            "objectives": objectives,
            "resources": {
                "marker": resources.marker,
                "volume": resources.volume,
                "network": resources.network,
                "postgres_container": resources.postgres_container,
                "polaris_container": resources.polaris_container,
                "preserved": True,
            },
            "catalog": catalog,
            "cutover": "not_performed",
        }
    except Exception as exc:
        primary = f"timed catalog drill failed during {stage}: {_report_diagnostic(exc, environ)}"
    finally:
        if polaris_may_hold_secrets:
            try:
                operations.quiesce_polaris()
                polaris_quiesce = "stopped"
            except Exception as exc:
                polaris_quiesce = "failed: " + _report_diagnostic(exc, environ)
        objective_failed = result is not None and result.get("status") != "pass"
        if postgres_may_hold_secrets or (
            postgres_start_attempted and (primary is not None or objective_failed)
        ):
            try:
                operations.quiesce_postgres()
                postgres_quiesce = "stopped"
            except Exception as exc:
                postgres_quiesce = "failed: " + _report_diagnostic(exc, environ)
        if marker_cleanup_required:
            try:
                operations.cleanup_marker(resources.marker)
                cleanup["marker_drop"] = "complete"
            except Exception as exc:
                cleanup["marker_drop"] = "failed: " + _report_diagnostic(exc, environ)
            try:
                operations.archive_cleanup_wal(environ)
                cleanup["wal_archive"] = "complete"
            except Exception as exc:
                cleanup["wal_archive"] = "failed: " + _report_diagnostic(exc, environ)
    cleanup_failed = any(value.startswith("failed:") for value in cleanup.values())
    quiesce_failed = postgres_quiesce.startswith("failed:") or polaris_quiesce.startswith("failed:")
    if result is not None:
        result["cleanup"] = cleanup
        result["postgres_quiesce"] = postgres_quiesce
        result["polaris_quiesce"] = polaris_quiesce
    if primary is not None or cleanup_failed or quiesce_failed:
        details = primary or "timed catalog drill validation completed"
        resource_text = dict(zip(DrillResources._fields, resources, strict=True))
        message = (
            f"{details}; resources={resource_text}; cleanup={cleanup}; "
            f"postgres_quiesce={postgres_quiesce}; polaris_quiesce={polaris_quiesce}; "
            "recovery artifacts were preserved"
        )
        raise RecoveryError(_redacted_diagnostic(RecoveryError(message), environ))
    if result is None:
        raise RecoveryError("timed catalog drill produced no result")
    return result


class DockerDrillOperations:
    """Concrete, no-port drill effects composed from existing recovery tools."""

    def __init__(
        self,
        *,
        catalog: str,
        source_revision: str,
        environ: Mapping[str, str],
        runner: InteractiveRunner = subprocess.run,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not _VOLUME_NAME.fullmatch(catalog):
            raise RecoveryError("invalid Polaris catalog name")
        self.catalog = catalog
        self.source_revision = source_revision
        self.environ = dict(environ)
        self.runner = runner
        self.sleeper = sleeper
        self._postgres_container: str | None = None
        self._polaris_container: str | None = None

    def _run(
        self,
        command: Sequence[str],
        *,
        environ: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            completed = self.runner(
                list(command),
                check=False,
                capture_output=True,
                text=True,
                env=dict(environ) if environ is not None else None,
            )
        except OSError as exc:
            raise RecoveryError("unable to invoke drill child process") from exc
        if completed.returncode != 0:
            raise RecoveryError(
                "drill child process failed: "
                + _redacted_diagnostic(
                    subprocess.CalledProcessError(
                        completed.returncode,
                        command,
                        output=completed.stdout,
                        stderr=completed.stderr,
                    ),
                    environ or self.environ,
                )
            )
        return completed

    def _docker_json(self, container: str) -> Mapping[str, Any]:
        output = self._run(
            (
                "docker",
                "inspect",
                "--format",
                '{"running":{{json .State.Running}},"health":{{json .State.Health.Status}},'
                '"image":{{json .Config.Image}},"ports":{{json .HostConfig.PortBindings}},'
                '"mounts":{{json .Mounts}},"labels":{{json .Config.Labels}},'
                '"networks":{{json .NetworkSettings.Networks}}}',
                container,
            )
        ).stdout
        try:
            value = json.loads(output)
        except json.JSONDecodeError as exc:
            raise RecoveryError("Docker returned invalid active-service state") from exc
        if not isinstance(value, dict):
            raise RecoveryError("Docker returned invalid active-service state")
        return value

    def _assert_absent(self, kind: str, name: str) -> None:
        command = (
            ("docker", kind, "inspect", name)
            if kind != "container"
            else (
                "docker",
                "container",
                "inspect",
                name,
            )
        )
        completed = self.runner(
            list(command), check=False, capture_output=True, text=True, env=None
        )
        if completed.returncode == 0:
            raise RecoveryError(f"drill {kind} name already exists: {name}")
        diagnostic = "\n".join(
            value for value in (completed.stderr, completed.stdout) if isinstance(value, str)
        )
        if (
            completed.returncode != 1
            or name not in diagnostic
            or not re.search(r"(?i)(no such|not found)", diagnostic)
        ):
            raise RecoveryError(f"unable to prove drill {kind} name is absent")

    def preflight(self, resources: DrillResources, environ: Mapping[str, str]) -> None:
        self.source_revision = _resolve_source_revision(self.source_revision)
        _require_backup_environment(environ)
        postgres = self._docker_json(_ACTIVE_POSTGRES)
        polaris = self._docker_json(_ACTIVE_POLARIS)
        if (
            postgres.get("running") is not True
            or postgres.get("health") != "healthy"
            or postgres.get("image") != _IMAGE
            or polaris.get("running") is not True
            or polaris.get("health") != "healthy"
            or polaris.get("image") != _POLARIS_IMAGE
        ):
            raise RecoveryError("active PostgreSQL and Polaris must be healthy and pinned")
        for service, state in (("postgres", postgres), ("polaris", polaris)):
            ports = state.get("ports")
            labels = state.get("labels")
            networks = state.get("networks")
            if (
                not isinstance(ports, dict)
                or ports != _ACTIVE_PORTS[service]
                or not isinstance(labels, dict)
                or labels.get("com.docker.compose.project") != _COMPOSE_PROJECT
                or labels.get("com.docker.compose.service") != service
                or not isinstance(networks, dict)
                or set(networks) != {_COMPOSE_NETWORK}
            ):
                raise RecoveryError(
                    "active services must have exact loopback bindings and Compose network"
                )
        mounts = postgres.get("mounts")
        if not isinstance(mounts, list) or not any(
            isinstance(item, dict)
            and item.get("Name") == _ACTIVE_VOLUME
            and item.get("Destination") == _DATA_PATH
            for item in mounts
        ):
            raise RecoveryError("active PostgreSQL volume identity is invalid")
        for name in (resources.postgres_container, resources.polaris_container):
            self._assert_absent("container", name)
        self._assert_absent("network", resources.network)
        self._assert_absent("volume", resources.volume)
        info = (
            "docker",
            "exec",
            "--user",
            "postgres",
            *sum((("--env", name) for name in _BACKUP_ENV), ()),
            _ACTIVE_POSTGRES,
            "/usr/local/bin/run-pgbackrest",
            "--stanza=polaris",
            "--output=json",
            "info",
        )
        response = self._run(info, environ=environ)
        try:
            repository = json.loads(response.stdout)
        except json.JSONDecodeError as exc:
            raise RecoveryError("pgBackRest repository info is invalid") from exc
        if not isinstance(repository, list) or not repository:
            raise RecoveryError("pgBackRest repository has no stanza metadata")
        stanza = repository[0]
        if (
            not isinstance(stanza, dict)
            or stanza.get("name") != "polaris"
            or not isinstance(stanza.get("backup"), list)
            or not stanza["backup"]
            or not isinstance(stanza.get("status"), dict)
            or stanza["status"].get("code") != 0
        ):
            raise RecoveryError("pgBackRest repository has no successful Polaris backup")

    @staticmethod
    def _quoted_marker(marker: str) -> str:
        if not re.fullmatch(r"[a-z0-9_]+", marker):
            raise RecoveryError("invalid generated marker identifier")
        return f'public."{marker}"'

    def _active_sql(self, sql: str) -> str:
        return self._run(
            (
                "docker",
                "exec",
                _ACTIVE_POSTGRES,
                "psql",
                "-U",
                "polaris",
                "-d",
                "polaris",
                "-qAtX",
                "-c",
                sql,
            )
        ).stdout.strip()

    def insert_marker(self, marker: str, phase: str) -> datetime:
        table = self._quoted_marker(marker)
        if phase not in {"before", "after"}:
            raise RecoveryError("invalid marker phase")
        prefix = (
            f"CREATE TABLE {table} (phase text PRIMARY KEY, committed_at timestamptz NOT NULL);"
            if phase == "before"
            else ""
        )
        output = self._active_sql(
            prefix
            + f"INSERT INTO {table}(phase, committed_at) VALUES ('{phase}', clock_timestamp()) "
            "RETURNING committed_at;"
        )
        rows = [line.strip() for line in output.splitlines() if line.strip()]
        if len(rows) != 1:
            raise RecoveryError("PostgreSQL returned an invalid marker timestamp")
        try:
            return recovery_target(rows[0])
        except (TypeError, ValueError) as exc:
            raise RecoveryError("PostgreSQL returned an invalid marker timestamp") from exc

    def database_now(self) -> datetime:
        return recovery_target(self._active_sql("SELECT clock_timestamp();"))

    def _archive_wal(self, environ: Mapping[str, str]) -> None:
        segment = self._active_sql("SELECT pg_walfile_name(pg_switch_wal() - 1);")
        if not re.fullmatch(r"[0-9A-F]{24}", segment):
            raise RecoveryError("PostgreSQL returned an invalid WAL segment name")
        command = ["docker", "exec", "--user", "postgres"]
        for name in _BACKUP_ENV:
            command.extend(("--env", name))
        command.extend(
            (
                _ACTIVE_POSTGRES,
                "/usr/local/bin/run-pgbackrest",
                "--stanza=polaris",
                "--no-archive-async",
                "archive-push",
                f"{_DATA_PATH}/pg_wal/{segment}",
            )
        )
        self._run(command, environ=environ)

    def archive_marker_wal(self, environ: Mapping[str, str]) -> None:
        self._archive_wal(environ)

    def restore(self, *, volume: str, recover_to: datetime, environ: Mapping[str, str]) -> None:
        def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
            return self._run(command, environ=environ)

        prepare_or_execute_restore(
            target_volume=volume,
            active_volume=_ACTIVE_VOLUME,
            recover_to=recover_to,
            execute=True,
            environ=environ,
            runner=runner,
        )

    def _wait_exec(self, container: str, command: Sequence[str], description: str) -> None:
        for _ in range(60):
            completed = self.runner(
                ["docker", "exec", container, *command],
                check=False,
                capture_output=True,
                text=True,
                env=None,
            )
            if completed.returncode == 0:
                return
            self.sleeper(1)
        raise RecoveryError(f"{description} did not become ready")

    @staticmethod
    def _postgres_command() -> tuple[str, ...]:
        return ("postgres", "-c", "archive_mode=off", "-c", "listen_addresses=*")

    def _start_postgres_exec(self, container: str, *, environ: Mapping[str, str] | None) -> None:
        command = ["docker", "exec", "--detach", "--user", "postgres"]
        if environ is not None:
            for name in _BACKUP_ENV:
                command.extend(("--env", name))
        command.extend((container, *self._postgres_command()))
        self._run(command, environ=environ)
        self._wait_exec(
            container,
            ("pg_isready", "-U", "polaris", "-d", "polaris"),
            "isolated PostgreSQL",
        )

    def start_postgres(self, *, container: str, network: str, volume: str) -> None:
        self._run(
            (
                "docker",
                "network",
                "create",
                "--label",
                f"{_RECOVERY_VALIDATION_LABEL}=network",
                network,
            )
        )
        # The preserved container configuration is secret-free. PITR credentials
        # exist only in the first detached PostgreSQL process environment.
        self._run(
            (
                "docker",
                "run",
                "--detach",
                "--name",
                container,
                "--label",
                f"{_RECOVERY_VALIDATION_LABEL}=postgres",
                "--network",
                network,
                "--user",
                "postgres",
                "--restart",
                "no",
                "--mount",
                f"type=volume,src={volume},dst={_DATA_PATH}",
                _IMAGE,
                "/bin/sh",
                "-c",
                "while :; do sleep 3600; done",
            )
        )
        self._postgres_container = container
        self._start_postgres_exec(container, environ=self.environ)

    def restart_postgres_without_credentials(self, *, container: str) -> None:
        if self._postgres_container != container:
            raise RecoveryError("isolated PostgreSQL was not started")
        self._run(("docker", "stop", "--time", "10", container))
        self._run(("docker", "start", container))
        self._start_postgres_exec(container, environ=None)

    def quiesce_postgres(self) -> None:
        if self._postgres_container is not None:
            self._run(("docker", "stop", "--time", "10", self._postgres_container))

    def validate_postgres(self, *, container: str, marker: str) -> None:
        table = self._quoted_marker(marker)
        sql = (
            "SELECT pg_is_in_recovery(), current_setting('archive_mode'),"
            "count(*) FILTER (WHERE phase='before'),"
            "count(*) FILTER (WHERE phase='after'),"
            f"count(*) FROM {table};"
        )
        command = (
            "docker",
            "exec",
            container,
            "psql",
            "-U",
            "polaris",
            "-d",
            "polaris",
            "-AtX",
            "-F",
            "|",
            "-c",
            sql,
        )
        for _ in range(120):
            completed = self.runner(
                list(command), check=False, capture_output=True, text=True, env=None
            )
            if completed.returncode == 0 and completed.stdout.strip() == "f|off|1|0|1":
                return
            self.sleeper(1)
        raise RecoveryError("isolated PostgreSQL marker boundary is invalid")

    def start_polaris(self, *, container: str, network: str) -> None:
        if self._postgres_container is None:
            raise RecoveryError("isolated PostgreSQL was not started")
        required = (
            "DATABOX_POLARIS_POSTGRES_PASSWORD",
            "DATABOX_POLARIS_CLIENT_ID",
            "DATABOX_POLARIS_CLIENT_SECRET",
            "DATABOX_AWS_ACCESS_KEY_ID",
            "DATABOX_AWS_SECRET_ACCESS_KEY",
            "DATABOX_AWS_REGION",
        )
        missing = [name for name in required if not self.environ.get(name)]
        if missing:
            raise RecoveryError("missing Polaris drill settings: " + ", ".join(missing))
        polaris_env = dict(self.environ)
        polaris_env.update(
            {
                "POLARIS_PERSISTENCE_TYPE": "relational-jdbc",
                "QUARKUS_DATASOURCE_USERNAME": "polaris",
                "QUARKUS_DATASOURCE_PASSWORD": self.environ["DATABOX_POLARIS_POSTGRES_PASSWORD"],
                "QUARKUS_DATASOURCE_JDBC_URL": f"jdbc:postgresql://{self._postgres_container}:5432/polaris",
                "POLARIS_REALM_CONTEXT_REALMS": "POLARIS",
                "POLARIS_REALM_CONTEXT_REQUIRE_HEADER": "false",
                "AWS_ACCESS_KEY_ID": self.environ["DATABOX_AWS_ACCESS_KEY_ID"],
                "AWS_SECRET_ACCESS_KEY": self.environ["DATABOX_AWS_SECRET_ACCESS_KEY"],
                "AWS_SESSION_TOKEN": self.environ.get("DATABOX_AWS_SESSION_TOKEN", ""),
                "AWS_REGION": self.environ["DATABOX_AWS_REGION"],
            }
        )
        names = (
            "POLARIS_PERSISTENCE_TYPE",
            "POLARIS_REALM_CONTEXT_REALMS",
            "POLARIS_REALM_CONTEXT_REQUIRE_HEADER",
            "QUARKUS_DATASOURCE_USERNAME",
            "QUARKUS_DATASOURCE_PASSWORD",
            "QUARKUS_DATASOURCE_JDBC_URL",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_REGION",
            "DATABOX_POLARIS_CLIENT_ID",
            "DATABOX_POLARIS_CLIENT_SECRET",
        )
        # The preserved container Config is secret-free. Credentials exist only
        # in the detached Polaris child process environment and are erased by stop.
        self._run(
            (
                "docker",
                "run",
                "--detach",
                "--name",
                container,
                "--label",
                f"{_RECOVERY_VALIDATION_LABEL}=polaris",
                "--network",
                network,
                "--restart",
                "no",
                _POLARIS_IMAGE,
                "/bin/sh",
                "-c",
                "while :; do sleep 3600; done",
            )
        )
        self._polaris_container = container
        command = ["docker", "exec", "--detach"]
        for name in names:
            command.extend(("--env", name))
        command.extend((container, "/opt/jboss/container/java/run/run-java.sh"))
        self._run(command, environ=polaris_env)
        self._wait_exec(
            container,
            ("curl", "--fail", "--silent", "http://localhost:8182/q/health/ready"),
            "isolated Polaris",
        )

    def validate_polaris(self, *, container: str) -> None:
        self._wait_exec(
            container,
            ("curl", "--fail", "--silent", "http://localhost:8182/q/health/ready"),
            "isolated Polaris",
        )

    def quiesce_polaris(self) -> None:
        if self._polaris_container is not None:
            self._run(("docker", "stop", "--time", "10", self._polaris_container))

    def validate_catalog(self, *, container: str, recover_to: datetime) -> Mapping[str, Any]:
        validator_environment = {
            key: value for key, value in self.environ.items() if key not in _BACKUP_ENV
        }
        completed = self._run(
            (
                sys.executable,
                str(_VALIDATOR),
                "--polaris-container",
                container,
                "--catalog",
                self.catalog,
                "--recovery-target",
                recover_to.isoformat(),
                "--source-revision",
                self.source_revision,
            ),
            environ=validator_environment,
        )
        try:
            report = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RecoveryError("catalog validator returned invalid JSON") from exc
        counts = report.get("counts") if isinstance(report, dict) else None
        if (
            not isinstance(report, dict)
            or report.get("status") != "pass"
            or not isinstance(counts, dict)
            or not isinstance(counts.get("expectedTables"), int)
            or counts["expectedTables"] <= 0
            or counts.get("validatedTables") != counts["expectedTables"]
            or counts.get("failedTables") != 0
        ):
            raise RecoveryError("catalog validator did not validate all canonical tables")
        return report

    def cleanup_marker(self, marker: str) -> None:
        self._active_sql(f"DROP TABLE IF EXISTS {self._quoted_marker(marker)};")

    def reconcile_marker(self, marker: str) -> None:
        if not _DRILL_MARKER.fullmatch(marker):
            raise RecoveryError("marker is not owned by a timed drill")
        relation = self._active_sql(
            "SELECT n.nspname, c.relkind, pg_get_userbyid(c.relowner) "
            "FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            f"WHERE c.relname = '{marker}';"
        )
        rows = [row.strip() for row in relation.splitlines() if row.strip()]
        if not rows:
            return
        if rows != ["public|r|polaris"]:
            raise RecoveryError("marker relation identity is invalid; no cleanup was performed")
        self._active_sql(f'DROP TABLE public."{marker}";')

    def archive_cleanup_wal(self, environ: Mapping[str, str]) -> None:
        self._archive_wal(environ)


def _environment_from_dotenv() -> dict[str, str]:
    values = {key: value for key, value in dotenv_values(_ROOT / ".env").items() if value}
    values.update(os.environ)
    region = values.get("DATABOX_AWS_REGION", "")
    values.update(
        {
            "PGBACKREST_REPO1_S3_BUCKET": values.get("DATABOX_CATALOG_BACKUP_BUCKET", ""),
            "PGBACKREST_REPO1_S3_REGION": region,
            "PGBACKREST_REPO1_S3_ENDPOINT": f"s3.{region}.amazonaws.com" if region else "",
        }
    )
    return values


def _restore_main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-volume", required=True)
    parser.add_argument("--active-volume", default=_ACTIVE_VOLUME)
    parser.add_argument("--recover-to", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = prepare_or_execute_restore(
            target_volume=args.target_volume,
            active_volume=args.active_volume,
            recover_to=recovery_target(args.recover_to),
            execute=args.execute,
        )
    except (RecoveryError, ValueError) as exc:
        print(f"catalog recovery refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


def _cleanup_marker_main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Reconcile one failed-drill marker")
    parser.add_argument("--marker", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--operator-profile", default=_OPERATOR_PROFILE)
    parser.add_argument("--backup-role-profile", default=_BACKUP_ROLE_PROFILE)
    args = parser.parse_args(argv)
    if not _DRILL_MARKER.fullmatch(args.marker):
        print("catalog recovery refused: marker is not owned by a timed drill", file=sys.stderr)
        return 1
    base = _environment_from_dotenv()
    try:
        environment = acquire_backup_role_environment(
            environ=base,
            operator_profile=args.operator_profile,
            backup_role_profile=args.backup_role_profile,
        )
        operations = DockerDrillOperations(
            catalog=args.catalog,
            source_revision=args.source_revision,
            environ=environment,
        )
        operations.preflight(_drill_resources(_new_ownership_token()), environment)
        operations.reconcile_marker(args.marker)
        operations.archive_cleanup_wal(environment)
    except (RecoveryError, ValueError) as exc:
        print(f"catalog recovery refused: {_redacted_diagnostic(exc, base)}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "pass", "marker": args.marker, "cleanup_wal": "archived"}))
    return 0


def _drill_main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Run the interactive timed catalog drill")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--reconcile-marker")
    parser.add_argument("--operator-profile", default=_OPERATOR_PROFILE)
    parser.add_argument("--backup-role-profile", default=_BACKUP_ROLE_PROFILE)
    args = parser.parse_args(argv)
    if args.reconcile_marker and not _DRILL_MARKER.fullmatch(args.reconcile_marker):
        print("catalog recovery refused: marker is not owned by a timed drill", file=sys.stderr)
        return 1
    started_at = time.monotonic()
    base = _environment_from_dotenv()
    try:
        environment = acquire_backup_role_environment(
            environ=base,
            operator_profile=args.operator_profile,
            backup_role_profile=args.backup_role_profile,
        )
        operations = DockerDrillOperations(
            catalog=args.catalog,
            source_revision=args.source_revision,
            environ=environment,
        )
        if args.reconcile_marker:
            operations.preflight(_drill_resources(_new_ownership_token()), environment)
            operations.reconcile_marker(args.reconcile_marker)
            operations.archive_cleanup_wal(environment)
        result = orchestrate_timed_drill(
            operations=operations,
            environ=environment,
            monotonic=time.monotonic,
            started_at=started_at,
        )
        if args.reconcile_marker:
            result["reconciled_marker"] = args.reconcile_marker
    except (RecoveryError, ValueError) as exc:
        print(f"catalog recovery refused: {_redacted_diagnostic(exc, base)}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result.get("status") == "pass" else 1


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "drill":
        return _drill_main(arguments[1:])
    if arguments and arguments[0] == "cleanup-marker":
        return _cleanup_marker_main(arguments[1:])
    return _restore_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
