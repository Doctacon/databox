#!/usr/bin/env python3
"""One-shot cleanup of evidence-owned recovery-drill resources."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Direct execution already has this directory on sys.path; spec-based tests do not.
_PLATFORM = Path(__file__).resolve().parent
if str(_PLATFORM) not in sys.path:
    sys.path.insert(0, str(_PLATFORM))
import iceberg_recovery_drill as ir  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
_CLEANUP_ROOT = _ROOT / ".recovery" / "cleanup"
_EVIDENCE_ROOTS = {
    "stage1": _ROOT / ".recovery" / "iceberg",
    "stage2a": _ROOT / ".recovery" / "catalog-stage2a",
    "stage2b": _ROOT / ".recovery" / "catalog-stage2b",
    "stage2c": _ROOT / ".recovery" / "catalog-warehouse-stage2c",
}
_RUN = re.compile(r"[0-9a-f]{16}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,127}")
_MAX_FILE = 2 * 1024 * 1024
_MAX_KEYS = 64
_MAX_TIMELINE = 16
_ACTIVE = ("databox-iceberg-postgres-1", "databox-iceberg-polaris-1")
_TIMEOUT = 30
_STAGE_LABEL = "com.databox.catalog-recovery.stage"
_VALIDATION_LABEL = "com.databox.catalog-recovery.validation"
_RUNTIME_LABEL = "com.databox.catalog-recovery.runtime"
_OWNER_LABEL = "com.databox.catalog-recovery.owner"
_STAGE2A_NETWORK = re.compile(r"databox-stage2a-([0-9a-f]{16})")
_STAGE2A_VOLUME = re.compile(r"databox_stage2a_(src|dst|repo|diag)_([0-9a-f]{16})")
_STAGE2B_CONTAINER = re.compile(
    r"databox-polaris-recovery-drill-(postgres|polaris)-([a-z0-9]{12,16})"
)
_LEGACY_CONTAINER = re.compile(
    r"databox-polaris-recovery-(?:(validation|postgres)-(\d{8}-\d{6})|"
    r"(probe)-(\d{8}_\d{6}))"
)
_STAGE2B_RESOURCE = re.compile(r"databox_polaris_recovery_drill_([a-z0-9]{12,16})")
_LEGACY_NETWORK = re.compile(r"databox_polaris_recovery_validation_(\d{8}_\d{6})")
_LEGACY_VOLUME = re.compile(
    r"databox_polaris_recovery_(?:(probe)_(\d{8}_\d{6})|(\d{8}_\d{6})(?:_retry[1-9]\d*)?)"
)


class CleanupError(RuntimeError):
    """Cleanup refused an unsafe, ambiguous, or changed target."""


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(_safe_bytes(path)).hexdigest()


def _safe_bytes(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_FILE:
            os.close(descriptor)
            raise CleanupError("private evidence file is unsafe")
        with os.fdopen(descriptor, "rb") as stream:
            value = stream.read(_MAX_FILE + 1)
    except OSError as exc:
        raise CleanupError("private evidence file is unavailable") from exc
    if len(value) > _MAX_FILE:
        raise CleanupError("private evidence file is too large")
    return value


def _json_object(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CleanupError("private evidence is invalid JSON") from exc
    if not isinstance(value, dict):
        raise CleanupError("private evidence has an unexpected shape")
    return value


def _safe_json(path: Path) -> dict[str, Any]:
    return _json_object(_safe_bytes(path))


def _ensure_private_dir(path: Path) -> None:
    if path.exists():
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise CleanupError("private cleanup directory is unsafe")
    else:
        path.mkdir(mode=0o700, parents=True)
    os.chmod(path, 0o700)


def _atomic_private(path: Path, value: object) -> None:
    """Publish a 0600 file atomically without replacing an existing artifact."""
    payload = _canonical(value)
    _ensure_private_dir(path.parent)
    temp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    try:
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp, path)
        except FileExistsError as exc:
            raise CleanupError("private cleanup artifact already exists") from exc
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)


def _append_journal(path: Path, event: Mapping[str, object]) -> None:
    flags = os.O_WRONLY | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            raise CleanupError("private cleanup journal is unsafe")
        with os.fdopen(descriptor, "ab") as stream:
            stream.write(_canonical(dict(event)))
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise CleanupError("private cleanup journal is unavailable") from exc


@contextmanager
def _global_lock() -> Iterator[None]:
    _ensure_private_dir(_CLEANUP_ROOT)
    lock_path = _CLEANUP_ROOT / ".lock"
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError as exc:
        raise CleanupError("another cleanup operation holds the global lock") from exc
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _run(
    command: Sequence[str], *, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            env=dict(env) if env is not None else None,
            text=True,
            capture_output=True,
            check=False,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CleanupError("bounded external operation failed") from exc


def _checked(command: Sequence[str], *, env: Mapping[str, str] | None = None) -> str:
    completed = _run(command, env=env)
    if completed.returncode != 0:
        raise CleanupError("bounded external operation was refused")
    return completed.stdout


def _validate_generated_prefix(run_id: str, prefix: str) -> str:
    if _RUN.fullmatch(run_id) is None:
        raise CleanupError("recovery run directory is invalid")
    expected = f"integration/recovery/{run_id}/stage1/warehouse/"
    if prefix.rstrip("/") + "/" != expected:
        raise CleanupError("recovery prefix is not the exact generated sandbox")
    return expected


def _run_directories(root: Path) -> tuple[Path, ...]:
    if not root.exists():
        return ()
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise CleanupError("fixed evidence root is unsafe")
    result: list[Path] = []
    for path in sorted(root.iterdir()):
        if _RUN.fullmatch(path.name) is None or not stat.S_ISDIR(path.lstat().st_mode):
            raise CleanupError("fixed evidence root contains an invalid run directory")
        result.append(path)
    return tuple(result)


def _settings_target(settings: ir.RecoverySettings) -> dict[str, str]:
    return {
        "bucket": settings.bucket,
        "region": settings.region,
        "expectedOwner": settings.storage_role_arn.split(":", 5)[4],
    }


def _require_target(raw: object, expected: Mapping[str, str]) -> None:
    if not isinstance(raw, dict) or any(raw.get(key) != value for key, value in expected.items()):
        raise CleanupError("source evidence target differs from current settings")


def _docker_inspect(kind: str, name: str) -> dict[str, Any] | None:
    completed = _run(("docker", kind, "inspect", name))
    if completed.returncode != 0:
        diagnostic = "\n".join((completed.stdout, completed.stderr))
        if (
            completed.returncode == 1
            and name in diagnostic
            and re.search(r"(?i)(no such|not found)", diagnostic)
        ):
            return None
        raise CleanupError("Docker resource absence could not be proven")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CleanupError("Docker inspection returned invalid JSON") from exc
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise CleanupError("Docker inspection returned an unexpected shape")
    return value[0]


def _labels(kind: str, inspect: Mapping[str, Any]) -> dict[str, str]:
    raw = inspect.get("Config", {}).get("Labels") if kind == "container" else inspect.get("Labels")
    if raw is None:
        return {}
    if not isinstance(raw, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in raw.items()
    ):
        raise CleanupError("Docker labels are invalid")
    return dict(raw)


def _docker_fingerprint(kind: str, inspect: Mapping[str, Any]) -> str:
    """Hash stable identity/config while excluding changing runtime state."""
    if kind == "network":
        stable_network = dict(inspect)
        stable_network.pop("Containers", None)
        return _digest(stable_network)
    if kind != "container":
        return _digest(inspect)
    config = inspect.get("Config")
    host = inspect.get("HostConfig")
    mounts = inspect.get("Mounts")
    network_settings = inspect.get("NetworkSettings")
    networks = network_settings.get("Networks") if isinstance(network_settings, dict) else None
    if (
        not isinstance(config, dict)
        or not isinstance(host, dict)
        or not isinstance(mounts, list)
        or not isinstance(networks, dict)
    ):
        raise CleanupError("Docker container configuration is incomplete")
    membership: dict[str, str] = {}
    for name, attachment in networks.items():
        if not isinstance(name, str) or not isinstance(attachment, dict):
            raise CleanupError("Docker container network membership is invalid")
        network_id = attachment.get("NetworkID")
        if not isinstance(network_id, str) or not network_id:
            raise CleanupError("Docker container network identity is invalid")
        membership[name] = network_id
    stable = {
        "id": inspect.get("Id"),
        "name": inspect.get("Name"),
        "image": inspect.get("Image"),
        "config": config,
        "mounts": sorted(mounts, key=lambda item: _canonical(item)),
        "networkMode": host.get("NetworkMode"),
        "networks": membership,
    }
    return _digest(stable)


def _resource(
    stage: str,
    kind: str,
    name: str,
    expected_labels: Mapping[str, str] | Sequence[Mapping[str, str]],
    source: Path | str,
    *,
    group: str | None = None,
) -> dict[str, Any] | None:
    if _NAME.fullmatch(name) is None:
        raise CleanupError("evidence-derived Docker name is invalid")
    inspect = _docker_inspect(kind, name)
    if inspect is None:
        return None
    actual = _labels(kind, inspect)
    if stage == "stage2b" and kind == "container":
        actual = {key: value for key, value in actual.items() if key.startswith("com.databox.")}
    options = [expected_labels] if isinstance(expected_labels, Mapping) else expected_labels
    if actual not in [dict(option) for option in options]:
        raise CleanupError("Docker ownership labels differ from the exact cleanup contract")
    identity = inspect.get("Id") if kind != "volume" else inspect.get("Name")
    if not isinstance(identity, str) or not identity:
        raise CleanupError("Docker resource identity is invalid")
    state = inspect.get("State") if kind == "container" else None
    source_name = str(source.relative_to(_ROOT)) if isinstance(source, Path) else source
    return {
        "stage": stage,
        "kind": kind,
        "name": name,
        "id": identity,
        "inspectSha256": _docker_fingerprint(kind, inspect),
        "source": source_name,
        "group": group or source_name,
        "running": bool(isinstance(state, dict) and state.get("Running") is True),
    }


def _group(resources: list[dict[str, Any]], candidates: Sequence[dict[str, Any] | None]) -> None:
    resources.extend(item for item in candidates if item is not None)


def _stage2b_report(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = raw.get("report")
    if nested is not None:
        if not isinstance(nested, dict):
            raise CleanupError("Stage 2B nested report is invalid")
        return nested
    return raw


def _docker_names(kind: str) -> tuple[str, ...]:
    command = ["docker", kind, "ls"]
    if kind == "container":
        command.append("--all")
    command.extend(("--format", "{{.Names}}" if kind == "container" else "{{.Name}}"))
    names = tuple(line.strip() for line in _checked(command).splitlines() if line.strip())
    if len(names) != len(set(names)) or any(_NAME.fullmatch(name) is None for name in names):
        raise CleanupError("global Docker inventory is ambiguous")
    return names


def _discovered_spec(
    kind: str, name: str
) -> tuple[str, Mapping[str, str] | Sequence[Mapping[str, str]], str] | None:
    match: re.Match[str] | None
    if kind == "network":
        if match := _STAGE2A_NETWORK.fullmatch(name):
            return "stage2a", {_STAGE_LABEL: "2a"}, f"stage2a:{match[1]}"
        if match := _STAGE2B_RESOURCE.fullmatch(name):
            return "stage2b", {_VALIDATION_LABEL: "network"}, f"stage2b:{match[1]}"
        if match := _LEGACY_NETWORK.fullmatch(name):
            return "stage2b", {_VALIDATION_LABEL: "true"}, f"stage2b-legacy:{match[1]}"
        generated = name.startswith(("databox-stage2a-", "databox_polaris_recovery_"))
    elif kind == "volume":
        if match := _STAGE2A_VOLUME.fullmatch(name):
            return "stage2a", {_STAGE_LABEL: "2a"}, f"stage2a:{match[2]}"
        if match := _STAGE2B_RESOURCE.fullmatch(name):
            return "stage2b", {}, f"stage2b:{match[1]}"
        if match := _LEGACY_VOLUME.fullmatch(name):
            timestamp = match[2] or match[3]
            return "stage2b", {}, f"stage2b-legacy:{timestamp}"
        generated = name.startswith(("databox_stage2a_", "databox_polaris_recovery_"))
    elif kind == "container":
        if match := _STAGE2B_CONTAINER.fullmatch(name):
            role, token = match.groups()
            return "stage2b", {_VALIDATION_LABEL: role}, f"stage2b:{token}"
        if match := _LEGACY_CONTAINER.fullmatch(name):
            standard_role, standard_timestamp, probe_role, probe_timestamp = match.groups()
            role = standard_role or probe_role
            timestamp = standard_timestamp or probe_timestamp
            if role is None or timestamp is None:
                raise CleanupError("legacy Docker resource identity is invalid")
            labels: Mapping[str, str] | Sequence[Mapping[str, str]]
            if role == "validation":
                labels = {_VALIDATION_LABEL: "polaris"}
            else:
                labels = (
                    {_VALIDATION_LABEL: "postgres"},
                    {_RUNTIME_LABEL: "true"},
                )
            return "stage2b", labels, f"stage2b-legacy:{timestamp.replace('-', '_')}"
        generated = name.startswith("databox-polaris-recovery-")
    else:
        raise CleanupError("unsupported Docker inventory kind")
    if generated:
        raise CleanupError("generated-looking Docker resource has an unknown name")
    return None


def _discover_owned_resources() -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for kind in ("container", "network", "volume"):
        for name in _docker_names(kind):
            spec = _discovered_spec(kind, name)
            if spec is None:
                continue
            stage, labels, group = spec
            if kind == "volume" and stage == "stage2b":
                inspect = _docker_inspect(kind, name)
                actual = _labels(kind, inspect or {})
                owner = actual.get(_OWNER_LABEL)
                if not owner or actual != {_OWNER_LABEL: owner}:
                    raise CleanupError("generated recovery volume has invalid ownership labels")
                labels = actual
            item = _resource(stage, kind, name, labels, "docker-discovery", group=group)
            if item is None:
                raise CleanupError("globally listed Docker resource disappeared during inspection")
            resources.append(item)
    return resources


def _merge_resources(
    evidence: Sequence[dict[str, Any]], discovered: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged = {(item["kind"], item["name"]): item for item in evidence}
    if len(merged) != len(evidence):
        raise CleanupError("evidence-derived Docker inventory is not unique")
    for item in discovered:
        key = (item["kind"], item["name"])
        prior = merged.get(key)
        if prior is None:
            merged[key] = item
            continue
        for field in ("stage", "kind", "id", "inspectSha256"):
            if prior[field] != item[field]:
                raise CleanupError("Docker discovery conflicts with source evidence")
        replacement = dict(item)
        replacement["source"] = prior["source"]
        merged[key] = replacement
    return list(merged.values())


def _verify_discovery(resources: Sequence[Mapping[str, Any]]) -> None:
    planned = {(item["kind"], item["name"]): item for item in resources}
    observed = _discover_owned_resources()
    for item in observed:
        prior = planned.get((item["kind"], item["name"]))
        if prior is None or any(
            prior[key] != item[key] for key in ("stage", "id", "inspectSha256")
        ):
            raise CleanupError("global Docker cleanup inventory changed after planning")
    observed_keys = {(item["kind"], item["name"]) for item in observed}
    for item in resources:
        if (
            item["stage"] in {"stage2a", "stage2b"}
            and (
                item["kind"],
                item["name"],
            )
            not in observed_keys
        ):
            raise CleanupError("planned legacy Docker resource disappeared")


def _inventory_sources(
    settings: ir.RecoverySettings,
) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[str]]:
    expected = _settings_target(settings)
    sources: list[dict[str, str]] = []
    resources: list[dict[str, Any]] = []
    prefixes: list[str] = []

    for run_dir in _run_directories(_EVIDENCE_ROOTS["stage1"]):
        path = run_dir / "seed-a.plan.json"
        if not path.exists():
            continue
        plan = _safe_json(path)
        scope, stack = plan.get("scope"), plan.get("stack")
        if (
            not isinstance(scope, dict)
            or not isinstance(stack, dict)
            or not isinstance(stack.get("resources"), dict)
        ):
            raise CleanupError("Stage 1 plan is invalid")
        _require_target(scope, expected)
        prefix = _validate_generated_prefix(run_dir.name, str(scope.get("prefix", "")))
        sha = _file_sha256(path)
        names = stack["resources"]
        expected_names = {
            "network": f"databox-ir-{run_dir.name}-net",
            "postgresVolume": f"databox-ir-{run_dir.name}-pgdata",
        }
        if any(names.get(key) != value for key, value in expected_names.items()):
            raise CleanupError("Stage 1 resources are not generated from their run")
        labels = {
            "com.databox.owner": "iceberg-recovery",
            "com.databox.run": run_dir.name,
            "com.databox.stage": "stage1",
            "com.databox.seed-plan": sha,
        }
        _group(
            resources,
            (
                _resource("stage1", "network", names["network"], labels, path),
                _resource("stage1", "volume", names["postgresVolume"], labels, path),
            ),
        )
        sources.append({"path": str(path.relative_to(_ROOT)), "sha256": sha})
        prefixes.append(prefix)

    for run_dir in _run_directories(_EVIDENCE_ROOTS["stage2a"]):
        path = run_dir / "result.json"
        if not path.exists():
            continue
        report = _safe_json(path)
        if report.get("stage") != "2a" or not str(report.get("status", "")).startswith(
            ("pass", "failed")
        ):
            raise CleanupError("Stage 2A result is invalid")
        token = run_dir.name
        labels = {_STAGE_LABEL: "2a"}
        names = (
            ("network", f"databox-stage2a-{token}"),
            ("volume", f"databox_stage2a_src_{token}"),
            ("volume", f"databox_stage2a_dst_{token}"),
            ("volume", f"databox_stage2a_repo_{token}"),
        )
        _group(
            resources, tuple(_resource("stage2a", kind, name, labels, path) for kind, name in names)
        )
        sources.append({"path": str(path.relative_to(_ROOT)), "sha256": _file_sha256(path)})

    for run_dir in _run_directories(_EVIDENCE_ROOTS["stage2b"]):
        available = [
            run_dir / name for name in ("report.json", "result.json") if (run_dir / name).exists()
        ]
        if not available:
            continue
        if len(available) != 1:
            raise CleanupError("Stage 2B run has ambiguous result evidence")
        path = available[0]
        raw_report = _safe_json(path)
        report = _stage2b_report(raw_report)
        names = report.get("resources")
        if (
            report.get("status") != "pass"
            or not isinstance(names, dict)
            or names.get("preserved") is not True
        ):
            continue
        required = ("network", "volume", "postgres_container", "polaris_container")
        if not all(isinstance(names.get(key), str) for key in required):
            raise CleanupError("successful Stage 2B resources are invalid")
        suffixes = {
            str(names["network"]).removeprefix("databox_polaris_recovery_drill_"),
            str(names["volume"]).removeprefix("databox_polaris_recovery_drill_"),
            str(names["postgres_container"]).removeprefix(
                "databox-polaris-recovery-drill-postgres-"
            ),
            str(names["polaris_container"]).removeprefix("databox-polaris-recovery-drill-polaris-"),
        }
        if len(suffixes) != 1 or re.fullmatch(r"[a-z0-9]{12,16}", suffixes.pop()) is None:
            raise CleanupError("Stage 2B resource names are not deterministic")
        net_labels = {_VALIDATION_LABEL: "network"}
        pg_labels = {_VALIDATION_LABEL: "postgres"}
        polaris_labels = {_VALIDATION_LABEL: "polaris"}
        volume = _docker_inspect("volume", names["volume"])
        volume_labels: dict[str, str] = {}
        if volume is not None:
            volume_labels = _labels("volume", volume)
            owner = volume_labels.get(_OWNER_LABEL)
            if not owner or volume_labels != {_OWNER_LABEL: owner}:
                raise CleanupError("Stage 2B volume ownership label is invalid")
        candidates = (
            _resource("stage2b", "network", names["network"], net_labels, path),
            _resource("stage2b", "volume", names["volume"], volume_labels, path),
            _resource("stage2b", "container", names["postgres_container"], pg_labels, path),
            _resource("stage2b", "container", names["polaris_container"], polaris_labels, path),
        )
        _group(resources, candidates)
        sources.append({"path": str(path.relative_to(_ROOT)), "sha256": _file_sha256(path)})

    for run_dir in _run_directories(_EVIDENCE_ROOTS["stage2c"]):
        path = run_dir / "campaign.plan.json"
        if not path.exists():
            continue
        plan = _safe_json(path)
        scope, target, stack = plan.get("scope"), plan.get("target"), plan.get("stack")
        if (
            not isinstance(scope, dict)
            or not isinstance(stack, dict)
            or not isinstance(stack.get("resources"), dict)
        ):
            raise CleanupError("Stage 2C campaign is invalid")
        _require_target(target, expected)
        prefix = _validate_generated_prefix(run_dir.name, str(scope.get("prefix", "")))
        names = stack["resources"]
        stem = f"databox-stage2c-{run_dir.name}"
        expected_names = {
            "network": f"{stem}-net",
            "sourceVolume": f"{stem}-source",
            "restoredVolume": f"{stem}-restored",
            "repositoryVolume": f"{stem}-repo",
        }
        if any(names.get(key) != value for key, value in expected_names.items()):
            raise CleanupError("Stage 2C resources are not generated from their run")
        sha = _file_sha256(path)
        labels = {
            "com.databox.owner": "catalog-warehouse-recovery",
            "com.databox.run": run_dir.name,
            "com.databox.stage": "stage2c",
            "com.databox.campaign": sha,
        }
        _group(
            resources,
            tuple(
                _resource(
                    "stage2c", "network" if key == "network" else "volume", name, labels, path
                )
                for key, name in expected_names.items()
            ),
        )
        sources.append({"path": str(path.relative_to(_ROOT)), "sha256": sha})
        prefixes.append(prefix)

    resources = _merge_resources(resources, _discover_owned_resources())
    if len(prefixes) != len(set(prefixes)):
        raise CleanupError("cleanup prefix inventory is not unique")
    return (
        sorted(sources, key=lambda item: item["path"]),
        sorted(resources, key=lambda item: (item["kind"], item["name"])),
        sorted(prefixes),
    )


def _aws_environment(settings: ir.RecoverySettings) -> Mapping[str, str]:
    profile = ir._profile_environment(os.environ, profile=settings.profile, region=settings.region)
    credentials = ir._export_aws_credentials(environ=profile)
    environment = ir._credential_environment(
        profile, credentials=credentials, region=settings.region
    )
    identity = ir._verify_non_root_identity(
        environ=environment, expected_sha256=settings.identity_sha256, region=settings.region
    )
    ir._require_identity_relationship(identity=identity, storage_role_arn=settings.storage_role_arn)
    return environment


def _verify_bucket_protection(
    settings: ir.RecoverySettings,
    target: Mapping[str, str],
    environment: Mapping[str, str],
) -> None:
    partition = settings.storage_role_arn.split(":", 2)[1]
    root_arn = f"arn:{partition}:iam::{target['expectedOwner']}:root"
    store = ir.AwsCliVersionStore(
        bucket=target["bucket"],
        prefix="integration/recovery",
        region=target["region"],
        environ=environment,
        expected_owner=target["expectedOwner"],
    )
    store.verify_bucket_protection(root_arn=root_arn)


def _timeline_inventory(
    prefix: str, target: Mapping[str, str], env: Mapping[str, str]
) -> dict[str, list[dict[str, Any]]]:
    command = (
        "aws",
        "s3api",
        "list-object-versions",
        "--bucket",
        target["bucket"],
        "--prefix",
        prefix,
        "--expected-bucket-owner",
        target["expectedOwner"],
        "--region",
        target["region"],
        "--no-paginate",
        "--output",
        "json",
        "--no-cli-pager",
    )
    try:
        raw = json.loads(_checked(command, env=env))
    except json.JSONDecodeError as exc:
        raise CleanupError("AWS version inventory returned invalid JSON") from exc
    if (
        not isinstance(raw, dict)
        or raw.get("IsTruncated") is not False
        or any(raw.get(key) for key in ("NextKeyMarker", "NextVersionIdMarker", "NextToken"))
    ):
        raise CleanupError("AWS version inventory is truncated or paginated")
    timelines: dict[str, list[dict[str, Any]]] = {}
    for field, kind in (("Versions", "version"), ("DeleteMarkers", "delete-marker")):
        values = raw.get(field, [])
        if not isinstance(values, list):
            raise CleanupError("AWS version inventory has an unexpected shape")
        for record in values:
            if not isinstance(record, dict):
                raise CleanupError("AWS timeline entry is invalid")
            key, version, latest = (
                record.get("Key"),
                record.get("VersionId"),
                record.get("IsLatest"),
            )
            if (
                not isinstance(key, str)
                or not key.startswith(prefix)
                or not isinstance(version, str)
                or not version
                or not isinstance(latest, bool)
            ):
                raise CleanupError("AWS timeline entry escaped the planned prefix")
            timelines.setdefault(key, []).append({"kind": kind, "record": record})
    if len(timelines) > _MAX_KEYS:
        raise CleanupError("AWS prefix exceeds the cleanup key limit")
    for entries in timelines.values():
        if (
            len(entries) > _MAX_TIMELINE
            or sum(bool(item["record"]["IsLatest"]) for item in entries) != 1
        ):
            raise CleanupError("AWS key timeline is ambiguous or too long")
    return dict(sorted(timelines.items()))


def _live_keys(timelines: Mapping[str, Sequence[Mapping[str, Any]]]) -> tuple[str, ...]:
    result = []
    for key, entries in timelines.items():
        latest = [item for item in entries if item["record"]["IsLatest"]]
        if len(latest) != 1:
            raise CleanupError("AWS key timeline has no unique latest entry")
        if latest[0]["kind"] == "version":
            result.append(key)
    return tuple(sorted(result))


def _reconcile_timeline(
    before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]]
) -> str:
    """Accept only one newly-created latest delete marker and no other drift."""

    def identity(item: Mapping[str, Any]) -> tuple[object, object]:
        record = item.get("record")
        return item.get("kind"), record.get("VersionId") if isinstance(record, dict) else None

    old = {identity(item): item for item in before}
    new = {identity(item): item for item in after}
    if len(old) != len(before) or len(new) != len(after) or len(new) != len(old) + 1:
        raise CleanupError("post-delete S3 timeline changed unexpectedly")
    added = [item for key, item in new.items() if key not in old]
    old_latest = [item for item in before if item["record"].get("IsLatest") is True]
    if len(added) != 1 or len(old_latest) != 1 or old_latest[0].get("kind") != "version":
        raise CleanupError("ordinary delete did not add exactly one marker")
    marker = added[0]
    marker_record = marker.get("record")
    if (
        marker.get("kind") != "delete-marker"
        or not isinstance(marker_record, dict)
        or marker_record.get("IsLatest") is not True
    ):
        raise CleanupError("ordinary delete did not create the latest marker")
    for key, item in old.items():
        candidate = new.get(key)
        if candidate is None:
            raise CleanupError("ordinary delete removed a prior S3 version")
        expected = json.loads(json.dumps(item))
        if item["record"].get("IsLatest") is True:
            expected["record"]["IsLatest"] = False
        if candidate != expected:
            raise CleanupError("prior S3 timeline entry drifted during deletion")
    return str(marker_record.get("VersionId", ""))


def _reconcile_inventory(
    before: Mapping[str, Sequence[Mapping[str, Any]]],
    after: Mapping[str, Sequence[Mapping[str, Any]]],
    key: str,
) -> str:
    if set(before) != set(after) or key not in before:
        raise CleanupError("post-delete S3 prefix inventory drifted")
    marker = _reconcile_timeline(before[key], after[key])
    if any(after[name] != entries for name, entries in before.items() if name != key):
        raise CleanupError("an unrelated S3 timeline drifted during deletion")
    return marker


def _aws_delete_command(bucket: str, key: str, owner: str, region: str) -> tuple[str, ...]:
    return (
        "aws",
        "s3api",
        "delete-object",
        "--bucket",
        bucket,
        "--key",
        key,
        "--expected-bucket-owner",
        owner,
        "--region",
        region,
        "--no-cli-pager",
    )


def _docker_remove_command(kind: str, identity: str, name: str) -> tuple[str, ...]:
    if kind == "container":
        return ("docker", "container", "rm", identity)
    if kind == "network":
        return ("docker", "network", "rm", identity)
    if kind == "volume":
        return ("docker", "volume", "rm", name)
    raise CleanupError("unsupported Docker resource kind")


def _active_state() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for name in _ACTIVE:
        inspect = _docker_inspect("container", name)
        state = inspect.get("State") if isinstance(inspect, dict) else None
        health = state.get("Health") if isinstance(state, dict) else None
        if (
            not isinstance(inspect, dict)
            or not isinstance(state, dict)
            or state.get("Running") is not True
            or not isinstance(health, dict)
            or health.get("Status") != "healthy"
        ):
            raise CleanupError("active Compose services are not running and healthy")
        identity = inspect.get("Id")
        if not isinstance(identity, str) or not identity:
            raise CleanupError("active Compose identity is invalid")
        result[name] = {"id": identity}
    return result


def _consumer_ids(volume: str) -> set[str]:
    output = _checked(
        (
            "docker",
            "container",
            "ls",
            "--all",
            "--filter",
            f"volume={volume}",
            "--format",
            "{{.ID}}",
        )
    )
    return {line.strip() for line in output.splitlines() if line.strip()}


def _postgres_recovery_container(name: str) -> bool:
    current = _STAGE2B_CONTAINER.fullmatch(name)
    if current is not None:
        return current[1] == "postgres"
    legacy = _LEGACY_CONTAINER.fullmatch(name)
    if legacy is None:
        return False
    return (legacy[1] or legacy[3]) in {"postgres", "probe"}


def _validate_attachments(resources: Sequence[Mapping[str, Any]]) -> None:
    for item in resources:
        same_run = [value for value in resources if value["group"] == item["group"]]
        if item["kind"] == "container":
            inspect = _docker_inspect("container", item["name"])
            settings = inspect.get("NetworkSettings") if isinstance(inspect, dict) else None
            networks = settings.get("Networks") if isinstance(settings, dict) else None
            expected_names = {
                value["name"]
                for value in same_run
                if item["stage"] == "stage2b" and value["kind"] == "network"
            }
            if (
                not expected_names
                and _LEGACY_CONTAINER.fullmatch(str(item["name"])) is not None
                and _labels("container", inspect or {}) == {_RUNTIME_LABEL: "true"}
            ):
                expected_names = {"bridge"}
            if not isinstance(networks, dict) or set(networks) != expected_names:
                raise CleanupError("Docker container has unplanned network membership")
        elif item["kind"] == "network":
            inspect = _docker_inspect("network", item["name"])
            attached = set((inspect or {}).get("Containers", {}))
            expected = {
                value["id"]
                for value in same_run
                if item["stage"] == "stage2b" and value["kind"] == "container"
            }
            if not attached.issubset(expected):
                raise CleanupError("Docker network has unplanned attachments")
        elif item["kind"] == "volume":
            consumers = _consumer_ids(item["name"])
            expected = {
                value["id"]
                for value in same_run
                if item["stage"] == "stage2b"
                and value["kind"] == "container"
                and _postgres_recovery_container(str(value["name"]))
            }
            # Docker's formatted IDs may be short; compare unambiguous prefixes.
            if len(consumers) != len(expected) or any(
                not any(full.startswith(short) for full in expected) for short in consumers
            ):
                raise CleanupError("Docker volume has unplanned consumers")


def _verify_source_hashes(plan: Mapping[str, Any], *, root: Path = _ROOT) -> None:
    sources = plan.get("sources")
    if not isinstance(sources, list):
        raise CleanupError("cleanup source hash inventory is invalid")
    for item in sources:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or _SHA256.fullmatch(str(item.get("sha256", ""))) is None
        ):
            raise CleanupError("cleanup source hash entry is invalid")
        path = root / item["path"]
        try:
            path.relative_to(root / ".recovery")
        except ValueError as exc:
            raise CleanupError("cleanup source path escaped private evidence") from exc
        if not hmac.compare_digest(_file_sha256(path), item["sha256"]):
            raise CleanupError("source recovery evidence changed after planning")


def _public_summary(status: str, plan: Mapping[str, Any]) -> dict[str, object]:
    resources = plan.get("resources", [])
    prefixes = plan.get("prefixes", [])
    object_count = sum(
        len(_live_keys(item.get("timelines", {}))) for item in prefixes if isinstance(item, dict)
    )
    return {
        "status": status,
        "prefixCount": len(prefixes) if isinstance(prefixes, list) else 0,
        "objectCount": object_count,
        "resourceCount": len(resources) if isinstance(resources, list) else 0,
    }


def prepare_cleanup(*, settings: ir.RecoverySettings | None = None) -> dict[str, object]:
    settings = settings or ir.RecoverySettings.load()
    with _global_lock():
        sources, resources, prefixes = _inventory_sources(settings)
        if not resources and not prefixes:
            raise CleanupError("no retained recovery resources were proven")
        _validate_attachments(resources)
        target = _settings_target(settings)
        environment = _aws_environment(settings)
        _verify_bucket_protection(settings, target, environment)
        prefix_plans = [
            {"prefix": prefix, "timelines": _timeline_inventory(prefix, target, environment)}
            for prefix in prefixes
        ]
        active = _active_state()
        run_id = secrets.token_hex(8)
        run_dir = _CLEANUP_ROOT / run_id
        _ensure_private_dir(run_dir)
        plan = {
            "schemaVersion": 1,
            "status": "planned",
            "createdAt": datetime.now(UTC).isoformat(),
            "target": target,
            "sources": sources,
            "prefixes": prefix_plans,
            "resources": resources,
            "active": active,
        }
        _atomic_private(run_dir / "plan.json", plan)
        return _public_summary("planned", plan)


def _read_execution_plan(
    path: Path, sha256: str, *, cleanup_root: Path = _CLEANUP_ROOT
) -> dict[str, Any]:
    if _SHA256.fullmatch(sha256) is None:
        raise CleanupError("approved cleanup plan hash is invalid")
    absolute = Path(os.path.abspath(path))
    root = Path(os.path.abspath(cleanup_root))
    if (
        absolute.name != "plan.json"
        or absolute.parent.parent != root
        or _RUN.fullmatch(absolute.parent.name) is None
    ):
        raise CleanupError("cleanup plan is outside the fixed private directory")
    parent_info = absolute.parent.lstat()
    if not stat.S_ISDIR(parent_info.st_mode):
        raise CleanupError("cleanup plan directory is unsafe")
    payload = _safe_bytes(absolute)
    if stat.S_IMODE(absolute.lstat().st_mode) != 0o600 or not hmac.compare_digest(
        hashlib.sha256(payload).hexdigest(), sha256
    ):
        raise CleanupError("cleanup plan differs from the approved hash")
    if (absolute.parent / "result.json").exists() or (absolute.parent / "intent.json").exists():
        raise CleanupError("cleanup plan is already consumed")
    plan = _json_object(payload)
    if plan.get("schemaVersion") != 1 or plan.get("status") != "planned":
        raise CleanupError("cleanup plan contract is invalid")
    return plan


def _require_evidence_derived_plan(plan: Mapping[str, Any], settings: ir.RecoverySettings) -> None:
    sources, resources, prefixes = _inventory_sources(settings)
    planned_prefixes = plan.get("prefixes")
    if not isinstance(planned_prefixes, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("prefix"), str)
        for item in planned_prefixes
    ):
        raise CleanupError("cleanup prefix plan is invalid")
    prefix_names = [item["prefix"] for item in planned_prefixes]
    if (
        plan.get("sources") != sources
        or plan.get("resources") != resources
        or prefix_names != prefixes
        or any(
            _validate_generated_prefix(prefix.split("/")[2], prefix) != prefix
            for prefix in prefixes
        )
    ):
        raise CleanupError("cleanup plan is not the exact authorized inventory")
    resource_names = {item["name"] for item in resources}
    if resource_names.intersection(_ACTIVE):
        raise CleanupError("active Compose resource was included in cleanup")


def _recheck_resource(
    item: Mapping[str, Any], *, expected_running: bool | None = None
) -> dict[str, Any]:
    inspect = _docker_inspect(item["kind"], item["name"])
    identity = (
        inspect.get("Id")
        if item["kind"] != "volume" and inspect
        else inspect.get("Name")
        if inspect
        else None
    )
    state = inspect.get("State") if isinstance(inspect, dict) else None
    running = bool(isinstance(state, dict) and state.get("Running") is True)
    required_running = item.get("running") if expected_running is None else expected_running
    if (
        inspect is None
        or identity != item["id"]
        or (item["kind"] == "container" and running != required_running)
        or not hmac.compare_digest(
            _docker_fingerprint(str(item["kind"]), inspect), item["inspectSha256"]
        )
    ):
        raise CleanupError("Docker resource fingerprint changed after planning")
    return inspect


def _recheck_docker(resources: Sequence[Mapping[str, Any]]) -> None:
    for item in resources:
        _recheck_resource(item)
    _validate_attachments(resources)


def _journal_mutation(path: Path, action: str, ordinal: int, **private: object) -> None:
    _append_journal(path, {"phase": "intent", "action": action, "ordinal": ordinal, **private})


def execute_cleanup(
    path: Path, sha256: str, *, settings: ir.RecoverySettings | None = None
) -> dict[str, object]:
    settings = settings or ir.RecoverySettings.load()
    trusted = False
    run_dir = path.parent
    plan: dict[str, Any] = {}
    with _global_lock():
        try:
            plan = _read_execution_plan(path, sha256)
            trusted = True
            target = _settings_target(settings)
            if plan.get("target") != target:
                raise CleanupError("cleanup plan target differs from current settings")
            _require_evidence_derived_plan(plan, settings)
            _verify_source_hashes(plan)
            resources = plan.get("resources")
            prefixes = plan.get("prefixes")
            if not isinstance(resources, list) or not isinstance(prefixes, list):
                raise CleanupError("cleanup plan inventories are invalid")
            environment = _aws_environment(settings)
            current: dict[str, dict[str, list[dict[str, Any]]]] = {}
            for item in prefixes:
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("prefix"), str)
                    or not isinstance(item.get("timelines"), dict)
                ):
                    raise CleanupError("cleanup prefix plan is invalid")
                observed = _timeline_inventory(item["prefix"], target, environment)
                if observed != item["timelines"]:
                    raise CleanupError("S3 timeline changed after planning")
                current[item["prefix"]] = observed
            _recheck_docker(resources)
            _verify_discovery(resources)
            if _active_state() != plan.get("active"):
                raise CleanupError("active Compose services changed after planning")
            _verify_bucket_protection(settings, target, environment)

            counts = _public_summary("executing", plan)
            _atomic_private(
                run_dir / "intent.json",
                {"schemaVersion": 1, "planSha256": sha256, "counts": counts},
            )
            _atomic_private(
                run_dir / "journal.jsonl",
                {"schemaVersion": 1, "planSha256": sha256, "phase": "started"},
            )
            journal = run_dir / "journal.jsonl"
            ordinal = 0

            for prefix_item in prefixes:
                prefix = prefix_item["prefix"]
                timelines = current[prefix]
                for key in _live_keys(timelines):
                    ordinal += 1
                    _journal_mutation(journal, "ordinary-delete", ordinal, key=key)
                    unchanged = _timeline_inventory(prefix, target, environment)
                    if unchanged != timelines:
                        raise CleanupError("S3 timeline changed at the mutation boundary")
                    command = _aws_delete_command(
                        target["bucket"], key, target["expectedOwner"], target["region"]
                    )
                    _checked(command, env=environment)
                    observed = _timeline_inventory(prefix, target, environment)
                    marker = _reconcile_inventory(timelines, observed, key)
                    timelines = observed
                    current[prefix] = observed
                    _append_journal(
                        journal,
                        {
                            "phase": "complete",
                            "action": "ordinary-delete",
                            "ordinal": ordinal,
                            "deleteMarkerVersionId": marker,
                        },
                    )

            containers = [item for item in resources if item["kind"] == "container"]
            for item in containers:
                if item.get("running"):
                    ordinal += 1
                    _journal_mutation(journal, "stop-container", ordinal, id=item["id"])
                    _recheck_resource(item, expected_running=True)
                    _checked(("docker", "stop", item["id"]))
                    _recheck_resource(item, expected_running=False)
                    _append_journal(
                        journal,
                        {"phase": "complete", "action": "stop-container", "ordinal": ordinal},
                    )
                ordinal += 1
                _journal_mutation(journal, "remove-container", ordinal, id=item["id"])
                _recheck_resource(item, expected_running=False)
                _checked(_docker_remove_command("container", item["id"], item["name"]))
                _append_journal(
                    journal, {"phase": "complete", "action": "remove-container", "ordinal": ordinal}
                )

            for kind in ("network", "volume"):
                for item in (value for value in resources if value["kind"] == kind):
                    ordinal += 1
                    _journal_mutation(
                        journal, f"remove-{kind}", ordinal, id=item["id"], name=item["name"]
                    )
                    inspected = _recheck_resource(item)
                    if kind == "network" and (inspected.get("Containers") or {}):
                        raise CleanupError("Docker network gained an attachment before removal")
                    if kind == "volume" and _consumer_ids(item["name"]):
                        raise CleanupError("Docker volume gained a consumer before removal")
                    _checked(_docker_remove_command(kind, item["id"], item["name"]))
                    _append_journal(
                        journal,
                        {"phase": "complete", "action": f"remove-{kind}", "ordinal": ordinal},
                    )

            for item in resources:
                if _docker_inspect(item["kind"], item["name"]) is not None:
                    raise CleanupError("planned Docker resource remains after cleanup")
            if _discover_owned_resources():
                raise CleanupError("owned Docker resource appeared during cleanup")
            for prefix_item in prefixes:
                observed = _timeline_inventory(prefix_item["prefix"], target, environment)
                if _live_keys(observed) or observed != current[prefix_item["prefix"]]:
                    raise CleanupError("final S3 cleanup proof failed")
            if _active_state() != plan.get("active"):
                raise CleanupError("active Compose services changed during cleanup")
            _verify_bucket_protection(settings, target, environment)
            _verify_source_hashes(plan)
            result = {
                "schemaVersion": 1,
                "status": "pass",
                "planSha256": sha256,
                "counts": _public_summary("pass", plan),
            }
            _atomic_private(run_dir / "result.json", result)
            return _public_summary("pass", plan)
        except BaseException as exc:
            if trusted and not (run_dir / "result.json").exists():
                try:
                    _atomic_private(
                        run_dir / "result.json",
                        {
                            "schemaVersion": 1,
                            "status": "failed",
                            "planSha256": sha256,
                            "errorKind": type(exc).__name__,
                            "counts": _public_summary("failed", plan),
                        },
                    )
                except BaseException:
                    pass
            raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare", help="inventory retained evidence and write one private plan")
    execute = commands.add_parser("execute", help="execute one exact approved cleanup plan once")
    execute.add_argument("--plan", required=True, type=Path)
    execute.add_argument("--sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = (
            prepare_cleanup()
            if args.command == "prepare"
            else execute_cleanup(args.plan, args.sha256)
        )
    except Exception:
        print(
            json.dumps(
                {"status": "refused", "prefixCount": 0, "objectCount": 0, "resourceCount": 0},
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
