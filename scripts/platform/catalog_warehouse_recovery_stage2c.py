#!/usr/bin/env python3
"""Bounded Stage 2C joint Polaris-catalog and Iceberg-object recovery drill.

``prepare`` is mutation-free and writes one exact private plan. ``execute`` consumes
that plan once. A run uses only generated Docker resources and the existing
``integration/recovery/<16hex>/stage1/warehouse/`` S3 sandbox. Once damage is
journaled, expiry aborts the success path into mandatory restoration and containment;
that compensation ignores the aggregate objective but retains per-command bounds.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import hmac
import importlib.metadata
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

# Running this file directly puts scripts/platform on sys.path. Tests insert it too.
import iceberg_recovery_drill as ir

_ROOT = Path(__file__).resolve().parents[2]
_EVIDENCE_ROOT = _ROOT / ".recovery" / "catalog-warehouse-stage2c"
_RUN_ID = re.compile(r"[0-9a-f]{16}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_MAX_KEYS = 64
_MAX_BYTES = 32 * 1024 * 1024
_MAX_VERSIONS = 16
_MAX_PRIVATE_BYTES = 1024 * 1024
_PLAN_LIFETIME = timedelta(hours=6)
_LIVE_OBJECTIVE_SECONDS = 20 * 60
_COMMAND_TIMEOUT_SECONDS = 30
_SERVICE_PROCESS_TIMEOUT_SECONDS = _LIVE_OBJECTIVE_SECONDS + 60
_SERVICE_STOP_TIMEOUT_SECONDS = 10
_POSTGRES_READY_TIMEOUT_SECONDS = 120
_POLARIS_READY_TIMEOUT_SECONDS = 180
_POSTGRES_IMAGE = "databox-polaris-postgres:17.6-pgbackrest-2.59.1"
_ADMIN_IMAGE = "apache/polaris-admin-tool:1.7.0"
_POLARIS_IMAGE = "apache/polaris:1.7.0"

POINT_A_ROWS: tuple[tuple[Mapping[str, object], ...], ...] = (
    (
        {"event_id": 1, "generation": "point-a", "value": 110},
        {"event_id": 2, "generation": "point-a", "value": 120},
        {"event_id": 3, "generation": "point-a", "value": 130},
    ),
    (
        {"event_id": 1, "generation": "point-a", "value": 210},
        {"event_id": 2, "generation": "point-a", "value": 220},
        {"event_id": 3, "generation": "point-a", "value": 230},
    ),
)
POINT_B_ROWS: tuple[Mapping[str, object], ...] = (
    {"event_id": 4, "generation": "point-b", "value": 140},
    {"event_id": 4, "generation": "point-b", "value": 240},
)


class Stage2CError(RuntimeError):
    """A fail-closed Stage 2C refusal."""


def _bounded_run(command: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run one local/AWS/Docker command with a mandatory finite timeout."""
    if "timeout" in kwargs:
        raise Stage2CError("nested subprocess timeout override is prohibited")
    try:
        return subprocess.run(list(command), timeout=_COMMAND_TIMEOUT_SECONDS, **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise Stage2CError("bounded subprocess operation timed out") from exc


def _inspect_image(reference: str) -> ir.ImagePin:
    return ir._inspect_docker_image(reference, runner=_bounded_run)


def _docker_fingerprint() -> str:
    return ir._docker_runtime_fingerprint(runner=_bounded_run)


@dataclass(frozen=True)
class JointScope:
    run_id: str
    prefix: str
    catalog: str
    namespace: str
    tables: tuple[str, str]


@dataclass(frozen=True)
class TablePoint:
    table: str
    capture: ir.TableCapture
    logical_graph_sha256: str


@dataclass(frozen=True)
class PointBState:
    table: str
    metadata_location: str
    snapshot_id: int
    rows_sha256: str
    nodes: tuple[ir.GraphNode, ...]

    @property
    def graph_keys(self) -> frozenset[str]:
        return frozenset(node.key for node in self.nodes)


@dataclass(frozen=True)
class RecoveryTarget:
    name: str


class JointRecoveryOperations(Protocol):
    """Effect seam used by the exact, crash-safe Stage 2C state machine."""

    def preflight(self, scope: JointScope) -> ir.GraphNode: ...

    def create_point_a(self, scope: JointScope) -> tuple[TablePoint, TablePoint]: ...

    def backup_point_a(self) -> RecoveryTarget: ...

    def append_point_b(self, point_a: Sequence[TablePoint]) -> tuple[PointBState, PointBState]: ...

    def verify_prefix_inventory(
        self,
        canary: ir.GraphNode,
        point_a: Sequence[TablePoint],
        point_b: Sequence[PointBState],
    ) -> None: ...

    def predelete_state(self, node: ir.GraphNode) -> ir.ObjectState: ...

    def current_state(self, node: ir.GraphNode) -> ir.ObjectState: ...

    def delete_current(self, node: ir.GraphNode) -> ir.DeleteResult: ...

    def prove_point_b_broken(
        self, point_b: Sequence[PointBState], approved_nodes: Sequence[ir.GraphNode]
    ) -> None: ...

    def stop_source(self) -> None: ...

    def restore_catalog(self, target: RecoveryTarget) -> None: ...

    def restore_object(self, node: ir.GraphNode) -> ir.ObjectState: ...

    def validate_restored(
        self, point_a: Sequence[TablePoint], point_b: Sequence[PointBState]
    ) -> tuple[TablePoint, TablePoint]: ...

    def contain(self) -> None: ...


@dataclass(frozen=True)
class PlanBinding:
    source_revision: str
    script_sha256: str
    stage1_script_sha256: str
    python_version: str
    pyiceberg_version: str
    pyarrow_version: str
    configuration_sha256: str


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _scope(run_id: str) -> JointScope:
    if _RUN_ID.fullmatch(run_id) is None:
        raise Stage2CError("generated Stage 2C run ID is invalid")
    return JointScope(
        run_id=run_id,
        prefix=f"integration/recovery/{run_id}/stage1/warehouse",
        catalog=f"joint_recovery_{run_id}",
        namespace=f"joint_{run_id}",
        tables=(f"events_alpha_{run_id}", f"events_beta_{run_id}"),
    )


def _scope_dict(scope: JointScope) -> dict[str, object]:
    return {
        "runId": scope.run_id,
        "prefix": scope.prefix,
        "catalog": scope.catalog,
        "namespace": scope.namespace,
        "tables": list(scope.tables),
    }


def _rows_digest(rows: Sequence[Mapping[str, object]]) -> str:
    normalized = [dict(row) for row in sorted(rows, key=lambda row: int(row["event_id"]))]
    return _digest(normalized)


def _node_dict(node: ir.GraphNode) -> dict[str, object]:
    return {
        "key": node.key,
        "kind": node.kind,
        "sourceVersionId": node.source_version_id,
        "etag": node.etag,
        "size": node.size,
        "sha256": node.sha256,
        "depth": node.depth,
    }


def _node_from_dict(raw: object) -> ir.GraphNode:
    if not isinstance(raw, dict) or set(raw) != {
        "key",
        "kind",
        "sourceVersionId",
        "etag",
        "size",
        "sha256",
        "depth",
    }:
        raise Stage2CError("private Stage 2C graph node has an unexpected shape")
    try:
        node = ir.GraphNode(
            key=raw["key"],
            kind=raw["kind"],
            source_version_id=raw["sourceVersionId"],
            etag=raw["etag"],
            size=raw["size"],
            sha256=raw["sha256"],
            depth=raw["depth"],
        )
    except (KeyError, TypeError) as exc:
        raise Stage2CError("private Stage 2C graph node is invalid") from exc
    if (
        not isinstance(node.key, str)
        or not isinstance(node.kind, str)
        or not isinstance(node.source_version_id, str)
        or not isinstance(node.etag, str)
        or isinstance(node.size, bool)
        or not isinstance(node.size, int)
        or node.size < 0
        or not _SHA256.fullmatch(node.sha256)
        or isinstance(node.depth, bool)
        or not isinstance(node.depth, int)
        or node.depth < 0
    ):
        raise Stage2CError("private Stage 2C graph node values are invalid")
    return node


def _logical_node(node: ir.GraphNode) -> dict[str, object]:
    return {
        "key": node.key,
        "kind": node.kind,
        "size": node.size,
        "sha256": node.sha256,
        "depth": node.depth,
    }


def _logical_graph_sha256(nodes: Sequence[ir.GraphNode]) -> str:
    return _digest(sorted((_logical_node(node) for node in nodes), key=lambda item: item["key"]))


def _validate_point_a(scope: JointScope, points: Sequence[TablePoint]) -> tuple[ir.GraphNode, ...]:
    if len(points) != 2 or tuple(point.table for point in points) != scope.tables:
        raise Stage2CError("Stage 2C requires exactly the generated two-table point A")
    all_nodes: list[ir.GraphNode] = []
    table_keys: list[set[str]] = []
    for index, point in enumerate(points):
        capture = point.capture
        if (
            capture.row_count != 3
            or capture.rows_sha256 != _rows_digest(POINT_A_ROWS[index])
            or not capture.nodes
            or point.logical_graph_sha256 != _logical_graph_sha256(capture.nodes)
        ):
            raise Stage2CError("point-A table contract differs from deterministic input")
        keys = {node.key for node in capture.nodes}
        table_prefix = f"{scope.prefix}/{scope.namespace}/{point.table}/"
        parsed_location = urlparse(capture.metadata_location)
        metadata_key = parsed_location.path.lstrip("/")
        if len(keys) != len(capture.nodes):
            raise Stage2CError("point-A table graph contains duplicate keys")
        if (
            parsed_location.scheme != "s3"
            or parsed_location.netloc != capture.bucket
            or parsed_location.query
            or parsed_location.fragment
            or metadata_key not in keys
            or not metadata_key.startswith(table_prefix + "metadata/")
            or not all(key.startswith(table_prefix) for key in keys)
        ):
            raise Stage2CError("point-A table graph escaped the generated table prefix")
        table_keys.append(keys)
        all_nodes.extend(capture.nodes)
    if table_keys[0].intersection(table_keys[1]):
        raise Stage2CError("point-A table graphs are not disjoint")
    if len(all_nodes) + 1 > _MAX_KEYS:
        raise Stage2CError("joint point-A graph exceeds the aggregate key limit")
    if sum(node.size for node in all_nodes) > _MAX_BYTES:
        raise Stage2CError("joint point-A graph exceeds the aggregate byte limit")
    return tuple(all_nodes)


def _validate_point_b(
    point_a: Sequence[TablePoint], point_b: Sequence[PointBState]
) -> frozenset[str]:
    if len(point_b) != 2 or tuple(item.table for item in point_b) != tuple(
        item.table for item in point_a
    ):
        raise Stage2CError("point-B table set differs from point A")
    b_only: set[str] = set()
    for a, b in zip(point_a, point_b, strict=True):
        a_keys = {node.key for node in a.capture.nodes}
        metadata_key = urlparse(a.capture.metadata_location).path.lstrip("/")
        if "/metadata/" not in metadata_key:
            raise Stage2CError("point-A metadata location is not inside its table prefix")
        table_prefix = metadata_key.rsplit("/metadata/", 1)[0] + "/"
        b_metadata = urlparse(b.metadata_location)
        b_metadata_key = b_metadata.path.lstrip("/")
        if (
            b_metadata.scheme != "s3"
            or b_metadata.netloc != a.capture.bucket
            or b_metadata.query
            or b_metadata.fragment
            or b_metadata_key not in b.graph_keys
            or not b_metadata_key.startswith(table_prefix + "metadata/")
            or len(b.graph_keys) != len(b.nodes)
            or not all(node.key.startswith(table_prefix) for node in b.nodes)
        ):
            raise Stage2CError("point-B graph contains duplicate or malformed keys")
        if (
            b.metadata_location == a.capture.metadata_location
            or b.snapshot_id == a.capture.snapshot_id
            or b.rows_sha256 == a.capture.rows_sha256
            or not a_keys.intersection(b.graph_keys)
        ):
            raise Stage2CError("point B did not diverge while retaining point-A dependencies")
        only = set(b.graph_keys) - a_keys
        if not only:
            raise Stage2CError("point B introduced no table-specific graph objects")
        b_only.update(only)
    return frozenset(b_only)


def _damage_nodes(
    point_a: Sequence[TablePoint], point_b: Sequence[PointBState]
) -> tuple[ir.GraphNode, ...]:
    """Select only live point-A dependencies still referenced by each point-B graph."""
    live_kinds = {"manifest", "data", "position-delete", "equality-delete"}
    selected: list[ir.GraphNode] = []
    for a, b in zip(point_a, point_b, strict=True):
        table_nodes = tuple(
            node for node in a.capture.nodes if node.key in b.graph_keys and node.kind in live_kinds
        )
        if not table_nodes:
            raise Stage2CError("point B retained no damageable live point-A dependency")
        selected.extend(table_nodes)
    keys = {node.key for node in selected}
    if len(keys) != len(selected):
        raise Stage2CError("Stage 2C damage selection is not table-disjoint")
    return tuple(selected)


def _capture_dict(point: TablePoint) -> dict[str, object]:
    capture = point.capture
    return {
        "table": point.table,
        "tableUuid": capture.table_uuid,
        "metadataLocation": capture.metadata_location,
        "snapshotId": capture.snapshot_id,
        "schemaSha256": capture.schema_sha256,
        "rowCount": capture.row_count,
        "rowsSha256": capture.rows_sha256,
        "logicalGraphSha256": point.logical_graph_sha256,
        "nodes": [_node_dict(node) for node in capture.nodes],
    }


def _capture_from_dict(raw: object, bucket: str) -> TablePoint:
    if not isinstance(raw, dict) or set(raw) != {
        "table",
        "tableUuid",
        "metadataLocation",
        "snapshotId",
        "schemaSha256",
        "rowCount",
        "rowsSha256",
        "logicalGraphSha256",
        "nodes",
    }:
        raise Stage2CError("private point-A table contract has an unexpected shape")
    nodes_raw = raw["nodes"]
    if not isinstance(nodes_raw, list):
        raise Stage2CError("private point-A graph is invalid")
    nodes = tuple(_node_from_dict(item) for item in nodes_raw)
    values = (
        raw["table"],
        raw["tableUuid"],
        raw["metadataLocation"],
        raw["schemaSha256"],
        raw["rowsSha256"],
        raw["logicalGraphSha256"],
    )
    if not all(isinstance(item, str) for item in values):
        raise Stage2CError("private point-A table values are invalid")
    if any(
        not _SHA256.fullmatch(raw[name])
        for name in ("schemaSha256", "rowsSha256", "logicalGraphSha256")
    ):
        raise Stage2CError("private point-A digests are invalid")
    if isinstance(raw["snapshotId"], bool) or not isinstance(raw["snapshotId"], int):
        raise Stage2CError("private point-A snapshot is invalid")
    if raw["rowCount"] != 3:
        raise Stage2CError("private point-A row count is invalid")
    capture = ir.TableCapture(
        bucket=bucket,
        table_uuid=raw["tableUuid"],
        metadata_location=raw["metadataLocation"],
        snapshot_id=raw["snapshotId"],
        schema_sha256=raw["schemaSha256"],
        row_count=raw["rowCount"],
        rows_sha256=raw["rowsSha256"],
        nodes=nodes,
    )
    point = TablePoint(raw["table"], capture, raw["logicalGraphSha256"])
    if point.logical_graph_sha256 != _logical_graph_sha256(nodes):
        raise Stage2CError("private point-A logical graph digest is invalid")
    return point


def _point_b_dict(point: PointBState) -> dict[str, object]:
    return {
        "table": point.table,
        "metadataLocation": point.metadata_location,
        "snapshotId": point.snapshot_id,
        "rowsSha256": point.rows_sha256,
        "nodes": [_node_dict(node) for node in point.nodes],
    }


def _point_b_from_dict(raw: object) -> PointBState:
    if not isinstance(raw, dict) or set(raw) != {
        "table",
        "metadataLocation",
        "snapshotId",
        "rowsSha256",
        "nodes",
    }:
        raise Stage2CError("private point-B contract has an unexpected shape")
    nodes_raw = raw["nodes"]
    if (
        not isinstance(raw["table"], str)
        or not isinstance(raw["metadataLocation"], str)
        or isinstance(raw["snapshotId"], bool)
        or not isinstance(raw["snapshotId"], int)
        or not isinstance(raw["rowsSha256"], str)
        or not _SHA256.fullmatch(raw["rowsSha256"])
        or not isinstance(nodes_raw, list)
        or not nodes_raw
    ):
        raise Stage2CError("private point-B values are invalid")
    return PointBState(
        raw["table"],
        raw["metadataLocation"],
        raw["snapshotId"],
        raw["rowsSha256"],
        tuple(_node_from_dict(item) for item in nodes_raw),
    )


def _binding(configuration: Mapping[str, object]) -> PlanBinding:
    completed = _bounded_run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    revision = completed.stdout.strip()
    if completed.returncode != 0 or re.fullmatch(r"[0-9a-f]{40,64}", revision) is None:
        raise Stage2CError("source revision could not be pinned")
    try:
        return PlanBinding(
            source_revision=revision,
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            stage1_script_sha256=hashlib.sha256(Path(ir.__file__).read_bytes()).hexdigest(),
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            pyiceberg_version=importlib.metadata.version("pyiceberg"),
            pyarrow_version=importlib.metadata.version("pyarrow"),
            configuration_sha256=_digest(configuration),
        )
    except (OSError, importlib.metadata.PackageNotFoundError) as exc:
        raise Stage2CError("Stage 2C runtime could not be pinned") from exc


def _binding_dict(binding: PlanBinding) -> dict[str, str]:
    return {
        "sourceRevision": binding.source_revision,
        "scriptSha256": binding.script_sha256,
        "stage1ScriptSha256": binding.stage1_script_sha256,
        "pythonVersion": binding.python_version,
        "pyicebergVersion": binding.pyiceberg_version,
        "pyarrowVersion": binding.pyarrow_version,
        "configurationSha256": binding.configuration_sha256,
    }


def _secret_binding(settings: ir.RecoverySettings, scope: JointScope) -> str:
    return hmac.new(
        settings.run_secret.encode(),
        f"databox-stage2c:{scope.run_id}:secret-binding".encode(),
        hashlib.sha256,
    ).hexdigest()


def _resources(scope: JointScope) -> dict[str, str]:
    stem = f"databox-stage2c-{scope.run_id}"
    return {
        "network": f"{stem}-net",
        "sourceVolume": f"{stem}-source",
        "restoredVolume": f"{stem}-restored",
        "repositoryVolume": f"{stem}-repo",
        "sourcePostgres": f"{stem}-source-postgres",
        "sourcePolaris": f"{stem}-source-polaris",
        "bootstrap": f"{stem}-bootstrap",
        "restoredPostgres": f"{stem}-restored-postgres",
        "restoredPolaris": f"{stem}-restored-polaris",
    }


def _contract() -> dict[str, object]:
    return {
        "oneCycle": True,
        "liveObjectiveSeconds": _LIVE_OBJECTIVE_SECONDS,
        "deadlineAfterDamageForcesCompensation": True,
        "compensationIgnoresObjective": True,
        "commandTimeoutSeconds": _COMMAND_TIMEOUT_SECONDS,
        "serviceProcessTimeoutSeconds": _SERVICE_PROCESS_TIMEOUT_SECONDS,
        "tableCount": 2,
        "pointARowsPerTable": 3,
        "pointBAppendsPerTable": 1,
        "maxKeysIncludingCanary": _MAX_KEYS,
        "maxGraphBytes": _MAX_BYTES,
        "maxVersionsPerKey": _MAX_VERSIONS,
        "operations": [
            "verify-non-root-pinned-operator-and-bucket-protection",
            "verify-empty-generated-prefix-and-absent-generated-docker-resources",
            "canary-ordinary-delete-and-exact-version-promotion",
            "create-isolated-postgres-and-polaris",
            "create-two-deterministic-point-a-tables",
            "capture-disjoint-point-a-graphs-and-exact-versions",
            "local-posix-full-backup-and-named-target",
            "append-point-b-to-both-tables-and-archive-marker",
            "publish-exact-recovery-plan-and-damage-journal",
            "ordinary-delete-selected-live-point-a-dependencies",
            "prove-both-point-b-tables-fail-on-approved-missing-objects",
            "restore-isolated-catalog-to-point-a",
            "promote-exact-point-a-s3-versions",
            "validate-two-table-point-a-equality-through-restored-polaris",
            "contain-credential-bearing-containers",
        ],
        "prohibited": [
            "active-or-canonical-service",
            "deployed-catalog-backup-repository",
            "catalog-backup-credentials",
            "delete-object-version",
            "delete-marker-removal",
            "bucket-control-change",
            "iam-change",
            "cutover",
            "automatic-cleanup",
            "second-damage-cycle",
        ],
    }


def _atomic_private_write(path: Path, value: object) -> None:
    payload = _canonical_json(value)
    if len(payload) > _MAX_PRIVATE_BYTES:
        raise Stage2CError("private Stage 2C evidence exceeds its size limit")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
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
            raise Stage2CError("private Stage 2C evidence already exists") from exc
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)


def _atomic_private_replace(path: Path, value: object) -> None:
    payload = _canonical_json(value)
    if len(payload) > _MAX_PRIVATE_BYTES:
        raise Stage2CError("private Stage 2C evidence exceeds its size limit")
    temp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)


def _read_private(path: Path, expected_sha256: str) -> dict[str, object]:
    if _SHA256.fullmatch(expected_sha256) is None:
        raise Stage2CError("approved Stage 2C plan digest is invalid")
    try:
        details = path.lstat()
        if (
            not stat.S_ISREG(details.st_mode)
            or stat.S_IMODE(details.st_mode) != 0o600
            or details.st_size > _MAX_PRIVATE_BYTES
        ):
            raise Stage2CError("private Stage 2C plan is unsafe")
        payload = path.read_bytes()
    except OSError as exc:
        raise Stage2CError("private Stage 2C plan is unavailable") from exc
    if not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), expected_sha256):
        raise Stage2CError("private Stage 2C plan digest differs from approval")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise Stage2CError("private Stage 2C plan is invalid JSON") from exc
    if not isinstance(value, dict):
        raise Stage2CError("private Stage 2C plan has an unexpected shape")
    return value


def prepare_plan(
    *,
    settings: ir.RecoverySettings,
    evidence_root: Path = _EVIDENCE_ROOT,
    token_factory: Callable[[], str] = lambda: secrets.token_hex(8),
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    image_inspector: Callable[[str], ir.ImagePin] = _inspect_image,
    docker_fingerprint: Callable[[], str] = _docker_fingerprint,
) -> dict[str, object]:
    """Write one mutation-free, exact Stage 2C campaign plan."""
    scope = _scope(token_factory())
    created = clock().astimezone(UTC)
    images = {
        name: image_inspector(reference).as_manifest()
        for name, reference in (
            ("postgres", _POSTGRES_IMAGE),
            ("polarisAdmin", _ADMIN_IMAGE),
            ("polaris", _POLARIS_IMAGE),
        )
    }
    stack = {
        "resources": _resources(scope),
        "images": images,
        "dockerRuntimeSha256": docker_fingerprint(),
        "secretBindingSha256": _secret_binding(settings, scope),
    }
    target = {
        "bucket": settings.bucket,
        "region": settings.region,
        "profile": settings.profile,
        "identitySha256": settings.identity_sha256,
        "storageRoleArn": settings.storage_role_arn,
        "expectedOwner": settings.storage_role_arn.split(":", 5)[4],
    }
    configuration = {"scope": _scope_dict(scope), "stack": stack, "target": target}
    plan = {
        "schemaVersion": 1,
        "planType": "stage-2c-campaign",
        "createdAt": created.isoformat().replace("+00:00", "Z"),
        "expiresAt": (created + _PLAN_LIFETIME).isoformat().replace("+00:00", "Z"),
        "scope": _scope_dict(scope),
        "target": target,
        "stack": stack,
        "runtime": _binding_dict(_binding(configuration)),
        "contract": _contract(),
    }
    path = evidence_root / scope.run_id / "campaign.plan.json"
    _atomic_private_write(path, plan)
    payload = path.read_bytes()
    return {
        "status": "planned",
        "runId": scope.run_id,
        "plan": str(path),
        "planSha256": hashlib.sha256(payload).hexdigest(),
    }


_IMAGE_REFERENCES = {
    "postgres": _POSTGRES_IMAGE,
    "polarisAdmin": _ADMIN_IMAGE,
    "polaris": _POLARIS_IMAGE,
}


def _planned_images(stack: Mapping[str, object]) -> dict[str, ir.ImagePin]:
    raw = stack.get("images")
    if not isinstance(raw, dict) or set(raw) != set(_IMAGE_REFERENCES):
        raise Stage2CError("private Stage 2C image pins are invalid")
    try:
        return {
            name: ir._image_pin_from_manifest(raw[name], reference=reference)
            for name, reference in _IMAGE_REFERENCES.items()
        }
    except ir.DrillError as exc:
        raise Stage2CError("private Stage 2C image pins are invalid") from exc


def _validate_stored_runtime(runtime: object, *, configuration: Mapping[str, object]) -> None:
    if not isinstance(runtime, dict) or set(runtime) != {
        "sourceRevision",
        "scriptSha256",
        "stage1ScriptSha256",
        "pythonVersion",
        "pyicebergVersion",
        "pyarrowVersion",
        "configurationSha256",
    }:
        raise Stage2CError("private Stage 2C runtime binding is invalid")
    if (
        not isinstance(runtime["sourceRevision"], str)
        or re.fullmatch(r"[0-9a-f]{40,64}", runtime["sourceRevision"]) is None
        or any(
            not isinstance(runtime[name], str) or _SHA256.fullmatch(runtime[name]) is None
            for name in ("scriptSha256", "stage1ScriptSha256")
        )
        or runtime.get("configurationSha256") != _digest(configuration)
        or any(
            not isinstance(runtime[name], str) or not runtime[name]
            for name in ("pythonVersion", "pyicebergVersion", "pyarrowVersion")
        )
    ):
        raise Stage2CError("private Stage 2C runtime binding is invalid")


def _parse_campaign_plan(
    path: Path,
    expected_sha256: str,
    *,
    settings: ir.RecoverySettings,
    restore_only: bool = False,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    image_inspector: Callable[[str], ir.ImagePin] = _inspect_image,
    docker_fingerprint: Callable[[], str] = _docker_fingerprint,
) -> tuple[dict[str, object], JointScope, str]:
    plan = _read_private(path, expected_sha256)
    if (
        set(plan)
        != {
            "schemaVersion",
            "planType",
            "createdAt",
            "expiresAt",
            "scope",
            "target",
            "stack",
            "runtime",
            "contract",
        }
        or plan.get("schemaVersion") != 1
        or plan.get("planType") != "stage-2c-campaign"
    ):
        raise Stage2CError("private Stage 2C campaign plan has an unexpected shape")
    raw_scope = plan["scope"]
    if not isinstance(raw_scope, dict) or not isinstance(raw_scope.get("runId"), str):
        raise Stage2CError("private Stage 2C scope is invalid")
    scope = _scope(raw_scope["runId"])
    if raw_scope != _scope_dict(scope) or path.parent.name != scope.run_id:
        raise Stage2CError("private Stage 2C scope is not generated")
    target = plan["target"]
    expected_target = {
        "bucket": settings.bucket,
        "region": settings.region,
        "profile": settings.profile,
        "identitySha256": settings.identity_sha256,
        "storageRoleArn": settings.storage_role_arn,
        "expectedOwner": settings.storage_role_arn.split(":", 5)[4],
    }
    if target != expected_target:
        raise Stage2CError("private Stage 2C target differs from current settings")
    stack = plan["stack"]
    if (
        not isinstance(stack, dict)
        or set(stack)
        != {
            "resources",
            "images",
            "dockerRuntimeSha256",
            "secretBindingSha256",
        }
        or stack.get("resources") != _resources(scope)
        or not isinstance(stack.get("secretBindingSha256"), str)
        or _SHA256.fullmatch(stack["secretBindingSha256"]) is None
        or not isinstance(stack.get("dockerRuntimeSha256"), str)
        or _SHA256.fullmatch(stack["dockerRuntimeSha256"]) is None
    ):
        raise Stage2CError("private Stage 2C resources or bindings are invalid")
    images = _planned_images(stack)
    if not restore_only:
        if stack["secretBindingSha256"] != _secret_binding(settings, scope):
            raise Stage2CError("private Stage 2C secret binding is invalid")
        for name, reference in _IMAGE_REFERENCES.items():
            if image_inspector(reference).as_manifest() != images[name].as_manifest():
                raise Stage2CError("current Docker image differs from Stage 2C plan")
        if stack["dockerRuntimeSha256"] != docker_fingerprint():
            raise Stage2CError("current Docker runtime differs from Stage 2C plan")
    if plan["contract"] != _contract():
        raise Stage2CError("private Stage 2C operation contract is invalid")
    configuration = {"scope": raw_scope, "stack": stack, "target": target}
    _validate_stored_runtime(plan["runtime"], configuration=configuration)
    if not restore_only and plan["runtime"] != _binding_dict(_binding(configuration)):
        raise Stage2CError("current source/runtime differs from Stage 2C plan")
    try:
        created = datetime.fromisoformat(str(plan["createdAt"]).replace("Z", "+00:00"))
        expires = datetime.fromisoformat(str(plan["expiresAt"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise Stage2CError("private Stage 2C timestamps are invalid") from exc
    now = clock().astimezone(UTC)
    if expires - created != _PLAN_LIFETIME or (
        not restore_only and (now < created or now > expires)
    ):
        raise Stage2CError("private Stage 2C plan is outside its approval window")
    return plan, scope, expected_sha256


def _complete_nodes(
    canary: ir.GraphNode,
    point_a: Sequence[TablePoint],
    point_b: Sequence[PointBState],
) -> dict[str, ir.GraphNode]:
    current = {canary.key: canary}
    for point in point_a:
        for node in point.capture.nodes:
            if node.key == canary.key:
                raise Stage2CError("Stage 2C canary collides with a table graph")
            current.setdefault(node.key, node)
    for point in point_b:
        for node in point.nodes:
            if node.key == canary.key:
                raise Stage2CError("Stage 2C canary collides with a table graph")
            current[node.key] = node
    if len(current) > _MAX_KEYS:
        raise Stage2CError("complete Stage 2C prefix exceeds the aggregate key limit")
    if sum(node.size for node in current.values()) > _MAX_BYTES:
        raise Stage2CError("complete Stage 2C prefix exceeds the aggregate byte limit")
    return current


def _complete_aggregate(
    canary: ir.GraphNode,
    point_a: Sequence[TablePoint],
    point_b: Sequence[PointBState],
) -> dict[str, int]:
    complete = _complete_nodes(canary, point_a, point_b)
    point_a_nodes = {node.key: node for point in point_a for node in point.capture.nodes}
    return {
        "pointAGraphKeys": len(point_a_nodes),
        "pointAGraphBytes": sum(node.size for node in point_a_nodes.values()),
        "completeKeysIncludingCanary": len(complete),
        "completeBytesIncludingCanary": sum(node.size for node in complete.values()),
    }


def _recovery_plan(
    *,
    campaign_sha256: str,
    scope: JointScope,
    bucket: str,
    canary: ir.GraphNode,
    point_a: Sequence[TablePoint],
    target: RecoveryTarget,
    point_b: Sequence[PointBState],
) -> dict[str, object]:
    _validate_point_a(scope, point_a)
    b_only = _validate_point_b(point_a, point_b)
    damage_nodes = _damage_nodes(point_a, point_b)
    if canary.key != f"{scope.prefix}/capability-canary.bin":
        raise Stage2CError("Stage 2C canary is outside the exact generated key")
    aggregate = _complete_aggregate(canary, point_a, point_b)
    return {
        "schemaVersion": 1,
        "planType": "stage-2c-recovery",
        "parentCampaignSha256": campaign_sha256,
        "scope": _scope_dict(scope),
        "bucket": bucket,
        "canary": _node_dict(canary),
        "pointA": [_capture_dict(point) for point in point_a],
        "pointB": [_point_b_dict(point) for point in point_b],
        "pointBOnlyKeys": sorted(b_only),
        "damageNodes": [_node_dict(node) for node in damage_nodes],
        "target": {"name": target.name},
        "aggregate": aggregate,
    }


def _parse_recovery_plan(
    path: Path,
    *,
    campaign_sha256: str,
    scope: JointScope,
    bucket: str,
) -> tuple[
    dict[str, object],
    tuple[TablePoint, TablePoint],
    tuple[PointBState, PointBState],
    RecoveryTarget,
    tuple[ir.GraphNode, ...],
]:
    payload = path.read_bytes()
    raw = _read_private(path, hashlib.sha256(payload).hexdigest())
    if (
        set(raw)
        != {
            "schemaVersion",
            "planType",
            "parentCampaignSha256",
            "scope",
            "bucket",
            "canary",
            "pointA",
            "pointB",
            "pointBOnlyKeys",
            "damageNodes",
            "target",
            "aggregate",
        }
        or raw.get("schemaVersion") != 1
        or raw.get("planType") != "stage-2c-recovery"
    ):
        raise Stage2CError("private Stage 2C recovery plan has an unexpected shape")
    if (
        raw.get("parentCampaignSha256") != campaign_sha256
        or raw.get("scope") != _scope_dict(scope)
        or raw.get("bucket") != bucket
    ):
        raise Stage2CError("private Stage 2C recovery plan differs from campaign")
    point_a_raw = raw["pointA"]
    point_b_raw = raw["pointB"]
    if not isinstance(point_a_raw, list) or not isinstance(point_b_raw, list):
        raise Stage2CError("private Stage 2C point contracts are invalid")
    point_a = tuple(_capture_from_dict(item, bucket) for item in point_a_raw)
    point_b = tuple(_point_b_from_dict(item) for item in point_b_raw)
    if len(point_a) != 2 or len(point_b) != 2:
        raise Stage2CError("private Stage 2C recovery plan requires two tables")
    _validate_point_a(scope, point_a)
    b_only = _validate_point_b(point_a, point_b)
    damage_raw = raw["damageNodes"]
    if not isinstance(damage_raw, list):
        raise Stage2CError("private Stage 2C damage selection is invalid")
    nodes = tuple(_node_from_dict(item) for item in damage_raw)
    if nodes != _damage_nodes(point_a, point_b):
        raise Stage2CError("private Stage 2C damage selection is invalid")
    if raw["pointBOnlyKeys"] != sorted(b_only):
        raise Stage2CError("private Stage 2C point-B-only inventory is invalid")
    canary = _node_from_dict(raw["canary"])
    if canary.key != f"{scope.prefix}/capability-canary.bin":
        raise Stage2CError("private Stage 2C canary is invalid")
    aggregate = raw["aggregate"]
    if aggregate != _complete_aggregate(canary, point_a, point_b):
        raise Stage2CError("private Stage 2C aggregate limits are invalid")
    target = raw["target"]
    if (
        not isinstance(target, dict)
        or set(target) != {"name"}
        or not isinstance(target["name"], str)
    ):
        raise Stage2CError("private Stage 2C recovery target is invalid")
    return raw, point_a, point_b, RecoveryTarget(target["name"]), nodes


def _initial_journal(
    campaign_sha256: str, recovery_sha256: str, scope: JointScope, nodes: Sequence[ir.GraphNode]
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "campaignSha256": campaign_sha256,
        "recoveryPlanSha256": recovery_sha256,
        "runId": scope.run_id,
        "restoreOnly": True,
        "milestones": {
            "deletes": "pending",
            "breakProof": "pending",
            "catalogRestore": "pending",
            "objectRestore": "pending",
            "finalValidation": "pending",
            "containment": "pending",
        },
        "nodes": [
            {
                "key": node.key,
                "sourceVersionId": node.source_version_id,
                "phase": "pending",
                "deleteMarkerVersionId": None,
                "promotedVersionId": None,
            }
            for node in nodes
        ],
    }


def _journal_entries(
    journal: Mapping[str, object], nodes: Sequence[ir.GraphNode]
) -> dict[str, dict[str, object]]:
    raw = journal.get("nodes")
    if not isinstance(raw, list) or len(raw) != len(nodes):
        raise Stage2CError("Stage 2C damage journal graph differs from plan")
    result: dict[str, dict[str, object]] = {}
    for item, node in zip(raw, nodes, strict=True):
        if (
            not isinstance(item, dict)
            or set(item)
            != {
                "key",
                "sourceVersionId",
                "phase",
                "deleteMarkerVersionId",
                "promotedVersionId",
            }
            or item.get("key") != node.key
            or item.get("sourceVersionId") != node.source_version_id
        ):
            raise Stage2CError("Stage 2C damage journal node differs from plan")
        phase = item.get("phase")
        if phase not in {
            "pending",
            "delete-intent",
            "deleted",
            "promotion-intent",
            "promoted",
        }:
            raise Stage2CError("Stage 2C damage journal phase is invalid")
        delete_marker = item.get("deleteMarkerVersionId")
        promoted = item.get("promotedVersionId")
        if (
            (delete_marker is not None and not isinstance(delete_marker, str))
            or (promoted is not None and not isinstance(promoted, str))
            or (isinstance(delete_marker, str) and not 1 <= len(delete_marker) <= 1024)
            or (isinstance(promoted, str) and not 1 <= len(promoted) <= 1024)
            or (phase in {"pending", "delete-intent"} and (delete_marker or promoted))
            or (phase == "deleted" and (not delete_marker or promoted))
            or (phase == "promotion-intent" and promoted)
            or (phase == "promoted" and not promoted)
        ):
            raise Stage2CError("Stage 2C damage journal receipts are invalid")
        result[node.key] = item
    return result


def _read_journal(
    path: Path, recovery_sha256: str, scope: JointScope, nodes: Sequence[ir.GraphNode]
) -> dict[str, object]:
    raw = _read_private(path, hashlib.sha256(path.read_bytes()).hexdigest())
    milestones = raw.get("milestones")
    if (
        set(raw)
        != {
            "schemaVersion",
            "campaignSha256",
            "recoveryPlanSha256",
            "runId",
            "restoreOnly",
            "milestones",
            "nodes",
        }
        or raw.get("schemaVersion") != 1
        or not isinstance(raw.get("campaignSha256"), str)
        or not _SHA256.fullmatch(raw["campaignSha256"])
        or raw.get("recoveryPlanSha256") != recovery_sha256
        or raw.get("runId") != scope.run_id
        or raw.get("restoreOnly") is not True
        or not isinstance(milestones, dict)
        or set(milestones)
        != {
            "deletes",
            "breakProof",
            "catalogRestore",
            "objectRestore",
            "finalValidation",
            "containment",
        }
        or not all(
            value in {"pending", "complete", "passed", "failed"} for value in milestones.values()
        )
    ):
        raise Stage2CError("Stage 2C damage journal differs from recovery plan")
    _journal_entries(raw, nodes)
    return raw


def _set_milestone(journal: dict[str, object], path: Path, name: str, value: str) -> None:
    milestones = journal.get("milestones")
    if not isinstance(milestones, dict) or name not in milestones:
        raise Stage2CError("Stage 2C damage milestone is invalid")
    updated = dict(milestones)
    updated[name] = value
    candidate = dict(journal)
    candidate["milestones"] = updated
    _atomic_private_replace(path, candidate)
    journal["milestones"] = updated


def _matches(node: ir.GraphNode, state: ir.ObjectState) -> bool:
    return (
        state.exists
        and not state.delete_marker
        and state.size == node.size
        and state.sha256 == node.sha256
    )


def _restore_only(
    operations: JointRecoveryOperations,
    nodes: Sequence[ir.GraphNode],
    journal: dict[str, object],
    journal_path: Path,
    *,
    objective_check: Callable[[], None] | None = None,
) -> None:
    entries = _journal_entries(journal, nodes)
    for node in sorted(nodes, key=lambda item: (-item.depth, item.key)):
        if objective_check is not None:
            objective_check()
        entry = entries[node.key]
        state = operations.current_state(node)
        phase = entry["phase"]
        if phase == "pending":
            if not (_matches(node, state) and state.version_id == node.source_version_id):
                raise Stage2CError("untouched Stage 2C object has unknown state")
            continue
        if phase == "promoted":
            if not (_matches(node, state) and state.version_id == entry.get("promotedVersionId")):
                raise Stage2CError("promoted Stage 2C object has unknown state")
            continue
        if (
            phase == "delete-intent"
            and _matches(node, state)
            and state.version_id == node.source_version_id
        ):
            entry["phase"] = "pending"
            _atomic_private_replace(journal_path, journal)
            continue
        if (
            phase == "promotion-intent"
            and _matches(node, state)
            and state.version_id != node.source_version_id
        ):
            entry["phase"] = "promoted"
            entry["promotedVersionId"] = state.version_id
            _atomic_private_replace(journal_path, journal)
            continue
        if state.exists or not state.delete_marker:
            raise Stage2CError("damaged Stage 2C object has unknown current state")
        marker = entry.get("deleteMarkerVersionId")
        if marker is not None and state.version_id != marker:
            raise Stage2CError("damaged Stage 2C object has unknown delete marker")
        entry["phase"] = "promotion-intent"
        _atomic_private_replace(journal_path, journal)
        restored = operations.restore_object(node)
        if objective_check is not None:
            objective_check()
        if (
            not _matches(node, restored)
            or not restored.version_id
            or restored.version_id == node.source_version_id
        ):
            raise Stage2CError("Stage 2C exact-version promotion did not verify")
        entry["phase"] = "promoted"
        entry["promotedVersionId"] = restored.version_id
        _atomic_private_replace(journal_path, journal)
    _set_milestone(journal, journal_path, "objectRestore", "complete")


def _validate_final(
    expected: Sequence[TablePoint], actual: Sequence[TablePoint], point_b: Sequence[PointBState]
) -> None:
    if len(actual) != 2:
        raise Stage2CError("restored Stage 2C catalog did not return two tables")
    b_only = set().union(*(set(item.graph_keys) for item in point_b)) - set().union(
        *({node.key for node in item.capture.nodes} for item in expected)
    )
    for wanted, observed in zip(expected, actual, strict=True):
        if (
            observed.table != wanted.table
            or observed.capture.table_uuid != wanted.capture.table_uuid
            or observed.capture.metadata_location != wanted.capture.metadata_location
            or observed.capture.snapshot_id != wanted.capture.snapshot_id
            or observed.capture.schema_sha256 != wanted.capture.schema_sha256
            or observed.capture.row_count != wanted.capture.row_count
            or observed.capture.rows_sha256 != wanted.capture.rows_sha256
            or observed.logical_graph_sha256 != wanted.logical_graph_sha256
            or {_logical_node(node)["key"]: _logical_node(node) for node in observed.capture.nodes}
            != {_logical_node(node)["key"]: _logical_node(node) for node in wanted.capture.nodes}
        ):
            raise Stage2CError("restored Stage 2C table differs from exact point A")
        if {node.key for node in observed.capture.nodes}.intersection(b_only):
            raise Stage2CError("restored Stage 2C catalog still references point-B-only objects")


def _error_kind(error: BaseException | None) -> str | None:
    if error is None:
        return None
    name = type(error).__name__
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()
    return normalized if re.fullmatch(r"[a-z0-9-]{1,80}", normalized) else "unclassified"


def _failure_summary(journal: Mapping[str, object] | None) -> dict[str, object]:
    if journal is None:
        return {"present": False}
    milestones = journal.get("milestones")
    raw_nodes = journal.get("nodes")
    if not isinstance(milestones, dict) or not isinstance(raw_nodes, list):
        return {"present": True, "readable": False}
    phases = {
        name: 0 for name in ("pending", "delete-intent", "deleted", "promotion-intent", "promoted")
    }
    for item in raw_nodes:
        phase = item.get("phase") if isinstance(item, dict) else None
        if phase not in phases:
            return {"present": True, "readable": False}
        phases[phase] += 1
    return {
        "present": True,
        "readable": True,
        "milestones": dict(milestones),
        "nodePhaseCounts": phases,
    }


def _write_failure_receipt(
    path: Path,
    *,
    campaign_sha256: str,
    recovery_sha256: str | None,
    primary: BaseException,
    catalog_error: BaseException | None,
    object_error: BaseException | None,
    containment_error: BaseException | None,
    journal: Mapping[str, object] | None,
    clock: Callable[[], datetime],
) -> None:
    _atomic_private_write(
        path,
        {
            "schemaVersion": 1,
            "status": "failed-contained" if containment_error is None else "failed-uncertain",
            "stage": "2c",
            "campaignSha256": campaign_sha256,
            "recoveryPlanSha256": recovery_sha256,
            "primaryErrorKind": _error_kind(primary),
            "catalogCompensationErrorKind": _error_kind(catalog_error),
            "objectCompensationErrorKind": _error_kind(object_error),
            "containmentErrorKind": _error_kind(containment_error),
            "damage": _failure_summary(journal),
            "recordedAt": clock().astimezone(UTC).isoformat().replace("+00:00", "Z"),
        },
    )


@contextmanager
def _execution_lock(run_dir: Path) -> Iterator[None]:
    run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(run_dir, 0o700)
    lock_path = run_dir / "execution.lock"
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise Stage2CError("Stage 2C execution lock is unsafe") from exc
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or stat.S_IMODE(details.st_mode) != 0o600:
            raise Stage2CError("Stage 2C execution lock is unsafe")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Stage2CError("another Stage 2C execution owns this run") from exc
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _reject_terminal_replay(run_dir: Path) -> None:
    terminal = tuple(
        name
        for name in ("result.json", "failure.json", "restoration-only.json")
        if (run_dir / name).exists()
    )
    if terminal:
        raise Stage2CError("Stage 2C campaign already has terminal evidence")


def _journal_is_terminal(journal: Mapping[str, object]) -> bool:
    milestones = journal.get("milestones")
    if not isinstance(milestones, dict):
        raise Stage2CError("Stage 2C damage journal milestones are invalid")
    return milestones.get("containment") != "pending"


def execute_campaign(
    *,
    settings: ir.RecoverySettings,
    plan_path: Path,
    expected_sha256: str,
    operations_factory: Callable[[dict[str, object], JointScope, Path], JointRecoveryOperations],
    monotonic: Callable[[], float] = time.monotonic,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    image_inspector: Callable[[str], ir.ImagePin] = _inspect_image,
    docker_fingerprint: Callable[[], str] = _docker_fingerprint,
) -> dict[str, object]:
    """Execute one exact Stage 2C cycle, or restore-only after valid damage."""
    run_dir = plan_path.parent
    with _execution_lock(run_dir):
        _reject_terminal_replay(run_dir)
        return _execute_campaign_locked(
            settings=settings,
            plan_path=plan_path,
            expected_sha256=expected_sha256,
            operations_factory=operations_factory,
            monotonic=monotonic,
            clock=clock,
            image_inspector=image_inspector,
            docker_fingerprint=docker_fingerprint,
        )


def _execute_campaign_locked(
    *,
    settings: ir.RecoverySettings,
    plan_path: Path,
    expected_sha256: str,
    operations_factory: Callable[[dict[str, object], JointScope, Path], JointRecoveryOperations],
    monotonic: Callable[[], float],
    clock: Callable[[], datetime],
    image_inspector: Callable[[str], ir.ImagePin],
    docker_fingerprint: Callable[[], str],
) -> dict[str, object]:
    started = monotonic()
    run_dir = plan_path.parent
    recovery_path = run_dir / "recovery.plan.json"
    journal_path = run_dir / "damage-journal.json"
    if recovery_path.exists() != journal_path.exists():
        raise Stage2CError("Stage 2C recovery plan and damage journal are incomplete")
    restore_only_entry = recovery_path.exists()
    campaign, scope, campaign_sha = _parse_campaign_plan(
        plan_path,
        expected_sha256,
        settings=settings,
        restore_only=restore_only_entry,
        clock=clock,
        image_inspector=image_inspector,
        docker_fingerprint=docker_fingerprint,
    )
    recovery_sha = ""
    journal: dict[str, object] | None = None
    resume_bundle: tuple[RecoveryTarget, tuple[ir.GraphNode, ...]] | None = None
    if restore_only_entry:
        recovery_sha = hashlib.sha256(recovery_path.read_bytes()).hexdigest()
        _, _point_a, _point_b, target, nodes = _parse_recovery_plan(
            recovery_path,
            campaign_sha256=campaign_sha,
            scope=scope,
            bucket=settings.bucket,
        )
        journal = _read_journal(journal_path, recovery_sha, scope, nodes)
        if _journal_is_terminal(journal):
            raise Stage2CError("Stage 2C damage journal is already terminal")
        resume_bundle = (target, nodes)
    operations = operations_factory(campaign, scope, run_dir)
    damaged = False
    restore_only_completed = False

    def live_deadline() -> None:
        if monotonic() - started > _LIVE_OBJECTIVE_SECONDS:
            raise Stage2CError("Stage 2C success objective expired")

    try:
        if resume_bundle is not None:
            target, nodes = resume_bundle
            if journal is None:
                raise Stage2CError("Stage 2C restore-only journal is unavailable")
            damaged = True
            operations.stop_source()
            operations.restore_catalog(target)
            _set_milestone(journal, journal_path, "catalogRestore", "complete")
            _restore_only(operations, nodes, journal, journal_path)
            restore_only_completed = True
            raise Stage2CError("interrupted Stage 2C run completed restoration only")

        live_deadline()
        canary = operations.preflight(scope)
        live_deadline()
        point_a = operations.create_point_a(scope)
        _validate_point_a(scope, point_a)
        live_deadline()
        target = operations.backup_point_a()
        live_deadline()
        point_b = operations.append_point_b(point_a)
        _validate_point_b(point_a, point_b)
        operations.verify_prefix_inventory(canary, point_a, point_b)
        recovery = _recovery_plan(
            campaign_sha256=campaign_sha,
            scope=scope,
            bucket=settings.bucket,
            canary=canary,
            point_a=point_a,
            target=target,
            point_b=point_b,
        )
        _atomic_private_write(recovery_path, recovery)
        recovery_sha = hashlib.sha256(recovery_path.read_bytes()).hexdigest()
        _, point_a, point_b, target, nodes = _parse_recovery_plan(
            recovery_path,
            campaign_sha256=campaign_sha,
            scope=scope,
            bucket=settings.bucket,
        )
        live_deadline()
        journal = _initial_journal(campaign_sha, recovery_sha, scope, nodes)
        _atomic_private_write(journal_path, journal)
        damaged = True
        entries = _journal_entries(journal, nodes)
        for node in sorted(nodes, key=lambda item: (-item.depth, item.key)):
            live_deadline()
            state = operations.predelete_state(node)
            if not _matches(node, state) or state.version_id != node.source_version_id:
                raise Stage2CError("Stage 2C graph changed immediately before deletion")
            entry = entries[node.key]
            entry["phase"] = "delete-intent"
            _atomic_private_replace(journal_path, journal)
            deleted = operations.delete_current(node)
            live_deadline()
            if not deleted.delete_marker or not deleted.version_id:
                raise Stage2CError("Stage 2C ordinary delete returned no marker")
            observed = operations.current_state(node)
            if (
                observed.exists
                or not observed.delete_marker
                or observed.version_id != deleted.version_id
            ):
                raise Stage2CError("Stage 2C ordinary delete marker did not verify")
            entry["phase"] = "deleted"
            entry["deleteMarkerVersionId"] = deleted.version_id
            _atomic_private_replace(journal_path, journal)
        _set_milestone(journal, journal_path, "deletes", "complete")
        live_deadline()
        operations.prove_point_b_broken(point_b, nodes)
        live_deadline()
        _set_milestone(journal, journal_path, "breakProof", "passed")
        operations.stop_source()
        live_deadline()
        operations.restore_catalog(target)
        live_deadline()
        _set_milestone(journal, journal_path, "catalogRestore", "complete")
        _restore_only(
            operations,
            nodes,
            journal,
            journal_path,
            objective_check=live_deadline,
        )
        live_deadline()
        actual = operations.validate_restored(point_a, point_b)
        live_deadline()
        _validate_final(point_a, actual, point_b)
        operations.verify_prefix_inventory(canary, point_a, point_b)
        live_deadline()
        _set_milestone(journal, journal_path, "finalValidation", "passed")
        operations.contain()
        live_deadline()
        _set_milestone(journal, journal_path, "containment", "passed")
        live_deadline()
        result = {
            "schemaVersion": 1,
            "status": "pass",
            "stage": "2c",
            "runId": scope.run_id,
            "campaignSha256": campaign_sha,
            "recoveryPlanSha256": recovery_sha,
            "tableCount": 2,
            "pointARowsPerTable": 3,
            "pointBExcluded": True,
            "catalogPointA": True,
            "warehousePointA": True,
            "containersAbsent": True,
            "retainedEvidence": True,
        }
        _atomic_private_write(run_dir / "result.json", result)
        return result
    except BaseException as primary:
        catalog_error: BaseException | None = None
        object_error: BaseException | None = None
        containment_error: BaseException | None = None
        if (
            damaged
            and not restore_only_completed
            and journal is not None
            and recovery_path.exists()
        ):
            try:
                _, _point_a, _point_b, target, nodes = _parse_recovery_plan(
                    recovery_path,
                    campaign_sha256=campaign_sha,
                    scope=scope,
                    bucket=settings.bucket,
                )
            except BaseException as exc:
                object_error = exc
            else:
                try:
                    operations.stop_source()
                    operations.restore_catalog(target)
                    _set_milestone(journal, journal_path, "catalogRestore", "complete")
                except BaseException as exc:
                    catalog_error = exc
                try:
                    _restore_only(operations, nodes, journal, journal_path)
                except BaseException as exc:
                    object_error = exc
        try:
            operations.contain()
            if journal is not None:
                _set_milestone(journal, journal_path, "containment", "passed")
        except BaseException as exc:
            containment_error = exc
            if journal is not None:
                try:
                    _set_milestone(journal, journal_path, "containment", "failed")
                except BaseException:
                    pass
        if restore_only_completed:
            try:
                _atomic_private_write(
                    run_dir / "restoration-only.json",
                    {
                        "schemaVersion": 1,
                        "status": (
                            "restored-and-contained"
                            if containment_error is None
                            else "restored-containment-uncertain"
                        ),
                        "stage": "2c",
                        "campaignSha256": campaign_sha,
                        "recoveryPlanSha256": recovery_sha,
                        "containmentErrorKind": _error_kind(containment_error),
                        "damage": _failure_summary(journal),
                        "recordedAt": clock().astimezone(UTC).isoformat().replace("+00:00", "Z"),
                    },
                )
            except BaseException as exc:
                raise Stage2CError(
                    "mandatory Stage 2C restoration-only evidence is incomplete"
                ) from exc
            if containment_error is not None:
                raise Stage2CError("mandatory Stage 2C containment is incomplete") from (
                    containment_error
                )
            raise primary
        receipt_error: BaseException | None = None
        try:
            _write_failure_receipt(
                run_dir / "failure.json",
                campaign_sha256=campaign_sha,
                recovery_sha256=recovery_sha or None,
                primary=primary,
                catalog_error=catalog_error,
                object_error=object_error,
                containment_error=containment_error,
                journal=journal,
                clock=clock,
            )
        except BaseException as exc:
            receipt_error = exc
        if receipt_error is not None:
            raise Stage2CError(
                "mandatory Stage 2C failure evidence is incomplete"
            ) from receipt_error
        if object_error is not None or catalog_error is not None or containment_error is not None:
            raise Stage2CError(
                "mandatory Stage 2C compensation or containment is incomplete"
            ) from (object_error or catalog_error or containment_error)
        if isinstance(primary, Stage2CError | KeyboardInterrupt | SystemExit):
            raise
        raise Stage2CError("Stage 2C execution failed closed") from primary


# ---- Live adapters -------------------------------------------------------


class BoundedProcess:
    """A long-running Docker exec with an unconditional watchdog and bounded stop."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self.process = process
        self.timer = threading.Timer(_SERVICE_PROCESS_TIMEOUT_SECONDS, self._expire)
        self.timer.daemon = True
        self.timer.start()

    def _expire(self) -> None:
        if self.process.poll() is None:
            self.process.kill()

    def close(self) -> None:
        self.timer.cancel()
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=_SERVICE_STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self.process.kill()
            try:
                self.process.wait(timeout=_SERVICE_STOP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired as exc:
                raise Stage2CError("spawned Docker exec did not terminate") from exc


class CommandExecutor:
    """Bounded subprocess adapter; private values are accepted only through stdin."""

    def run(
        self, command: Sequence[str], *, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        return _bounded_run(
            command,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )

    def spawn(self, command: Sequence[str], *, stdin: str) -> BoundedProcess:
        process = subprocess.Popen(
            list(command),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if process.stdin is None:
            process.kill()
            raise Stage2CError("private Docker child did not accept stdin")
        process.stdin.write(stdin)
        process.stdin.close()
        return BoundedProcess(process)


class LocalJointStack:
    """Isolated PostgreSQL/Polaris and local POSIX pgBackRest resources."""

    def __init__(
        self,
        *,
        scope: JointScope,
        resources: Mapping[str, str],
        images: Mapping[str, ir.ImagePin],
        campaign_sha256: str,
        credentials: ir.RunCredentials,
        aws_credentials: ir.AwsCredentials,
        region: str,
        executor: CommandExecutor | None = None,
    ) -> None:
        self.scope = scope
        self.resources = dict(resources)
        if self.resources != _resources(scope):
            raise Stage2CError("isolated Docker resources differ from campaign scope")
        self.images = dict(images)
        if set(self.images) != set(_IMAGE_REFERENCES):
            raise Stage2CError("isolated Docker image pins are incomplete")
        if _SHA256.fullmatch(campaign_sha256) is None:
            raise Stage2CError("isolated Docker campaign binding is invalid")
        self.campaign_sha256 = campaign_sha256
        self.credentials = credentials
        self.aws_credentials = aws_credentials
        self.region = region
        self.executor = executor or CommandExecutor()
        self._children: list[BoundedProcess] = []
        self._source_url: str | None = None
        self._restored_url: str | None = None

    @staticmethod
    def _config() -> str:
        return (
            "[global]\n"
            "repo1-type=posix\n"
            "repo1-path=/repo\n"
            "repo1-retention-full=2\n"
            "archive-async=n\n"
            "start-fast=y\n"
            "process-max=2\n\n"
            "[polaris]\n"
            "pg1-path=/var/lib/postgresql/data\n"
            "pg1-port=5432\n"
            "pg1-user=polaris\n"
        )

    def _checked(self, command: Sequence[str], *, stdin: str | None = None) -> str:
        completed = self.executor.run(command, stdin=stdin)
        if (
            completed.returncode != 0
            or len(completed.stdout) > _MAX_PRIVATE_BYTES
            or len(completed.stderr) > _MAX_PRIVATE_BYTES
        ):
            raise Stage2CError("isolated Docker operation failed")
        return completed.stdout.strip()

    def _label_map(self) -> dict[str, str]:
        return {
            "com.databox.owner": "catalog-warehouse-recovery",
            "com.databox.run": self.scope.run_id,
            "com.databox.stage": "stage2c",
            "com.databox.campaign": self.campaign_sha256,
        }

    def _labels(self) -> tuple[str, ...]:
        result: list[str] = []
        for name, value in sorted(self._label_map().items()):
            result.extend(("--label", f"{name}={value}"))
        return tuple(result)

    def _listed_names(self, resource: str, name: str) -> tuple[str, ...]:
        command = ["docker", resource, "ls"]
        if resource == "container":
            command.append("--all")
        field = "{{.Names}}" if resource == "container" else "{{.Name}}"
        command.extend(("--filter", f"name=^{name}$", "--format", field))
        completed = self.executor.run(command)
        if completed.returncode != 0:
            raise Stage2CError("Docker resource inventory failed")
        return tuple(line for line in completed.stdout.splitlines() if line)

    def _inspect(self, resource: str, name: str) -> dict[str, object]:
        output = self._checked(("docker", resource, "inspect", name))
        try:
            value = json.loads(output)
        except json.JSONDecodeError as exc:
            raise Stage2CError("Docker ownership inspection returned invalid JSON") from exc
        if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
            raise Stage2CError("Docker ownership inspection returned an unexpected shape")
        return value[0]

    def _volume_consumers(self, volume: str) -> dict[str, str]:
        completed = self.executor.run(
            (
                "docker",
                "container",
                "ls",
                "--all",
                "--filter",
                f"volume={volume}",
                "--format",
                "{{.ID}}\t{{.Names}}",
            )
        )
        if completed.returncode != 0:
            raise Stage2CError("Docker volume consumer inventory failed")
        consumers: dict[str, str] = {}
        for line in completed.stdout.splitlines():
            if not line:
                continue
            fields = line.split("\t")
            if (
                len(fields) != 2
                or re.fullmatch(r"[0-9a-f]{12,64}", fields[0]) is None
                or not fields[1]
                or fields[1] in consumers
            ):
                raise Stage2CError("Docker volume consumer inventory is ambiguous")
            consumers[fields[1]] = fields[0]
        return consumers

    def _container_spec(
        self, name: str
    ) -> tuple[ir.ImagePin, tuple[tuple[str, str], ...], str, bool]:
        resources = self.resources
        specs = {
            resources["sourcePostgres"]: (
                self.images["postgres"],
                (
                    (resources["sourceVolume"], "/var/lib/postgresql/data"),
                    (resources["repositoryVolume"], "/repo"),
                ),
                "postgres",
                False,
            ),
            resources["restoredPostgres"]: (
                self.images["postgres"],
                (
                    (resources["restoredVolume"], "/var/lib/postgresql/data"),
                    (resources["repositoryVolume"], "/repo"),
                ),
                "postgres",
                False,
            ),
            f"{resources['restoredPostgres']}-restore": (
                self.images["postgres"],
                (
                    (resources["restoredVolume"], "/var/lib/postgresql/data"),
                    (resources["repositoryVolume"], "/repo"),
                ),
                "",
                False,
            ),
            resources["sourcePolaris"]: (
                self.images["polaris"],
                (),
                resources["sourcePolaris"],
                True,
            ),
            resources["restoredPolaris"]: (
                self.images["polaris"],
                (),
                resources["restoredPolaris"],
                True,
            ),
            resources["bootstrap"]: (
                self.images["polarisAdmin"],
                (),
                "bootstrap",
                False,
            ),
        }
        try:
            return specs[name]
        except KeyError as exc:
            raise Stage2CError("Docker container name is outside the campaign") from exc

    def _validate_container(
        self,
        name: str,
        container: Mapping[str, object],
        *,
        network_id: str,
        attachment_id: str | None,
    ) -> str:
        pin, expected_mounts, alias, published = self._container_spec(name)
        config = container.get("Config")
        host = container.get("HostConfig")
        network_settings = container.get("NetworkSettings")
        networks = network_settings.get("Networks") if isinstance(network_settings, dict) else None
        runtime_ports = (
            network_settings.get("Ports") if isinstance(network_settings, dict) else None
        )
        container_id = container.get("Id")
        labels = config.get("Labels") if isinstance(config, dict) else None
        if (
            not isinstance(labels, dict)
            or {
                key: value
                for key, value in labels.items()
                if isinstance(key, str) and key.startswith("com.databox.")
            }
            != self._label_map()
        ):
            raise Stage2CError("Docker container ownership labels differ from campaign")
        restorer = name.endswith("-restore")
        expected_networks = set() if restorer else {self.resources["network"]}
        if (
            not isinstance(container_id, str)
            or not container_id
            or container.get("Name") != f"/{name}"
            or container.get("Image") != pin.image_id
            or container.get("Path") != "/bin/sh"
            or container.get("Args") != ["-ceu", "while :; do sleep 3600; done"]
            or not isinstance(config, dict)
            or config.get("Image") != pin.image_id
            or config.get("Entrypoint") != ["/bin/sh"]
            or config.get("Cmd") != ["-ceu", "while :; do sleep 3600; done"]
            or config.get("Env") != list(pin.environment)
            or (config.get("User") or "") != pin.user
            or (config.get("WorkingDir") or "") != pin.working_directory
            or not isinstance(host, dict)
            or host.get("Privileged") is not False
            or host.get("AutoRemove") is not False
            or host.get("ReadonlyRootfs") is not False
            or host.get("RestartPolicy") != {"Name": "no", "MaximumRetryCount": 0}
            or host.get("Binds") not in (None, [])
            or not isinstance(networks, dict)
            or set(networks) != expected_networks
        ):
            raise Stage2CError("Docker container identity differs from campaign")
        if restorer:
            if host.get("NetworkMode") != "none" or attachment_id is not None:
                raise Stage2CError("restore helper has an unexpected network attachment")
        else:
            details = networks.get(self.resources["network"])
            aliases = details.get("Aliases") if isinstance(details, dict) else None
            allowed_aliases = {alias, name, container_id, container_id[:12]}
            if (
                host.get("NetworkMode") != self.resources["network"]
                or not isinstance(details, dict)
                or details.get("NetworkID") != network_id
                or attachment_id != container_id
                or not isinstance(aliases, list)
                or alias not in aliases
                or any(item not in allowed_aliases for item in aliases)
            ):
                raise Stage2CError("Docker container network identity differs from campaign")
        mounts = container.get("Mounts")
        if not isinstance(mounts, list):
            raise Stage2CError("Docker container mounts are invalid")
        actual_mounts: set[tuple[str, str]] = set()
        for mount in mounts:
            if (
                not isinstance(mount, dict)
                or mount.get("Type") != "volume"
                or not isinstance(mount.get("Name"), str)
                or not isinstance(mount.get("Destination"), str)
                or mount.get("RW") is not True
            ):
                raise Stage2CError("Docker container mount ownership is invalid")
            actual_mounts.add((mount["Name"], mount["Destination"]))
        if actual_mounts != set(expected_mounts):
            raise Stage2CError("Docker container mounts differ from campaign")
        bindings = host.get("PortBindings")
        if published:
            if not isinstance(bindings, dict) or set(bindings) != {"8181/tcp"}:
                raise Stage2CError("Docker API port binding differs from campaign")
            configured = bindings["8181/tcp"]
            if (
                not isinstance(configured, list)
                or len(configured) != 1
                or not isinstance(configured[0], dict)
                or configured[0].get("HostIp") != "127.0.0.1"
                or not isinstance(configured[0].get("HostPort"), str)
                or (
                    configured[0]["HostPort"]
                    and (
                        not configured[0]["HostPort"].isdigit()
                        or not 1024 <= int(configured[0]["HostPort"]) <= 65535
                    )
                )
            ):
                raise Stage2CError("Docker configured API port is not loopback-only")
            if (
                not isinstance(runtime_ports, dict)
                or "8181/tcp" not in runtime_ports
                or any(
                    value is not None for port, value in runtime_ports.items() if port != "8181/tcp"
                )
            ):
                raise Stage2CError("Docker runtime API port differs from campaign")
            active = runtime_ports["8181/tcp"]
            if (
                not isinstance(active, list)
                or len(active) != 1
                or not isinstance(active[0], dict)
                or active[0].get("HostIp") != "127.0.0.1"
                or not isinstance(active[0].get("HostPort"), str)
                or not active[0]["HostPort"].isdigit()
                or not 1024 <= int(active[0]["HostPort"]) <= 65535
            ):
                raise Stage2CError("Docker runtime API port is not loopback-only")
        elif bindings not in (None, {}) or (
            runtime_ports is not None
            and (
                not isinstance(runtime_ports, dict)
                or any(value is not None for value in runtime_ports.values())
            )
        ):
            raise Stage2CError("Docker container has unexpected port bindings")
        return container_id

    def _owned_inventory(
        self, *, require_retained: bool
    ) -> dict[str, tuple[str, dict[str, object]]]:
        expected_labels = self._label_map()
        retained: dict[str, dict[str, object]] = {}
        for resource, key in (
            ("network", "network"),
            ("volume", "sourceVolume"),
            ("volume", "restoredVolume"),
            ("volume", "repositoryVolume"),
        ):
            name = self.resources[key]
            names = self._listed_names(resource, name)
            if names not in ((), (name,)):
                raise Stage2CError("Docker resource inventory is ambiguous")
            if not names:
                if require_retained:
                    raise Stage2CError("required retained Docker resource is absent")
                continue
            item = self._inspect(resource, name)
            if item.get("Name") != name or item.get("Labels") != expected_labels:
                raise Stage2CError("retained Docker resource ownership differs from campaign")
            if resource == "network" and (
                item.get("Driver") != "bridge"
                or item.get("Scope") != "local"
                or item.get("Internal") is not False
                or item.get("Attachable") is not False
                or item.get("Ingress") is not False
                or not isinstance(item.get("Containers"), dict)
            ):
                raise Stage2CError("retained Docker network differs from campaign")
            if resource == "volume" and (
                item.get("Driver") != "local" or item.get("Scope") != "local"
            ):
                raise Stage2CError("retained Docker volume differs from campaign")
            retained[key] = item
        names = (
            self.resources["sourcePostgres"],
            self.resources["sourcePolaris"],
            self.resources["bootstrap"],
            self.resources["restoredPostgres"],
            self.resources["restoredPolaris"],
            f"{self.resources['restoredPostgres']}-restore",
        )
        present: dict[str, dict[str, object]] = {}
        for name in names:
            listed = self._listed_names("container", name)
            if listed not in ((), (name,)):
                raise Stage2CError("Docker container inventory is ambiguous")
            if listed:
                present[name] = self._inspect("container", name)
        if present and "network" not in retained:
            raise Stage2CError("owned Docker container lost its retained network")
        attachments: dict[str, str] = {}
        if "network" in retained:
            for container_id, details in retained["network"]["Containers"].items():
                name = details.get("Name") if isinstance(details, dict) else None
                if (
                    not isinstance(container_id, str)
                    or not isinstance(name, str)
                    or name in attachments
                ):
                    raise Stage2CError("Docker network attachment inventory is ambiguous")
                attachments[name] = container_id
            expected_attached = {name for name in present if not name.endswith("-restore")}
            if set(attachments) != expected_attached:
                raise Stage2CError("generated Docker network has unknown attachments")
        network_id = retained.get("network", {}).get("Id")
        if present and (not isinstance(network_id, str) or not network_id):
            raise Stage2CError("generated Docker network identity is invalid")
        validated: dict[str, tuple[str, dict[str, object]]] = {}
        for name, container in present.items():
            container_id = self._validate_container(
                name,
                container,
                network_id=network_id if isinstance(network_id, str) else "",
                attachment_id=attachments.get(name),
            )
            validated[name] = (container_id, container)
        expected_consumers: dict[str, set[str]] = {
            self.resources["sourceVolume"]: {self.resources["sourcePostgres"]}.intersection(
                present
            ),
            self.resources["restoredVolume"]: {
                self.resources["restoredPostgres"],
                f"{self.resources['restoredPostgres']}-restore",
            }.intersection(present),
            self.resources["repositoryVolume"]: {
                self.resources["sourcePostgres"],
                self.resources["restoredPostgres"],
                f"{self.resources['restoredPostgres']}-restore",
            }.intersection(present),
        }
        for volume, expected in expected_consumers.items():
            if volume not in {self.resources[key] for key in retained if key != "network"}:
                if expected:
                    raise Stage2CError("owned Docker volume is missing")
                continue
            consumers = self._volume_consumers(volume)
            if set(consumers) != expected:
                raise Stage2CError("generated Docker volume has unknown consumers")
            for name, short_id in consumers.items():
                if not validated[name][0].startswith(short_id):
                    raise Stage2CError("Docker volume consumer identity changed")
        return validated

    def _owned_id(self, name: str) -> str:
        owned = self._owned_inventory(require_retained=True).get(name)
        if owned is None:
            raise Stage2CError("required owned Docker container is absent")
        return owned[0]

    def _remove_owned(self, name: str) -> None:
        present = self._owned_inventory(require_retained=True)
        owned = present.get(name)
        if owned is None:
            return
        container_id = owned[0]
        self._checked(("docker", "rm", "--force", container_id))
        if self._listed_names("container", name):
            raise Stage2CError("owned Docker container remains after removal")

    def _install_config(self, container: str) -> None:
        container_id = self._owned_id(container)
        self._checked(
            (
                "docker",
                "exec",
                "--interactive",
                "--user",
                "root",
                container_id,
                "/bin/sh",
                "-ceu",
                "IFS= read -r CONFIG; "
                "printf '%b' \"$CONFIG\" >/tmp/pgbackrest.conf; "
                "chown postgres:postgres /tmp/pgbackrest.conf; "
                "chmod 600 /tmp/pgbackrest.conf",
            ),
            stdin=self._config().replace("\n", "\\n") + "\n",
        )

    def _wait_postgres(self, container: str) -> None:
        container_id = self._owned_id(container)
        deadline = time.monotonic() + _POSTGRES_READY_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            completed = self.executor.run(
                (
                    "docker",
                    "exec",
                    container_id,
                    "pg_isready",
                    "-U",
                    "polaris",
                    "-d",
                    "polaris",
                )
            )
            if completed.returncode == 0:
                return
            time.sleep(1)
        raise Stage2CError("isolated PostgreSQL did not become ready")

    def _wait_polaris(self, container: str) -> str:
        container_id = self._owned_id(container)
        deadline = time.monotonic() + _POLARIS_READY_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            completed = self.executor.run(
                (
                    "docker",
                    "exec",
                    container_id,
                    "curl",
                    "--fail",
                    "--silent",
                    "http://localhost:8182/q/health/ready",
                )
            )
            if completed.returncode == 0:
                break
            time.sleep(1)
        else:
            raise Stage2CError("isolated Polaris did not become ready")
        output = self._checked(("docker", "port", container_id, "8181/tcp"))
        match = re.fullmatch(r"127\.0\.0\.1:([0-9]{1,5})", output)
        if match is None:
            raise Stage2CError("isolated Polaris port is not loopback-only")
        return f"http://127.0.0.1:{match.group(1)}"

    def assert_absent(self) -> None:
        for resource, name in (
            ("network", self.resources["network"]),
            ("volume", self.resources["sourceVolume"]),
            ("volume", self.resources["restoredVolume"]),
            ("volume", self.resources["repositoryVolume"]),
            ("container", self.resources["sourcePostgres"]),
            ("container", self.resources["sourcePolaris"]),
            ("container", self.resources["bootstrap"]),
            ("container", self.resources["restoredPostgres"]),
            ("container", self.resources["restoredPolaris"]),
            ("container", f"{self.resources['restoredPostgres']}-restore"),
        ):
            if self._listed_names(resource, name):
                raise Stage2CError("generated Docker resource already exists")

    def create(self) -> None:
        self._checked(
            (
                "docker",
                "network",
                "create",
                "--driver",
                "bridge",
                *self._labels(),
                self.resources["network"],
            )
        )
        for name in ("sourceVolume", "restoredVolume", "repositoryVolume"):
            self._checked(
                (
                    "docker",
                    "volume",
                    "create",
                    *self._labels(),
                    self.resources[name],
                )
            )
        self._owned_inventory(require_retained=True)
        source = self.resources["sourcePostgres"]
        self._checked(
            (
                "docker",
                "run",
                "--detach",
                "--name",
                source,
                "--network",
                self.resources["network"],
                "--network-alias",
                "postgres",
                *self._labels(),
                "--mount",
                f"type=volume,src={self.resources['sourceVolume']},dst=/var/lib/postgresql/data",
                "--mount",
                f"type=volume,src={self.resources['repositoryVolume']},dst=/repo",
                "--entrypoint",
                "/bin/sh",
                self.images["postgres"].image_id,
                "-ceu",
                "while :; do sleep 3600; done",
            )
        )
        self._owned_inventory(require_retained=True)
        source_id = self._owned_id(source)
        self._checked(
            (
                "docker",
                "exec",
                "--user",
                "root",
                source_id,
                "chown",
                "-R",
                "postgres:postgres",
                "/repo",
            )
        )
        self._install_config(source)
        process = self.executor.spawn(
            (
                "docker",
                "exec",
                "--interactive",
                source_id,
                "/bin/sh",
                "-ceu",
                "IFS= read -r DB_PASSWORD; "
                'export POSTGRES_PASSWORD="$DB_PASSWORD" '
                "POSTGRES_DB=polaris POSTGRES_USER=polaris; "
                "exec docker-entrypoint.sh postgres -c archive_mode=off "
                "-c listen_addresses='*'",
            ),
            stdin=self.credentials.postgres_password + "\n",
        )
        self._children.append(process)
        self._wait_postgres(source)
        bootstrap = self.resources["bootstrap"]
        self._checked(
            (
                "docker",
                "run",
                "--detach",
                "--name",
                bootstrap,
                "--network",
                self.resources["network"],
                "--network-alias",
                "bootstrap",
                *self._labels(),
                "--entrypoint",
                "/bin/sh",
                self.images["polarisAdmin"].image_id,
                "-ceu",
                "while :; do sleep 3600; done",
            )
        )
        self._owned_inventory(require_retained=True)
        self._checked(
            (
                "docker",
                "exec",
                "--interactive",
                self._owned_id(bootstrap),
                "/bin/sh",
                "-ceu",
                "IFS= read -r DB_PASSWORD; IFS= read -r CLIENT_ID; "
                "IFS= read -r CLIENT_SECRET; exec env "
                "polaris.persistence.type=relational-jdbc "
                "quarkus.datasource.username=polaris "
                'quarkus.datasource.password="$DB_PASSWORD" '
                "quarkus.datasource.jdbc.url=jdbc:postgresql://postgres:5432/polaris "
                "/opt/jboss/container/java/run/run-java.sh bootstrap -r POLARIS "
                '-c "POLARIS,${CLIENT_ID},${CLIENT_SECRET}"',
            ),
            stdin=f"{self.credentials.postgres_password}\n{self.credentials.polaris_client_id}\n{self.credentials.polaris_client_secret}\n",
        )
        self._remove_owned(bootstrap)
        self._source_url = self._start_polaris(self.resources["sourcePolaris"])

    def _start_polaris(self, name: str) -> str:
        self._checked(
            (
                "docker",
                "run",
                "--detach",
                "--name",
                name,
                "--network",
                self.resources["network"],
                "--network-alias",
                name,
                "--publish",
                "127.0.0.1::8181",
                *self._labels(),
                "--entrypoint",
                "/bin/sh",
                self.images["polaris"].image_id,
                "-ceu",
                "while :; do sleep 3600; done",
            )
        )
        self._owned_inventory(require_retained=True)
        script = (
            "IFS= read -r DB_PASSWORD; IFS= read -r ACCESS_KEY; "
            "IFS= read -r SECRET_KEY; IFS= read -r SESSION_TOKEN; "
            "IFS= read -r REGION; export "
            "POLARIS_PERSISTENCE_TYPE=relational-jdbc "
            "QUARKUS_DATASOURCE_USERNAME=polaris "
            'QUARKUS_DATASOURCE_PASSWORD="$DB_PASSWORD" '
            "QUARKUS_DATASOURCE_JDBC_URL=jdbc:postgresql://postgres:5432/polaris "
            "POLARIS_REALM_CONTEXT_REALMS=POLARIS "
            "POLARIS_REALM_CONTEXT_REQUIRE_HEADER=false "
            'AWS_ACCESS_KEY_ID="$ACCESS_KEY" '
            'AWS_SECRET_ACCESS_KEY="$SECRET_KEY" '
            'AWS_SESSION_TOKEN="$SESSION_TOKEN" '
            'AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"; '
            "exec /opt/jboss/container/java/run/run-java.sh"
        )
        process = self.executor.spawn(
            (
                "docker",
                "exec",
                "--interactive",
                self._owned_id(name),
                "/bin/sh",
                "-ceu",
                script,
            ),
            stdin=f"{self.credentials.postgres_password}\n{self.aws_credentials.access_key_id}\n{self.aws_credentials.secret_access_key}\n{self.aws_credentials.session_token}\n{self.region}\n",
        )
        self._children.append(process)
        return self._wait_polaris(name)

    @property
    def source_url(self) -> str:
        if self._source_url is None:
            raise Stage2CError("source Polaris is not started")
        return self._source_url

    @property
    def restored_url(self) -> str:
        if self._restored_url is None:
            self._restored_url = self.start_restored_polaris()
        return self._restored_url

    def start_restored_polaris(self) -> str:
        """Start Polaris only after catalog and object restoration have completed."""
        name = self.resources["restoredPolaris"]
        present = self._owned_inventory(require_retained=True)
        if name in present:
            return self._wait_polaris(name)
        return self._start_polaris(name)

    def backup_point_a(self) -> RecoveryTarget:
        pg = self._owned_id(self.resources["sourcePostgres"])
        self._checked(
            (
                "docker",
                "exec",
                pg,
                "psql",
                "-U",
                "polaris",
                "-d",
                "polaris",
                "-v",
                "ON_ERROR_STOP=1",
                "-qAtX",
                "-c",
                "CREATE TABLE public.stage2c_catalog_state "
                "(phase text PRIMARY KEY, value bigint NOT NULL); "
                "INSERT INTO public.stage2c_catalog_state VALUES ('A', 101);",
            )
        )
        self._checked(
            (
                "docker",
                "exec",
                "--user",
                "postgres",
                pg,
                "pgbackrest",
                "--config=/tmp/pgbackrest.conf",
                "--stanza=polaris",
                "stanza-create",
            )
        )
        self._checked(
            (
                "docker",
                "exec",
                "--user",
                "postgres",
                pg,
                "pg_ctl",
                "-D",
                "/var/lib/postgresql/data",
                "-m",
                "fast",
                "-w",
                "stop",
            )
        )
        process = self.executor.spawn(
            (
                "docker",
                "exec",
                "--interactive",
                pg,
                "/bin/sh",
                "-ceu",
                "exec docker-entrypoint.sh postgres -c archive_mode=on "
                "-c archive_command='pgbackrest --config=/tmp/pgbackrest.conf "
                "--stanza=polaris archive-push %p' -c listen_addresses='*'",
            ),
            stdin="",
        )
        self._children.append(process)
        self._wait_postgres(self.resources["sourcePostgres"])
        self._checked(
            (
                "docker",
                "exec",
                "--user",
                "postgres",
                pg,
                "pgbackrest",
                "--config=/tmp/pgbackrest.conf",
                "--stanza=polaris",
                "check",
            )
        )
        self._checked(
            (
                "docker",
                "exec",
                "--user",
                "postgres",
                pg,
                "pgbackrest",
                "--config=/tmp/pgbackrest.conf",
                "--stanza=polaris",
                "--type=full",
                "backup",
            )
        )
        target = f"stage2c_target_{self.scope.run_id}"
        self._checked(
            (
                "docker",
                "exec",
                pg,
                "psql",
                "-U",
                "polaris",
                "-d",
                "polaris",
                "-v",
                "ON_ERROR_STOP=1",
                "-qAtX",
                "-c",
                f"SELECT pg_create_restore_point('{target}'); SELECT pg_switch_wal();",
            )
        )
        self._checked(
            (
                "docker",
                "exec",
                "--user",
                "postgres",
                pg,
                "pgbackrest",
                "--config=/tmp/pgbackrest.conf",
                "--stanza=polaris",
                "check",
            )
        )
        return RecoveryTarget(target)

    def archive_point_b(self) -> None:
        pg = self._owned_id(self.resources["sourcePostgres"])
        self._checked(
            (
                "docker",
                "exec",
                pg,
                "psql",
                "-U",
                "polaris",
                "-d",
                "polaris",
                "-v",
                "ON_ERROR_STOP=1",
                "-qAtX",
                "-c",
                "INSERT INTO public.stage2c_catalog_state VALUES ('B', 202); "
                "SELECT pg_switch_wal();",
            )
        )
        self._checked(
            (
                "docker",
                "exec",
                "--user",
                "postgres",
                pg,
                "pgbackrest",
                "--config=/tmp/pgbackrest.conf",
                "--stanza=polaris",
                "check",
            )
        )

    def stop_source(self) -> None:
        present = self._owned_inventory(require_retained=True)
        for name in (self.resources["sourcePolaris"], self.resources["sourcePostgres"]):
            owned = present.get(name)
            if owned is None:
                continue
            if name == self.resources["sourcePostgres"]:
                self.executor.run(
                    (
                        "docker",
                        "exec",
                        "--user",
                        "postgres",
                        owned[0],
                        "pg_ctl",
                        "-D",
                        "/var/lib/postgresql/data",
                        "-m",
                        "fast",
                        "-w",
                        "stop",
                    )
                )
            self._remove_owned(name)
            present = self._owned_inventory(require_retained=True)

    def restore_catalog(self, target: RecoveryTarget) -> None:
        self.stop_source()
        restored = self.resources["restoredPostgres"]
        present = self._owned_inventory(require_retained=True)
        if restored in present:
            ready = self.executor.run(
                (
                    "docker",
                    "exec",
                    present[restored][0],
                    "pg_isready",
                    "-U",
                    "polaris",
                    "-d",
                    "polaris",
                )
            )
            if ready.returncode != 0:
                self._remove_owned(restored)
                present = self._owned_inventory(require_retained=True)
        if restored not in present:
            restorer = f"{restored}-restore"
            if restorer in present:
                self._remove_owned(restorer)
            self._checked(
                (
                    "docker",
                    "run",
                    "--detach",
                    "--name",
                    restorer,
                    *self._labels(),
                    "--network",
                    "none",
                    "--mount",
                    f"type=volume,src={self.resources['restoredVolume']},dst=/var/lib/postgresql/data",
                    "--mount",
                    f"type=volume,src={self.resources['repositoryVolume']},dst=/repo",
                    "--entrypoint",
                    "/bin/sh",
                    self.images["postgres"].image_id,
                    "-ceu",
                    "while :; do sleep 3600; done",
                )
            )
            self._owned_inventory(require_retained=True)
            restorer_id = self._owned_id(restorer)
            self._checked(
                (
                    "docker",
                    "exec",
                    "--user",
                    "root",
                    restorer_id,
                    "chown",
                    "-R",
                    "postgres:postgres",
                    "/var/lib/postgresql/data",
                )
            )
            self._install_config(restorer)
            self._checked(
                (
                    "docker",
                    "exec",
                    "--user",
                    "postgres",
                    restorer_id,
                    "pgbackrest",
                    "--config=/tmp/pgbackrest.conf",
                    "--stanza=polaris",
                    "--type=name",
                    f"--target={target.name}",
                    "--target-action=promote",
                    "--delta",
                    "restore",
                )
            )
            self._remove_owned(restorer)
            self._checked(
                (
                    "docker",
                    "run",
                    "--detach",
                    "--name",
                    restored,
                    "--network",
                    self.resources["network"],
                    "--network-alias",
                    "postgres",
                    *self._labels(),
                    "--mount",
                    f"type=volume,src={self.resources['restoredVolume']},dst=/var/lib/postgresql/data",
                    "--mount",
                    f"type=volume,src={self.resources['repositoryVolume']},dst=/repo",
                    "--entrypoint",
                    "/bin/sh",
                    self.images["postgres"].image_id,
                    "-ceu",
                    "while :; do sleep 3600; done",
                )
            )
            self._owned_inventory(require_retained=True)
            self._install_config(restored)
            process = self.executor.spawn(
                (
                    "docker",
                    "exec",
                    "--interactive",
                    self._owned_id(restored),
                    "/bin/sh",
                    "-ceu",
                    "exec docker-entrypoint.sh postgres -c archive_mode=off "
                    "-c listen_addresses='*'",
                ),
                stdin="",
            )
            self._children.append(process)
        self._wait_postgres(restored)
        restored_id = self._owned_id(restored)
        rows = self._checked(
            (
                "docker",
                "exec",
                restored_id,
                "psql",
                "-U",
                "polaris",
                "-d",
                "polaris",
                "-qAtX",
                "-F",
                "|",
                "-c",
                "SELECT phase,value FROM public.stage2c_catalog_state ORDER BY phase;",
            )
        )
        promoted = self._checked(
            (
                "docker",
                "exec",
                restored_id,
                "psql",
                "-U",
                "polaris",
                "-d",
                "polaris",
                "-qAtX",
                "-c",
                "SELECT pg_is_in_recovery();",
            )
        )
        if rows != "A|101" or promoted != "f":
            raise Stage2CError("restored catalog does not bracket point A and B")

    def contain(self) -> None:
        child_error: BaseException | None = None
        for child in self._children:
            try:
                child.close()
            except BaseException as exc:
                child_error = child_error or exc
        self._children.clear()
        present = self._owned_inventory(require_retained=False)
        for name in (
            self.resources["bootstrap"],
            self.resources["sourcePolaris"],
            self.resources["sourcePostgres"],
            self.resources["restoredPolaris"],
            self.resources["restoredPostgres"],
            f"{self.resources['restoredPostgres']}-restore",
        ):
            if name in present:
                self._remove_owned(name)
                present = self._owned_inventory(require_retained=False)
        if present:
            raise Stage2CError("Stage 2C credential-bearing containers remain")
        self._owned_inventory(require_retained=False)
        if child_error is not None:
            raise Stage2CError("spawned Docker exec containment failed") from child_error


class LiveJointRecoveryOperations:
    """Real two-table Polaris/S3 operations over one isolated local catalog stack."""

    def __init__(
        self,
        *,
        settings: ir.RecoverySettings,
        scope: JointScope,
        run_dir: Path,
        aws: ir.VerifiedAwsContext,
        stack: LocalJointStack,
        credentials: ir.RunCredentials,
    ) -> None:
        self.settings = settings
        self.scope = scope
        self.run_dir = run_dir
        self.aws = aws
        self.stack = stack
        self.credentials = credentials
        self.store: ir.AwsCliVersionStore = aws.store
        self._source_gateway: ir.PolarisGateway | None = None
        self._restored_gateway: ir.PolarisGateway | None = None
        self._point_b_tables: dict[str, Any] = {}
        self._point_b_ios: dict[str, Any] = {}

    def _drill_scope(self, table: str) -> ir.DrillScope:
        return ir.DrillScope(
            self.scope.run_id, self.scope.prefix, self.scope.catalog, self.scope.namespace, table
        )

    def _key(self, location: str) -> str:
        parsed = urlparse(location)
        key = parsed.path.lstrip("/")
        if (
            parsed.scheme != "s3"
            or parsed.netloc != self.settings.bucket
            or parsed.query
            or parsed.fragment
            or not key.startswith(self.scope.prefix + "/")
        ):
            raise Stage2CError("Iceberg location escaped the Stage 2C prefix")
        return key

    def _gateway(self, *, restored: bool = False) -> ir.PolarisGateway:
        current = self._restored_gateway if restored else self._source_gateway
        if current is not None:
            return current
        url = self.stack.restored_url if restored else self.stack.source_url
        gateway = ir.PolarisGateway(
            config=ir.RuntimeConfig.isolated(
                settings=self.settings,
                polaris_url=url,
                credentials=self.credentials,
            )
        )
        if restored:
            self._restored_gateway = gateway
        else:
            self._source_gateway = gateway
        return gateway

    def _fence(self, table: Any) -> Any:
        self._key(table.metadata_location)
        properties = getattr(table.io, "properties", {})
        if any(
            not isinstance(properties.get(name), str) or not properties[name]
            for name in ir._VENDED_S3_CREDENTIAL_PROPERTIES
        ):
            raise Stage2CError("catalog-loaded FileIO lacks vended credentials")
        table.io = ir._PrefixFencedFileIO(table.io, self._key)
        return table

    def _rows(self, table: Any) -> tuple[Mapping[str, object], ...]:
        raw = table.scan().to_arrow().to_pylist()
        if (
            not isinstance(raw, list)
            or len(raw) > 8
            or not all(isinstance(row, dict) for row in raw)
        ):
            raise Stage2CError("Iceberg query returned an invalid bounded result")
        return tuple(sorted((dict(row) for row in raw), key=lambda row: int(row["event_id"])))

    def _capture(
        self, table: Any, expected_rows: Sequence[Mapping[str, object]], snapshots: int
    ) -> TablePoint:
        graph = ir.capture_iceberg_graph(
            table, location_validator=self._key, expected_snapshot_count=snapshots
        )
        nodes: list[ir.GraphNode] = []
        total = 0
        for item in graph:
            key = self._key(item.location)
            timeline = self.store.list_versions(key)
            if len(timeline) > _MAX_VERSIONS:
                raise Stage2CError("Iceberg object exceeds version-count limit")
            latest = [entry for entry in timeline if entry.latest]
            if (
                len(latest) != 1
                or latest[0].delete_marker
                or latest[0].etag is None
                or latest[0].size is None
                or latest[0].version_id == "null"
            ):
                raise Stage2CError("Iceberg object has no unambiguous current version")
            state = self.store._version_state(latest[0])
            if not state.exists or state.sha256 is None or state.size != latest[0].size:
                raise Stage2CError("Iceberg object exact version could not be captured")
            total += state.size
            if total > _MAX_BYTES:
                raise Stage2CError("table graph exceeds byte limit")
            nodes.append(
                ir.GraphNode(
                    key,
                    item.kind,
                    latest[0].version_id,
                    latest[0].etag,
                    state.size,
                    state.sha256,
                    item.depth,
                )
            )
        rows = self._rows(table)
        if rows != tuple(dict(row) for row in expected_rows):
            raise Stage2CError("Iceberg table rows differ from deterministic contract")
        snapshot = table.current_snapshot()
        if snapshot is None:
            raise Stage2CError("Iceberg table has no current snapshot")
        capture = ir.TableCapture(
            bucket=self.settings.bucket,
            table_uuid=str(table.metadata.table_uuid),
            metadata_location=table.metadata_location,
            snapshot_id=snapshot.snapshot_id,
            schema_sha256=ir._schema_digest(table),
            row_count=len(rows),
            rows_sha256=_rows_digest(rows),
            nodes=tuple(nodes),
        )
        return TablePoint(table.name()[1], capture, _logical_graph_sha256(nodes))

    def preflight(self, scope: JointScope) -> ir.GraphNode:
        if scope != self.scope:
            raise Stage2CError("live Stage 2C scope mismatch")
        self.stack.assert_absent()
        self.store.verify_empty_prefix()
        key = f"{scope.prefix}/capability-canary.bin"
        canary = self.store.put_canary(key, b"canary\n")
        deleted = self.store.delete_current(canary)
        if not deleted.delete_marker:
            raise Stage2CError("capability canary ordinary delete failed")
        restored = self.store.restore(canary)
        if not _matches(canary, restored) or restored.version_id == canary.source_version_id:
            raise Stage2CError("capability canary exact-version promotion failed")
        self.stack.create()
        return canary

    def create_point_a(self, scope: JointScope) -> tuple[TablePoint, TablePoint]:
        gateway = self._gateway()
        catalog = gateway.provision(self._drill_scope(scope.tables[0]))
        namespace_location = f"s3://{self.settings.bucket}/{scope.prefix}/{scope.namespace}"
        catalog.create_namespace(scope.namespace, {"location": namespace_location})
        from pyarrow import Table as ArrowTable
        from pyiceberg.schema import Schema
        from pyiceberg.types import LongType, NestedField, StringType

        schema = Schema(
            NestedField(1, "event_id", LongType(), required=True),
            NestedField(2, "generation", StringType(), required=True),
            NestedField(3, "value", LongType(), required=True),
        )
        result: list[TablePoint] = []
        for table_name, rows in zip(scope.tables, POINT_A_ROWS, strict=True):
            table = catalog.create_table(
                (scope.namespace, table_name),
                schema=schema,
                location=f"{namespace_location}/{table_name}",
                properties={"format-version": "2"},
            )
            table = self._fence(table)
            table.append(
                ArrowTable.from_pylist([dict(row) for row in rows], schema=schema.as_arrow())
            )
            fresh = self._fence(catalog.load_table((scope.namespace, table_name)))
            result.append(self._capture(fresh, rows, 1))
        return result[0], result[1]

    def backup_point_a(self) -> RecoveryTarget:
        return self.stack.backup_point_a()

    def append_point_b(self, point_a: Sequence[TablePoint]) -> tuple[PointBState, PointBState]:
        del point_a
        from pyarrow import Table as ArrowTable

        catalog = self._gateway().open(self._drill_scope(self.scope.tables[0]))
        result: list[PointBState] = []
        for index, table_name in enumerate(self.scope.tables):
            table = self._fence(catalog.load_table((self.scope.namespace, table_name)))
            table.append(
                ArrowTable.from_pylist(
                    [dict(POINT_B_ROWS[index])], schema=table.schema().as_arrow()
                )
            )
            table = self._fence(catalog.load_table((self.scope.namespace, table_name)))
            rows = POINT_A_ROWS[index] + (POINT_B_ROWS[index],)
            point = self._capture(table, rows, 2)
            self._point_b_tables[table_name] = table
            self._point_b_ios[table_name] = table.io
            result.append(
                PointBState(
                    table_name,
                    point.capture.metadata_location,
                    point.capture.snapshot_id,
                    point.capture.rows_sha256,
                    point.capture.nodes,
                )
            )
        self.stack.archive_point_b()
        return result[0], result[1]

    def verify_prefix_inventory(
        self,
        canary: ir.GraphNode,
        point_a: Sequence[TablePoint],
        point_b: Sequence[PointBState],
    ) -> None:
        current_nodes = _complete_nodes(canary, point_a, point_b)
        point_a_nodes = tuple(node for point in point_a for node in point.capture.nodes)
        if self.store.prefix_keys() != frozenset(current_nodes):
            raise Stage2CError("complete Stage 2C prefix contains foreign or missing keys")
        for node in current_nodes.values():
            timeline = self.store.list_versions(node.key)
            latest = [entry for entry in timeline if entry.latest]
            if (
                len(timeline) > _MAX_VERSIONS
                or len(latest) != 1
                or latest[0].delete_marker
                or latest[0].size != node.size
                or latest[0].etag != node.etag
            ):
                raise Stage2CError("complete Stage 2C prefix has unexpected version metadata")
            if not _matches(node, self.store.current_state(node)):
                raise Stage2CError("complete Stage 2C prefix has unexpected current bytes")
        for node in (canary, *point_a_nodes):
            source = self.store.exact_source_state(node)
            if not _matches(node, source) or source.version_id != node.source_version_id:
                raise Stage2CError("point-A historical source changed or disappeared")

    def predelete_state(self, node: ir.GraphNode) -> ir.ObjectState:
        if len(self.store.list_versions(node.key)) > _MAX_VERSIONS - 2:
            raise Stage2CError("damage candidate lacks delete-and-promotion version headroom")
        return self.store.current_state(node)

    def current_state(self, node: ir.GraphNode) -> ir.ObjectState:
        return self.store.current_state(node)

    def delete_current(self, node: ir.GraphNode) -> ir.DeleteResult:
        return self.store.delete_current(node)

    @staticmethod
    def _missing_location(error: BaseException, allowed: set[str]) -> str | None:
        current: BaseException | None = error
        seen: set[int] = set()
        matches: set[str] = set()
        for _ in range(8):
            if current is None or id(current) in seen:
                break
            seen.add(id(current))
            if isinstance(current, FileNotFoundError):
                message = str(current)
                matches.update(
                    location
                    for location in allowed
                    if ir.LiveWarehouseDrillOperations._message_names_exact_location(
                        message, location
                    )
                )
            current = current.__cause__ or current.__context__
        return next(iter(matches)) if len(matches) == 1 else None

    def prove_point_b_broken(
        self, point_b: Sequence[PointBState], approved_nodes: Sequence[ir.GraphNode]
    ) -> None:
        approved_by_key = {node.key: node for node in approved_nodes}
        if len(approved_by_key) != len(approved_nodes):
            raise Stage2CError("break-proof approved nodes are ambiguous")
        assigned: set[str] = set()
        for state in point_b:
            table_keys = state.graph_keys.intersection(approved_by_key)
            if assigned.intersection(table_keys):
                raise Stage2CError("break-proof approved node crosses table boundaries")
            assigned.update(table_keys)
            table_nodes = tuple(approved_by_key[key] for key in sorted(table_keys))
            if not table_nodes:
                raise Stage2CError("break-proof table has no table-specific approved node")
            allowed = {f"s3://{self.settings.bucket}/{node.key}" for node in table_nodes}
            table = self._point_b_tables.get(state.table)
            if table is None:
                raise Stage2CError("point-B table handle is unavailable")
            try:
                table.scan().to_arrow()
            except Exception as exc:
                location = self._missing_location(exc, allowed)
                if location is None:
                    raise Stage2CError(
                        "point-B failure was not an approved missing object"
                    ) from exc
                try:
                    self._point_b_ios[state.table].new_input(location).open()
                except FileNotFoundError as direct:
                    if self._missing_location(direct, {location}) != location:
                        raise Stage2CError("direct missing-object proof was not exact") from direct
                else:
                    raise Stage2CError("point-B query and direct missing-object proof disagree")
            else:
                raise Stage2CError("point-B table remained readable after approved deletion")
        if assigned != set(approved_by_key):
            raise Stage2CError("break-proof approved node is outside both table graphs")
        for node in approved_nodes:
            current = self.store.current_state(node)
            source = self.store.exact_source_state(node)
            if (
                current.exists
                or not current.delete_marker
                or not _matches(node, source)
                or source.version_id != node.source_version_id
            ):
                raise Stage2CError("damaged object history is not safely recoverable")

    def stop_source(self) -> None:
        self.stack.stop_source()

    def restore_catalog(self, target: RecoveryTarget) -> None:
        self.stack.restore_catalog(target)

    def restore_object(self, node: ir.GraphNode) -> ir.ObjectState:
        return self.store.restore(node)

    def validate_restored(
        self, point_a: Sequence[TablePoint], point_b: Sequence[PointBState]
    ) -> tuple[TablePoint, TablePoint]:
        del point_b
        catalog = self._gateway(restored=True).open(self._drill_scope(self.scope.tables[0]))
        result: list[TablePoint] = []
        for index, expected in enumerate(point_a):
            table = self._fence(catalog.load_table((self.scope.namespace, expected.table)))
            result.append(self._capture(table, POINT_A_ROWS[index], 1))
        return result[0], result[1]

    def contain(self) -> None:
        self.stack.contain()


def _derive_credentials(settings: ir.RecoverySettings, scope: JointScope) -> ir.RunCredentials:
    def derive(label: str) -> str:
        return hmac.new(
            settings.run_secret.encode(),
            f"databox-stage2c:{scope.run_id}:{label}".encode(),
            hashlib.sha256,
        ).hexdigest()

    return ir.RunCredentials(
        postgres_password=derive("postgres-password"),  # secret-scan: allow
        polaris_client_id=f"stage2c-{scope.run_id}",
        polaris_client_secret=derive("polaris-client-secret"),  # secret-scan: allow
    )


def _verify_live_aws_bounded(
    *,
    settings: ir.RecoverySettings,
    scope: ir.DrillScope,
    temp_root: Path,
) -> ir.VerifiedAwsContext:
    profile_environment = ir._profile_environment(
        os.environ,
        profile=settings.profile,
        region=settings.region,
    )
    credentials = ir._export_aws_credentials(
        environ=profile_environment,
        runner=_bounded_run,
    )
    environment = ir._credential_environment(
        profile_environment,
        credentials=credentials,
        region=settings.region,
    )
    identity = ir._verify_non_root_identity(
        environ=environment,
        expected_sha256=settings.identity_sha256,
        region=settings.region,
        runner=_bounded_run,
    )
    root_arn = ir._require_identity_relationship(
        identity=identity,
        storage_role_arn=settings.storage_role_arn,
    )
    ir._isolate_parent_aws_environment(os.environ, region=settings.region)
    store = ir.AwsCliVersionStore(
        bucket=settings.bucket,
        prefix=scope.prefix,
        region=settings.region,
        environ=environment,
        expected_owner=identity.account,
        temp_root=temp_root,
        runner=_bounded_run,
    )
    store.verify_bucket_protection(root_arn=root_arn)
    return ir.VerifiedAwsContext(environment, identity, credentials, store)


def live_operations_factory(
    settings: ir.RecoverySettings,
) -> Callable[[dict[str, object], JointScope, Path], JointRecoveryOperations]:
    def factory(
        plan: dict[str, object], scope: JointScope, run_dir: Path
    ) -> JointRecoveryOperations:
        aws = _verify_live_aws_bounded(
            settings=settings,
            scope=ir.DrillScope(
                scope.run_id, scope.prefix, scope.catalog, scope.namespace, scope.tables[0]
            ),
            temp_root=run_dir,
        )
        credentials = _derive_credentials(settings, scope)
        stack_raw = plan.get("stack")
        resources = stack_raw.get("resources") if isinstance(stack_raw, dict) else None
        if not isinstance(resources, dict) or not isinstance(stack_raw, dict):
            raise Stage2CError("private Stage 2C stack resources are invalid")
        campaign_sha256 = hashlib.sha256((run_dir / "campaign.plan.json").read_bytes()).hexdigest()
        stack = LocalJointStack(
            scope=scope,
            resources=resources,
            images=_planned_images(stack_raw),
            campaign_sha256=campaign_sha256,
            credentials=credentials,
            aws_credentials=aws.credentials,
            region=settings.region,
        )
        return LiveJointRecoveryOperations(
            settings=settings,
            scope=scope,
            run_dir=run_dir,
            aws=aws,
            stack=stack,
            credentials=credentials,
        )

    return factory


def _require_plan_path(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    root = Path(os.path.abspath(_EVIDENCE_ROOT))
    if (
        absolute.name != "campaign.plan.json"
        or absolute.parent.parent != root
        or _RUN_ID.fullmatch(absolute.parent.name) is None
    ):
        raise Stage2CError("Stage 2C plan is outside the fixed private evidence root")
    for item in (root, absolute.parent, absolute):
        if item.exists() and item.is_symlink():
            raise Stage2CError("Stage 2C private path contains a symlink")
    return absolute


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare", help="write a mutation-free exact Stage 2C plan")
    execute = commands.add_parser("execute", help="execute or restore-only one exact plan")
    execute.add_argument("--plan", required=True, type=Path)
    execute.add_argument("--sha256", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        settings = ir.RecoverySettings.load()
        if args.command == "prepare":
            result = prepare_plan(settings=settings)
        else:
            path = _require_plan_path(args.plan)
            result = execute_campaign(
                settings=settings,
                plan_path=path,
                expected_sha256=args.sha256,
                operations_factory=live_operations_factory(settings),
            )
    except (Stage2CError, ir.DrillError, OSError, ValueError):
        print("Stage 2C refused; inspect private evidence locally", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
