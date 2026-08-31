"""Tests for the compiled browser configuration audit."""

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "rufous_media" / "audit_app_bundle.py"
MODULE = runpy.run_path(str(SCRIPT))
audit_bundle = cast(Callable[[Path, dict[str, str]], list[str]], MODULE["audit_bundle"])
dotenv_values = cast(Callable[[Path], dict[str, str]], MODULE["dotenv_values"])


def test_dotenv_reader_is_standard_library_only(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# local values\n"
        "export API_KEY='synthetic-value'\n"
        "PLAIN=value # comment\n"
        'QUOTED="actual-secret" # comment\n'
        "HASH='value # retained' # comment\n",
        encoding="utf-8",
    )

    assert dotenv_values(dotenv) == {
        "API_KEY": "synthetic-value",
        "PLAIN": "value",
        "QUOTED": "actual-secret",
        "HASH": "value # retained",
    }


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


def test_bundle_audit_rejects_forbidden_remote_map_resource_hosts(tmp_path: Path) -> None:
    bundle = tmp_path / "dist"
    assets = bundle / "assets"
    assets.mkdir(parents=True)
    (assets / "maplibre-gl-hash.js").write_text("https://tile.openstreetmap.org/{z}/{x}/{y}.png")

    assert audit_bundle(bundle, {}) == ["tile.openstreetmap.org forbidden remote map resource"]


def test_bundle_audit_accepts_exact_https_openfreemap_origin(tmp_path: Path) -> None:
    bundle = tmp_path / "dist"
    bundle.mkdir()
    (bundle / "app.js").write_text(
        '"https://tiles.openfreemap.org/styles/positron" '
        'candidate.hostname === "tiles.openfreemap.org" '
        'candidate.origin === "https://tiles.openfreemap.org"',
        encoding="utf-8",
    )

    assert audit_bundle(bundle, {}) == []


@pytest.mark.parametrize(
    "url",
    [
        "http://tiles.openfreemap.org/styles/positron",
        "//tiles.openfreemap.org/styles/positron",
        "https://user@tiles.openfreemap.org/styles/positron",
        "https://tiles.openfreemap.org:443/styles/positron",
        "https://tiles.openfreemap.org.evil.example/styles/positron",
    ],
)
def test_bundle_audit_rejects_non_exact_openfreemap_origins(tmp_path: Path, url: str) -> None:
    bundle = tmp_path / "dist"
    bundle.mkdir()
    (bundle / "app.js").write_text(url, encoding="utf-8")

    assert audit_bundle(bundle, {}) == ["tiles.openfreemap.org invalid map resource origin"]


def test_bundle_audit_accepts_bundle_without_configuration(tmp_path: Path) -> None:
    bundle = tmp_path / "dist"
    bundle.mkdir()
    (bundle / "app.js").write_text("Birding Trip Copilot", encoding="utf-8")

    assert audit_bundle(bundle, {"CF_WORKERS_AI_API_KEY": "configured-secret"}) == []


def test_bundle_audit_requires_a_build(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="run task app:check first"):
        audit_bundle(tmp_path / "missing", {})
