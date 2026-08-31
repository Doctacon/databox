"""Regression tests for the recursive repository secret scan."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "platform" / "check_secrets.py"


def _run_scan(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        check=False,
        capture_output=True,
        text=True,
    )


def _secret_assignment() -> str:
    # Construct this at runtime so the scanner test itself remains clean.
    return "API_" + "TOKEN = " + repr("live-credential-value-123456789")


def _identifier_secret() -> str:
    return "CorrectHorse" + "BatteryStaple123"


def _assignment(name: str, value: str) -> str:
    return f"{name} = {value!r}\n"


def _provider_credential() -> str:
    return "AK" + "IA" + ("A" * 16)


def _stage_repository(root: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "--force", "."], check=True)


def test_directory_invocation_detects_nested_secret(tmp_path: Path) -> None:
    nested = tmp_path / "src" / "nested"
    nested.mkdir(parents=True)
    (nested / "credentials.py").write_text(_secret_assignment(), encoding="utf-8")
    _stage_repository(tmp_path)

    result = _run_scan(tmp_path)

    assert result.returncode == 1
    assert "credentials.py:1: credential-like literal assignment" in result.stderr
    assert "live-credential-value" not in result.stderr


def test_identifier_only_credential_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "settings.py"
    path.write_text(_assignment("GITHUB_" + "TOKEN", _identifier_secret()), encoding="utf-8")
    _stage_repository(tmp_path)

    result = _run_scan(tmp_path)

    assert result.returncode == 1
    assert "settings.py:1: credential-like literal assignment" in result.stderr
    assert _identifier_secret() not in result.stderr


def test_quoted_structured_config_keys_are_detected(tmp_path: Path) -> None:
    name = "pass" + "word"
    value = _identifier_secret()
    payloads = {
        "config.json": '{"' + name + '": "' + value + '"}\n',
        "config.toml": '"' + name + '" = "' + value + '"\n',
        "config.yaml": '"' + name + '": "' + value + '"\n',
    }
    for filename, payload in payloads.items():
        (tmp_path / filename).write_text(payload, encoding="utf-8")
    _stage_repository(tmp_path)

    result = _run_scan(tmp_path)

    assert result.returncode == 1
    for filename in payloads:
        assert f"{filename}:1: credential-like literal assignment" in result.stderr
    assert value not in result.stderr


def test_allow_directive_does_not_hide_provider_credential(tmp_path: Path) -> None:
    provider_credential = _provider_credential()
    (tmp_path / "fixture.py").write_text(
        _assignment("FIXTURE_" + "VALUE", provider_credential).rstrip()
        + "  # secret-scan: allow\n",
        encoding="utf-8",
    )
    marker = "-----BEGIN " + "PRIVATE KEY-----"
    (tmp_path / "private.txt").write_text(marker + "  # secret-scan: allow\n", encoding="utf-8")
    _stage_repository(tmp_path)

    result = _run_scan(tmp_path)

    assert result.returncode == 1
    assert "fixture.py:1: AWS access key ID" in result.stderr
    assert "private.txt:1: private key" in result.stderr
    assert provider_credential not in result.stderr


def test_alphanumeric_bearer_token_is_detected(tmp_path: Path) -> None:
    token = _identifier_secret()
    (tmp_path / "request.txt").write_text(
        "Authorization: " + "Bearer " + token + "\n", encoding="utf-8"
    )
    _stage_repository(tmp_path)

    result = _run_scan(tmp_path)

    assert result.returncode == 1
    assert "request.txt:1: bearer token" in result.stderr
    assert token not in result.stderr


def test_tracked_env_variants_and_credential_dotfiles_are_scanned(
    tmp_path: Path,
) -> None:
    value = _identifier_secret()
    (tmp_path / ".env.production").write_text(
        _assignment("DEPLOY_" + "TOKEN", value), encoding="utf-8"
    )
    (tmp_path / ".npmrc").write_text(
        "//registry.npmjs.org/:_auth" + "Token=" + value + "\n", encoding="utf-8"
    )
    _stage_repository(tmp_path)

    result = _run_scan(tmp_path)

    assert result.returncode == 1
    assert ".env.production:1: credential-like literal assignment" in result.stderr
    assert ".npmrc:1: credential-like literal assignment" in result.stderr
    assert value not in result.stderr


def test_tracked_env_and_private_key_files_are_scanned(tmp_path: Path) -> None:
    value = _identifier_secret()
    (tmp_path / ".env").write_text(_assignment("DEPLOY_" + "TOKEN", value), encoding="utf-8")
    private_key_marker = "-----BEGIN " + "PRIVATE KEY-----"  # secret-scan: allow
    encrypted_key_marker = (  # secret-scan: allow
        "-----BEGIN " + "ENCRYPTED PRIVATE KEY-----"
    )
    (tmp_path / "certificate.pem").write_text(private_key_marker + "\n", encoding="utf-8")
    (tmp_path / "signing.key").write_text(encrypted_key_marker + "\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text(_assignment("REGISTRY_" + "TOKEN", value), encoding="utf-8")
    _stage_repository(tmp_path)

    result = _run_scan(tmp_path)

    assert result.returncode == 1
    assert ".env:1: credential-like literal assignment" in result.stderr
    assert "certificate.pem:1: private key" in result.stderr
    assert "signing.key:1: private key" in result.stderr
    assert "uv.lock:1: credential-like literal assignment" in result.stderr
    assert value not in result.stderr


def test_excluded_files_are_skipped(tmp_path: Path) -> None:
    excluded = tmp_path / "node_modules"
    excluded.mkdir()
    (excluded / "credentials.py").write_text(_secret_assignment(), encoding="utf-8")
    cache = tmp_path / ".cache"
    cache.mkdir()
    (cache / "credentials.py").write_text(_secret_assignment(), encoding="utf-8")
    (tmp_path / "clean.py").write_text("value = 'public'\n", encoding="utf-8")
    _stage_repository(tmp_path)

    result = _run_scan(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "1 eligible files checked" in result.stdout


def test_excluded_ancestor_name_does_not_suppress_repository(tmp_path: Path) -> None:
    root = tmp_path / "build" / "repository"
    nested = root / "src"
    nested.mkdir(parents=True)
    (nested / "credentials.py").write_text(_secret_assignment(), encoding="utf-8")
    _stage_repository(root)

    result = _run_scan(root)

    assert result.returncode == 1
    assert "credentials.py:1: credential-like literal assignment" in result.stderr


def test_non_sensitive_name_containing_secret_is_not_flagged(tmp_path: Path) -> None:
    (tmp_path / "profile.yaml").write_text(
        'secretary_contact: "alexander-hamilton"\n', encoding="utf-8"
    )
    _stage_repository(tmp_path)

    result = _run_scan(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "1 eligible files checked" in result.stdout


def test_directory_with_no_eligible_files_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "README").write_text("Public documentation.\n", encoding="utf-8")
    _stage_repository(tmp_path)

    result = _run_scan(tmp_path)

    assert result.returncode == 2
    assert "no eligible files found for directory scan" in result.stderr


def test_clean_repository_scan_succeeds() -> None:
    result = _run_scan(PROJECT_ROOT)

    assert result.returncode == 0, result.stderr
    assert "Secret scan passed:" in result.stdout
