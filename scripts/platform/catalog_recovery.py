#!/usr/bin/env python3
"""Fail-closed helpers for an isolated Polaris catalog recovery drill."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

_IMAGE = "databox-polaris-postgres:17.6-pgbackrest-2.59.1"
_ACTIVE_VOLUME = "databox_polaris_postgres"
_DATA_PATH = "/var/lib/postgresql/data"
_VOLUME_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]+$")
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
Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
InteractiveRunner = Callable[..., subprocess.CompletedProcess[str]]
TokenFactory = Callable[[], str]

_OPERATOR_PROFILE = "databox-recovery-operator"
_BACKUP_ROLE_PROFILE = "databox-polaris-catalog-backup"


class RecoveryError(RuntimeError):
    """The requested isolated recovery operation is unsafe or unavailable."""


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True, errors="replace")


def _redacted_diagnostic(
    exc: OSError | subprocess.CalledProcessError, environ: Mapping[str, str]
) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        parts = [
            part.strip()
            for part in (exc.stderr, exc.stdout)
            if isinstance(part, str) and part.strip()
        ]
        diagnostic = "\n".join(parts)
    else:
        diagnostic = str(exc)
    for name in _BACKUP_ENV:
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
        exported = runner(export_command, check=False, capture_output=True, text=True)
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
        expires_at = recovery_target(credential["Expiration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RecoveryError("backup-role credential export returned an invalid response") from exc
    if not all(
        isinstance(value, str) and value for value in (access_key, secret_key, session_token)
    ):
        raise RecoveryError("backup-role credential export returned an incomplete session")
    if expires_at <= now().astimezone(UTC):
        raise RecoveryError("backup-role credential export returned an expired session")

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
            f"--target={recover_to.astimezone(UTC).strftime('%Y-%m-%d %H:%M:%S+00')}",
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


def drill_result(started: datetime, recovered_to: datetime, finished: datetime) -> dict[str, Any]:
    return {
        "started_at": started.astimezone(UTC).isoformat(),
        "finished_at": finished.astimezone(UTC).isoformat(),
        "recovered_to": recovered_to.astimezone(UTC).isoformat(),
        "achieved_rpo_seconds": max(0, int((started - recovered_to).total_seconds())),
        "achieved_rto_seconds": max(0, int((finished - started).total_seconds())),
        "objectives_proven": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-volume", required=True)
    parser.add_argument("--active-volume", default=_ACTIVE_VOLUME)
    parser.add_argument("--recover-to", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
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


if __name__ == "__main__":
    raise SystemExit(main())
