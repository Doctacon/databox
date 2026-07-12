"""Tests for the compiled browser configuration audit."""

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "audit_app_bundle.py"
audit_bundle = cast(
    Callable[[Path, dict[str, str]], list[str]], runpy.run_path(str(SCRIPT))["audit_bundle"]
)


def test_bundle_audit_rejects_configured_names_and_values(tmp_path: Path) -> None:
    bundle = tmp_path / "dist"
    bundle.mkdir()
    (bundle / "app.js").write_text("CF_WORKERS_AI_API_KEY configured-secret", encoding="utf-8")

    assert audit_bundle(bundle, {"CF_WORKERS_AI_API_KEY": "configured-secret"}) == [
        "CF_WORKERS_AI_API_KEY name",
        "CF_WORKERS_AI_API_KEY configured value",
    ]


def test_bundle_audit_rejects_alert_smtp_names_and_values(tmp_path: Path) -> None:
    bundle = tmp_path / "dist"
    bundle.mkdir()
    (bundle / "app.js").write_text(
        "BIRD_ALERT_SMTP_PASSWORD configured-bridge-secret", encoding="utf-8"
    )

    assert audit_bundle(bundle, {"BIRD_ALERT_SMTP_PASSWORD": "configured-bridge-secret"}) == [
        "BIRD_ALERT_SMTP_PASSWORD name",
        "BIRD_ALERT_SMTP_PASSWORD configured value",
    ]


def test_bundle_audit_rejects_remote_map_runtime_hosts(tmp_path: Path) -> None:
    bundle = tmp_path / "dist"
    bundle.mkdir()
    (bundle / "app.js").write_text("https://tile.openstreetmap.org/{z}/{x}/{y}.png")

    assert audit_bundle(bundle, {}) == ["tile.openstreetmap.org remote map runtime"]


def test_bundle_audit_accepts_bundle_without_configuration(tmp_path: Path) -> None:
    bundle = tmp_path / "dist"
    bundle.mkdir()
    (bundle / "app.js").write_text("Birding Trip Copilot", encoding="utf-8")

    assert audit_bundle(bundle, {"CF_WORKERS_AI_API_KEY": "configured-secret"}) == []


def test_bundle_audit_requires_a_build(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="run task app:check first"):
        audit_bundle(tmp_path / "missing", {})
