#!/usr/bin/env python3
"""Fail-closed helpers for an isolated Polaris catalog recovery drill."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

_IMAGE = "databox-polaris-postgres:17.6-pgbackrest-2.59.1"
_ACTIVE_VOLUME = "databox_polaris_postgres"
_DATA_PATH = "/var/lib/postgresql/data"
_VOLUME_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]+$")
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


class RecoveryError(RuntimeError):
    """The requested isolated recovery operation is unsafe or unavailable."""


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


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
            f"--target={recover_to.isoformat().replace('+00:00', 'Z')}",
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
        try:
            runner(("docker", "volume", "create", target_volume))
            for command in commands:
                runner(command)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RecoveryError(
                "isolated catalog restore failed; the recovery volume was preserved for inspection"
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
