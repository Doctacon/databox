#!/usr/bin/env python3
"""Run a renewable AWS credential process and emit pgBackRest environment exports."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import UTC, datetime
from typing import Any

_REQUIRED = ("AccessKeyId", "SecretAccessKey", "SessionToken", "Expiration")


def load_credentials(command: str, *, now: datetime | None = None) -> dict[str, str]:
    if not command.strip():
        raise ValueError("DATABOX_AWS_CREDENTIAL_PROCESS is required")
    result = subprocess.run(shlex.split(command), capture_output=True, text=True, check=True)
    try:
        payload: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("AWS credential process returned invalid JSON") from exc
    missing = [
        key for key in _REQUIRED if not isinstance(payload.get(key), str) or not payload[key]
    ]
    if missing:
        raise ValueError(f"AWS credential process omitted required fields: {', '.join(missing)}")
    expiration = datetime.fromisoformat(payload["Expiration"].replace("Z", "+00:00"))
    if expiration <= (now or datetime.now(UTC)):
        raise ValueError("AWS credential process returned expired credentials")
    return {key: str(payload[key]) for key in _REQUIRED}


def shell_exports(credentials: dict[str, str]) -> str:
    values = {
        "PGBACKREST_REPO1_S3_KEY": credentials["AccessKeyId"],
        "PGBACKREST_REPO1_S3_KEY_SECRET": credentials["SecretAccessKey"],
        "PGBACKREST_REPO1_S3_TOKEN": credentials["SessionToken"],
    }
    return "\n".join(f"export {key}={shlex.quote(value)}" for key, value in values.items())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    args = parser.parse_args()
    print(shell_exports(load_credentials(args.command)))


if __name__ == "__main__":
    main()
