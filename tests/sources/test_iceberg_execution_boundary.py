"""Iceberg graph construction is inert; publication requires credentials."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from databox.config.settings import settings
from databox.destinations.iceberg import (
    iceberg_destination,
    require_iceberg_write_credentials,
)
from pydantic import SecretStr

ROOT = Path(__file__).parents[2]
_EMPTY_CREDENTIALS = {
    "DATABOX_ENV_FILE": "/nonexistent-databox-ci.env",
    "DATABOX_QUACK_TOKEN": "",
    "OPENLINEAGE_API_KEY": "",
    "DATABOX_POLARIS_CLIENT_ID": "",
    "DATABOX_POLARIS_CLIENT_SECRET": "",
    "DATABOX_AWS_S3_BUCKET": "",
    "DATABOX_AWS_ACCESS_KEY_ID": "",
    "DATABOX_AWS_SECRET_ACCESS_KEY": "",
    "DATABOX_AWS_SESSION_TOKEN": "",
}


def _credential_free_environment() -> dict[str, str]:
    """Preserve process essentials while overriding every settings credential."""
    return {
        key: value
        for key in ("PATH", "SYSTEMROOT", "WINDIR", "HOME", "TMPDIR", "TEMP", "TMP")
        if (value := os.environ.get(key)) is not None
    } | _EMPTY_CREDENTIALS


def test_definitions_construct_with_explicitly_empty_writer_configuration() -> None:
    """Real source assets are importable without triggering destination I/O."""
    environment = _credential_free_environment()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from databox.orchestration.definitions import defs; "
            "assert defs.resolve_asset_graph().assets_defs",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_source_layout_is_credential_free() -> None:
    environment = _credential_free_environment()
    result = subprocess.run(
        [sys.executable, "scripts/sources/check_source_layout.py"],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("session_token", "expected_token"),
    [("temporary-session-token", "temporary-session-token"), ("", None)],
)
def test_iceberg_destination_uses_normalized_warehouse_prefix_and_optional_session_token(
    session_token: str, expected_token: str | None
) -> None:
    with (
        patch.object(settings, "aws_s3_bucket", "databox-bucket"),
        patch.object(settings, "iceberg_warehouse_prefix", "/warehouse/"),
        patch.object(settings, "aws_access_key_id", SecretStr("access-key")),
        patch.object(settings, "aws_secret_access_key", SecretStr("secret-key")),
        patch.object(settings, "aws_session_token", SecretStr(session_token)),
        patch("databox.destinations.iceberg.dlt.destinations.filesystem") as filesystem,
    ):
        iceberg_destination()

    kwargs = filesystem.call_args.kwargs
    assert kwargs["bucket_url"] == "s3://databox-bucket/warehouse"
    assert kwargs["credentials"]["aws_access_key_id"] == "access-key"
    assert kwargs["credentials"]["aws_secret_access_key"] == "secret-key"
    if expected_token is None:
        assert "aws_session_token" not in kwargs["credentials"]
    else:
        assert kwargs["credentials"]["aws_session_token"] == expected_token


def test_iceberg_execution_requires_writer_credentials_before_publication() -> None:
    with (
        patch.object(settings, "aws_s3_bucket", ""),
        patch.object(settings, "aws_access_key_id", SecretStr("")),
        patch.object(settings, "aws_secret_access_key", SecretStr("")),
        pytest.raises(ValueError, match="AWS writer credentials"),
    ):
        require_iceberg_write_credentials()
