"""Fail when the browser bundle contains configured server-only values."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_NAMES = (
    "CF_WORKERS_AI_API_KEY",
    "CF_WORKERS_AI_ACCOUNT_ID",
    "CF_WORKERS_AI_MODEL_BASE_URL",
    "BIRD_ALERT_SMTP_ENABLED",
    "BIRD_ALERT_SMTP_SECURITY",
    "BIRD_ALERT_SMTP_HOST",
    "BIRD_ALERT_SMTP_PORT",
    "BIRD_ALERT_SMTP_USERNAME",
    "BIRD_ALERT_SMTP_PASSWORD",
    "BIRD_ALERT_FROM_EMAIL",
    "BIRD_ALERT_RECIPIENT_EMAIL",
    "BIRD_ALERT_SMTP_CA_FILE",
)
VALUE_NAMES = set(CONFIG_NAMES) - {"BIRD_ALERT_SMTP_ENABLED", "BIRD_ALERT_SMTP_PORT"}
FORBIDDEN_MAP_RUNTIME_HOSTS = (
    "api.mapbox.com",
    "tiles.mapbox.com",
    "tile.openstreetmap.org",
    "demotiles.maplibre.org",
    "fonts.googleapis.com",
)


def audit_bundle(bundle_dir: Path, configured: dict[str, str]) -> list[str]:
    """Return configuration names whose name or configured value occurs in the bundle."""
    if not bundle_dir.is_dir():
        raise FileNotFoundError(f"Built app not found at {bundle_dir}; run task app:check first")
    bundle = b"\n".join(path.read_bytes() for path in bundle_dir.rglob("*") if path.is_file())
    findings: list[str] = []
    for name in CONFIG_NAMES:
        if name.encode() in bundle:
            findings.append(f"{name} name")
        value = configured.get(name, "")
        if name in VALUE_NAMES and value and value.encode() in bundle:
            findings.append(f"{name} configured value")
    for host in FORBIDDEN_MAP_RUNTIME_HOSTS:
        if host.encode() in bundle:
            findings.append(f"{host} remote map runtime")
    return findings


def main() -> int:
    dotenv = {key: value or "" for key, value in dotenv_values(PROJECT_ROOT / ".env").items()}
    configured = {name: os.environ.get(name, dotenv.get(name, "")) for name in CONFIG_NAMES}
    findings = audit_bundle(PROJECT_ROOT / "app" / "dist", configured)
    if findings:
        print("bundle configuration audit failed: " + ", ".join(findings))
        return 1
    value_count = sum(bool(configured[name]) for name in VALUE_NAMES)
    print(
        f"bundle configuration audit passed: {len(CONFIG_NAMES)} names and "
        f"{value_count} configured values absent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
