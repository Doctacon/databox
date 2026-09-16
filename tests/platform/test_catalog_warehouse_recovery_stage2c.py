from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import subprocess
import sys
import threading
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).parents[2]
PLATFORM = ROOT / "scripts/platform"
SCRIPT = PLATFORM / "catalog_warehouse_recovery_stage2c.py"
if str(PLATFORM) not in sys.path:
    sys.path.insert(0, str(PLATFORM))


def _load() -> ModuleType:
    name = "catalog_warehouse_recovery_stage2c_tested"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


stage2c = _load()
ir = stage2c.ir
RUN_ID = "0123456789abcdef"
NOW = datetime(2026, 9, 16, 12, tzinfo=UTC)


def _settings() -> Any:
    return ir.RecoverySettings(
        bucket="private-test-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/stage2c-test",
        profile="operator-test",
        identity_sha256="1" * 64,
        run_secret="s" * 64,
    )


def _pin(reference: str) -> Any:
    return ir.ImagePin(
        reference=reference,
        image_id="sha256:" + "2" * 64,
        entrypoint=("/entrypoint",),
        command=("run",),
    )


def _node(table: str, suffix: str, *, depth: int, size: int = 10) -> Any:
    return ir.GraphNode(
        key=(f"integration/recovery/{RUN_ID}/stage1/warehouse/joint_{RUN_ID}/{table}/{suffix}"),
        kind="metadata" if depth == 0 else "data",
        source_version_id=f"source-{table}-{suffix}",
        etag=f'"etag-{table}-{suffix}"',
        size=size,
        sha256=hashlib.sha256(f"{table}-{suffix}".encode()).hexdigest(),
        depth=depth,
    )


def _point(table: str, index: int) -> Any:
    nodes = (
        _node(table, "metadata/00001.json", depth=0),
        _node(table, "data/data.parquet", depth=3),
    )
    capture = ir.TableCapture(
        bucket="private-test-bucket",
        table_uuid=f"uuid-{table}",
        metadata_location=f"s3://private-test-bucket/{nodes[0].key}",
        snapshot_id=100 + index,
        schema_sha256=hashlib.sha256(f"schema-{table}".encode()).hexdigest(),
        row_count=3,
        rows_sha256=stage2c._rows_digest(stage2c.POINT_A_ROWS[index]),
        nodes=nodes,
    )
    return stage2c.TablePoint(table, capture, stage2c._logical_graph_sha256(nodes))


def _point_b(point: Any, index: int) -> Any:
    b_key = (
        f"integration/recovery/{RUN_ID}/stage1/warehouse/joint_{RUN_ID}/"
        f"{point.table}/metadata/point-b-{index}.metadata.json"
    )
    rows = stage2c.POINT_A_ROWS[index] + (stage2c.POINT_B_ROWS[index],)
    b_node = ir.GraphNode(
        b_key,
        "metadata",
        f"b-{index}",
        f'"b-{index}"',
        10,
        hashlib.sha256(f"b-{index}".encode()).hexdigest(),
        0,
    )
    return stage2c.PointBState(
        point.table,
        f"s3://private-test-bucket/{b_key}",
        point.capture.snapshot_id + 1,
        stage2c._rows_digest(rows),
        (*point.capture.nodes, b_node),
    )


class FakeOperations:
    def __init__(self, *, fail_at: str | None = None) -> None:
        self.scope = stage2c._scope(RUN_ID)
        self.points = tuple(_point(table, index) for index, table in enumerate(self.scope.tables))
        self.point_b = tuple(_point_b(point, index) for index, point in enumerate(self.points))
        self.nodes = tuple(node for point in self.points for node in point.capture.nodes)
        self.states = {
            node.key: ir.ObjectState(
                exists=True,
                delete_marker=False,
                version_id=node.source_version_id,
                size=node.size,
                sha256=node.sha256,
            )
            for node in self.nodes
        }
        self.events: list[str] = []
        self.fail_at = fail_at
        self.restore_counter = 0
        self.resource_sha256 = "4" * 64
        self.timeline_sha256 = "5" * 64

    def preflight(self, scope: Any) -> Any:
        assert scope == self.scope
        self.events.append("preflight")
        return (
            _node("capability-canary.bin", "canary", depth=0, size=7)._replace()
            if False
            else ir.GraphNode(
                key=f"{scope.prefix}/capability-canary.bin",
                kind="capability-canary",
                source_version_id="canary-source",
                etag='"canary"',
                size=7,
                sha256=hashlib.sha256(b"canary\n").hexdigest(),
                depth=0,
            )
        )

    def create_point_a(self, scope: Any) -> Any:
        assert scope == self.scope
        self.events.append("point-a")
        return self.points

    def backup_point_a(self) -> Any:
        self.events.append("backup-a")
        return stage2c.RecoveryTarget(f"stage2c_target_{RUN_ID}")

    def append_point_b(self, point_a: Any) -> Any:
        assert point_a == self.points
        self.events.append("point-b")
        return self.point_b

    def verify_prefix_inventory(self, canary: Any, point_a: Any, point_b: Any) -> None:
        assert canary.key == f"{self.scope.prefix}/capability-canary.bin"
        assert tuple(point_a) == self.points
        assert tuple(point_b) == self.point_b
        self.events.append("inventory")

    def predelete_state(self, node: Any) -> Any:
        self.events.append(f"predelete:{node.key}")
        return self.states[node.key]

    def current_state(self, node: Any) -> Any:
        self.events.append(f"current:{node.key}")
        return self.states[node.key]

    def delete_current(self, node: Any) -> Any:
        self.events.append(f"delete:{node.key}")
        marker = f"marker-{node.key.rsplit('/', 1)[-1]}"
        self.states[node.key] = ir.ObjectState(False, True, marker)
        return ir.DeleteResult(True, marker)

    def prove_point_b_broken(self, point_b: Any, approved_nodes: Any) -> None:
        assert tuple(point_b) == self.point_b
        assert set(approved_nodes) == {node for node in self.nodes if node.kind == "data"}
        self.events.append("break-proof")
        if self.fail_at == "break-proof":
            raise stage2c.Stage2CError("injected break failure")

    def stop_source(self) -> None:
        self.events.append("stop-source")

    def restore_catalog(self, target: Any) -> None:
        assert target.name == f"stage2c_target_{RUN_ID}"
        self.events.append("restore-catalog")
        if self.fail_at == "catalog-restore":
            raise stage2c.Stage2CError("injected catalog failure")

    def retained_resources_sha256(self) -> str:
        return self.resource_sha256

    def prefix_timeline_sha256(self, canary: Any, point_a: Any, point_b: Any) -> str:
        assert canary.key == f"{self.scope.prefix}/capability-canary.bin"
        assert tuple(point_a) == self.points
        assert tuple(point_b) == self.point_b
        return self.timeline_sha256

    def start_retained_restored_catalog(self) -> None:
        self.events.append("start-retained-catalog")

    def restore_object(self, node: Any) -> Any:
        self.events.append(f"restore:{node.key}")
        self.restore_counter += 1
        state = ir.ObjectState(
            True,
            False,
            f"promoted-{self.restore_counter}",
            node.size,
            node.sha256,
        )
        self.states[node.key] = state
        return state

    def validate_restored(self, point_a: Any, point_b: Any) -> Any:
        assert tuple(point_a) == self.points
        assert tuple(point_b) == self.point_b
        self.events.append("validate-final")
        if self.fail_at == "final-validation":
            raise stage2c.Stage2CError("injected validation failure")
        return self.points

    def contain(self) -> None:
        self.events.append("contain")
        if self.fail_at == "resource-drift-on-contain":
            self.resource_sha256 = "6" * 64


def _plan(tmp_path: Path) -> tuple[Path, str]:
    result = stage2c.prepare_plan(
        settings=_settings(),
        evidence_root=tmp_path,
        token_factory=lambda: RUN_ID,
        clock=lambda: NOW,
        image_inspector=_pin,
        docker_fingerprint=lambda: "3" * 64,
    )
    return Path(result["plan"]), result["planSha256"]


def _canary() -> Any:
    scope = stage2c._scope(RUN_ID)
    return ir.GraphNode(
        f"{scope.prefix}/capability-canary.bin",
        "capability-canary",
        "canary-source",
        '"canary"',
        7,
        hashlib.sha256(b"canary\n").hexdigest(),
        0,
    )


def _seed_nonterminal_resume(tmp_path: Path, operations: FakeOperations) -> tuple[Path, str]:
    path, digest = _plan(tmp_path)
    campaign_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    recovery = stage2c._recovery_plan(
        campaign_sha256=campaign_sha,
        scope=operations.scope,
        bucket=_settings().bucket,
        canary=_canary(),
        point_a=operations.points,
        target=stage2c.RecoveryTarget(f"stage2c_target_{RUN_ID}"),
        point_b=operations.point_b,
    )
    recovery_path = path.parent / "recovery.plan.json"
    stage2c._atomic_private_write(recovery_path, recovery)
    recovery_sha = hashlib.sha256(recovery_path.read_bytes()).hexdigest()
    nodes = stage2c._damage_nodes(operations.points, operations.point_b)
    journal = stage2c._initial_journal(campaign_sha, recovery_sha, operations.scope, nodes)
    for item, node in zip(journal["nodes"], nodes, strict=True):
        marker = f"marker-{node.key.rsplit('/', 1)[-1]}"
        item["phase"] = "deleted"
        item["deleteMarkerVersionId"] = marker
        operations.states[node.key] = ir.ObjectState(False, True, marker)
    stage2c._atomic_private_write(path.parent / "damage-journal.json", journal)
    return path, digest


def _execute(tmp_path: Path, operations: FakeOperations, monotonic: Any = lambda: 0.0) -> Any:
    path, digest = _plan(tmp_path)
    return stage2c.execute_campaign(
        settings=_settings(),
        plan_path=path,
        expected_sha256=digest,
        operations_factory=lambda _plan, _scope, _run_dir: operations,
        monotonic=monotonic,
        clock=lambda: NOW,
        image_inspector=_pin,
        docker_fingerprint=lambda: "3" * 64,
    )


def _seed_restored_terminal(tmp_path: Path) -> tuple[Path, str, FakeOperations]:
    operations = FakeOperations(fail_at="catalog-restore")
    path, digest = _seed_nonterminal_resume(tmp_path, operations)
    recovery_path = path.parent / "recovery.plan.json"
    recovery_sha = hashlib.sha256(recovery_path.read_bytes()).hexdigest()
    journal_path = path.parent / "damage-journal.json"
    journal = json.loads(journal_path.read_text())
    journal["milestones"] = {
        "deletes": "complete",
        "breakProof": "passed",
        "catalogRestore": "complete",
        "objectRestore": "complete",
        "finalValidation": "pending",
        "containment": "passed",
    }
    nodes_by_key = {node.key: node for node in operations.nodes}
    for index, item in enumerate(journal["nodes"]):
        node = nodes_by_key[item["key"]]
        item["phase"] = "promoted"
        item["promotedVersionId"] = f"promoted-{index}"
        operations.states[node.key] = ir.ObjectState(
            True,
            False,
            item["promotedVersionId"],
            node.size,
            node.sha256,
        )
    stage2c._atomic_private_replace(journal_path, journal)
    stage2c._atomic_private_write(
        path.parent / "failure.json",
        {
            "schemaVersion": 1,
            "status": "failed-uncertain",
            "stage": "2c",
            "campaignSha256": digest,
            "recoveryPlanSha256": recovery_sha,
            "primaryErrorKind": "stage2-c-error",
            "catalogCompensationErrorKind": "stage2-c-error",
            "objectCompensationErrorKind": None,
            "containmentErrorKind": "stage2-c-error",
            "failedAt": "catalog-restore",
            "damage": {"present": True},
            "recordedAt": NOW.isoformat().replace("+00:00", "Z"),
        },
    )
    stage2c._atomic_private_write(
        path.parent / "restoration-correction.json",
        {
            "schemaVersion": 1,
            "status": "restored-and-contained",
            "stage": "2c",
            "catalogRestore": "complete",
            "objectRestore": "complete",
            "containment": "passed",
            "damageCycleConsumed": True,
            "resultClaimed": False,
        },
    )
    return path, digest, operations


def _prepare_validation_plan(
    campaign_path: Path, campaign_sha: str, operations: FakeOperations
) -> dict[str, object]:
    return stage2c.prepare_validation_plan(
        settings=_settings(),
        campaign_path=campaign_path,
        expected_campaign_sha256=campaign_sha,
        operations_factory=lambda *_: operations,
        clock=lambda: NOW,
        image_inspector=_pin,
        docker_fingerprint=lambda: "3" * 64,
    )


def test_prepare_validation_plan_binds_exact_terminal_evidence(tmp_path: Path) -> None:
    campaign_path, campaign_sha, _operations = _seed_restored_terminal(tmp_path)

    result = _prepare_validation_plan(campaign_path, campaign_sha, _operations)

    path = Path(result["plan"])
    assert path.name == "validation.plan.json"
    assert path.stat().st_mode & 0o777 == 0o600
    assert hashlib.sha256(path.read_bytes()).hexdigest() == result["planSha256"]
    plan = json.loads(path.read_text())
    assert plan["planType"] == "stage-2c-validation-only"
    assert plan["scope"] == stage2c._scope_dict(stage2c._scope(RUN_ID))
    for name in (
        "campaign.plan.json",
        "recovery.plan.json",
        "damage-journal.json",
        "failure.json",
        "restoration-correction.json",
    ):
        assert (
            plan["evidenceSha256"][name]
            == hashlib.sha256((campaign_path.parent / name).read_bytes()).hexdigest()
        )
    assert plan["retainedResourcesSha256"] == "4" * 64
    assert plan["prefixTimelineSha256"] == "5" * 64
    assert plan["contract"]["eventualCoherenceOnly"] is True
    assert plan["contract"]["rtoClaimed"] is False
    assert "delete" not in " ".join(plan["contract"]["operations"])
    payload = path.read_text()
    assert _settings().run_secret not in payload
    assert "AWS_SECRET_ACCESS_KEY" not in payload


def test_validation_only_orders_retained_reads_final_validation_and_containment(
    tmp_path: Path,
) -> None:
    campaign_path, campaign_sha, operations = _seed_restored_terminal(tmp_path)
    planned = _prepare_validation_plan(campaign_path, campaign_sha, operations)

    retained_names = (
        "campaign.plan.json",
        "recovery.plan.json",
        "damage-journal.json",
        "failure.json",
        "restoration-correction.json",
    )
    retained_before = {name: (campaign_path.parent / name).read_bytes() for name in retained_names}

    result = stage2c.execute_validation(
        settings=_settings(),
        plan_path=Path(planned["plan"]),
        expected_sha256=planned["planSha256"],
        operations_factory=lambda *_: operations,
        clock=lambda: NOW,
        image_inspector=_pin,
        docker_fingerprint=lambda: "3" * 64,
    )

    assert result == {
        "schemaVersion": 1,
        "status": "pass",
        "stage": "2c-validation-only",
        "runId": RUN_ID,
        "validationPlanSha256": planned["planSha256"],
        "eventualCoherentCorrectness": True,
        "uninterruptedRecoveryClaimed": False,
        "rtoClaimed": False,
        "pointBExcluded": True,
        "containersAbsent": True,
        "retainedEvidence": True,
    }
    assert operations.events[0] == "start-retained-catalog"
    current_events = [event for event in operations.events if event.startswith("current:")]
    assert len(current_events) == len(
        json.loads((campaign_path.parent / "damage-journal.json").read_text())["nodes"]
    )
    assert operations.events.index("validate-final") < operations.events.index("inventory")
    assert operations.events[-1] == "contain"
    assert not any(
        event.startswith(prefix)
        for event in operations.events
        for prefix in ("delete:", "restore:", "restore-catalog", "backup-a", "point-b")
    )
    assert not (campaign_path.parent / "result.json").exists()
    assert (
        json.loads((campaign_path.parent / "damage-journal.json").read_text())["milestones"][
            "finalValidation"
        ]
        == "pending"
    )
    assert (campaign_path.parent / "validation-result.json").exists()
    assert retained_before == {
        name: (campaign_path.parent / name).read_bytes() for name in retained_names
    }


@pytest.mark.parametrize("drift", ("resource", "timeline"))
def test_validation_refuses_retained_state_drift_before_start(tmp_path: Path, drift: str) -> None:
    campaign_path, campaign_sha, operations = _seed_restored_terminal(tmp_path)
    planned = _prepare_validation_plan(campaign_path, campaign_sha, operations)
    if drift == "resource":
        operations.resource_sha256 = "6" * 64
    else:
        operations.timeline_sha256 = "6" * 64

    with pytest.raises(stage2c.Stage2CError, match="differ"):
        stage2c.execute_validation(
            settings=_settings(),
            plan_path=Path(planned["plan"]),
            expected_sha256=planned["planSha256"],
            operations_factory=lambda *_: operations,
            clock=lambda: NOW,
            image_inspector=_pin,
            docker_fingerprint=lambda: "3" * 64,
        )

    assert operations.events == []
    assert not (campaign_path.parent / "validation-started.json").exists()


def test_validation_reports_retained_resource_drift_as_uncertain_containment(
    tmp_path: Path,
) -> None:
    campaign_path, campaign_sha, operations = _seed_restored_terminal(tmp_path)
    planned = _prepare_validation_plan(campaign_path, campaign_sha, operations)
    operations.fail_at = "resource-drift-on-contain"

    with pytest.raises(stage2c.Stage2CError, match="containment is incomplete"):
        stage2c.execute_validation(
            settings=_settings(),
            plan_path=Path(planned["plan"]),
            expected_sha256=planned["planSha256"],
            operations_factory=lambda *_: operations,
            clock=lambda: NOW,
            image_inspector=_pin,
            docker_fingerprint=lambda: "3" * 64,
        )

    failure = json.loads((campaign_path.parent / "validation-failure.json").read_text())
    assert failure["status"] == "failed-containment-uncertain"
    assert failure["containmentErrorKind"] == "stage2-c-error"
    assert not (campaign_path.parent / "validation-result.json").exists()


def test_validation_watchdog_contains_before_a_blocked_operation_can_start(
    tmp_path: Path,
) -> None:
    campaign_path, campaign_sha, operations = _seed_restored_terminal(tmp_path)
    planned = _prepare_validation_plan(campaign_path, campaign_sha, operations)

    class ImmediateWatchdog:
        daemon = False

        def __init__(self, seconds: float, callback: Any) -> None:
            assert 0 < seconds <= stage2c._VALIDATION_OBJECTIVE_SECONDS
            self.callback = callback

        def start(self) -> None:
            self.callback()

        def cancel(self) -> None:
            return None

    with pytest.raises(stage2c.Stage2CError, match="safety deadline expired"):
        stage2c.execute_validation(
            settings=_settings(),
            plan_path=Path(planned["plan"]),
            expected_sha256=planned["planSha256"],
            operations_factory=lambda *_: operations,
            clock=lambda: NOW,
            image_inspector=_pin,
            docker_fingerprint=lambda: "3" * 64,
            watchdog_factory=ImmediateWatchdog,
        )

    assert "start-retained-catalog" not in operations.events
    assert operations.events == ["contain", "contain"]
    assert (
        json.loads((campaign_path.parent / "validation-failure.json").read_text())["status"]
        == "failed-contained"
    )


def test_validation_safety_deadline_contains_without_claiming_rto(tmp_path: Path) -> None:
    campaign_path, campaign_sha, operations = _seed_restored_terminal(tmp_path)
    planned = _prepare_validation_plan(campaign_path, campaign_sha, operations)

    with pytest.raises(stage2c.Stage2CError, match="safety deadline expired"):
        stage2c.execute_validation(
            settings=_settings(),
            plan_path=Path(planned["plan"]),
            expected_sha256=planned["planSha256"],
            operations_factory=lambda *_: operations,
            clock=lambda: NOW,
            monotonic=lambda: (
                stage2c._VALIDATION_OBJECTIVE_SECONDS + 1
                if "start-retained-catalog" in operations.events
                else 0
            ),
            image_inspector=_pin,
            docker_fingerprint=lambda: "3" * 64,
        )

    assert operations.events == ["start-retained-catalog", "contain"]
    failure = json.loads((campaign_path.parent / "validation-failure.json").read_text())
    assert failure["failedAt"] == "retained-catalog-start"
    assert failure["status"] == "failed-contained"


def test_validation_failure_is_contained_sanitized_and_not_replayed(tmp_path: Path) -> None:
    campaign_path, campaign_sha, operations = _seed_restored_terminal(tmp_path)
    operations.fail_at = "final-validation"
    planned = _prepare_validation_plan(campaign_path, campaign_sha, operations)
    kwargs = {
        "settings": _settings(),
        "plan_path": Path(planned["plan"]),
        "expected_sha256": planned["planSha256"],
        "clock": lambda: NOW,
        "image_inspector": _pin,
        "docker_fingerprint": lambda: "3" * 64,
    }

    with pytest.raises(stage2c.Stage2CError, match="injected validation failure"):
        stage2c.execute_validation(
            **kwargs,
            operations_factory=lambda *_: operations,
        )

    assert operations.events[-1] == "contain"
    assert not (campaign_path.parent / "validation-result.json").exists()
    failure = json.loads((campaign_path.parent / "validation-failure.json").read_text())
    assert failure["status"] == "failed-contained"
    assert failure["failedAt"] == "final-validation"
    assert failure["primaryErrorKind"] == "stage2-c-error"
    assert "injected" not in json.dumps(failure)

    with pytest.raises(stage2c.Stage2CError, match="terminal evidence"):
        stage2c.execute_validation(
            **kwargs,
            operations_factory=lambda *_: pytest.fail("terminal validation replayed"),
        )


def test_interrupted_validation_only_contains_and_never_revalidates(tmp_path: Path) -> None:
    campaign_path, campaign_sha, operations = _seed_restored_terminal(tmp_path)
    planned = _prepare_validation_plan(campaign_path, campaign_sha, operations)
    stage2c._atomic_private_write(
        campaign_path.parent / "validation-started.json",
        {
            "schemaVersion": 1,
            "stage": "2c-validation-only",
            "runId": RUN_ID,
            "validationPlanSha256": planned["planSha256"],
        },
    )

    def interrupted_containment(*_args: Any) -> str:
        operations.events.append("contain")
        return "4" * 64

    with pytest.raises(stage2c.Stage2CError, match="cannot be replayed"):
        stage2c.execute_validation(
            settings=replace(
                _settings(),
                run_secret="changed-" * 8,  # secret-scan: allow
            ),
            plan_path=Path(planned["plan"]),
            expected_sha256=planned["planSha256"],
            operations_factory=lambda *_: pytest.fail(
                "interrupted containment created AWS-backed operations"
            ),
            clock=lambda: NOW + stage2c._PLAN_LIFETIME * 2,
            image_inspector=lambda _reference: pytest.fail(
                "interrupted containment inspected mutable image tags"
            ),
            docker_fingerprint=lambda: pytest.fail(
                "interrupted containment required the current Docker fingerprint"
            ),
            interrupted_containment=interrupted_containment,
        )

    assert operations.events == ["contain"]
    assert (
        json.loads((campaign_path.parent / "validation-failure.json").read_text())["failedAt"]
        == "interrupted"
    )


@pytest.mark.parametrize(
    "name",
    (
        "campaign.plan.json",
        "recovery.plan.json",
        "damage-journal.json",
        "failure.json",
        "restoration-correction.json",
    ),
)
def test_validation_rejects_any_changed_retained_evidence(tmp_path: Path, name: str) -> None:
    campaign_path, campaign_sha, operations = _seed_restored_terminal(tmp_path)
    planned = _prepare_validation_plan(campaign_path, campaign_sha, operations)
    evidence = campaign_path.parent / name
    evidence.write_bytes(evidence.read_bytes() + b" ")
    evidence.chmod(0o600)

    with pytest.raises(stage2c.Stage2CError):
        stage2c.execute_validation(
            settings=_settings(),
            plan_path=Path(planned["plan"]),
            expected_sha256=planned["planSha256"],
            operations_factory=lambda *_: pytest.fail("tampered evidence created operations"),
            clock=lambda: NOW,
            image_inspector=_pin,
            docker_fingerprint=lambda: "3" * 64,
        )

    assert not (campaign_path.parent / "validation-started.json").exists()
    assert operations.events == []


@pytest.mark.parametrize("mutation", ("final-validation", "node-receipt", "campaign-link"))
def test_prepare_validation_rejects_nonexact_restored_terminal_state(
    tmp_path: Path, mutation: str
) -> None:
    campaign_path, campaign_sha, _operations = _seed_restored_terminal(tmp_path)
    journal_path = campaign_path.parent / "damage-journal.json"
    journal = json.loads(journal_path.read_text())
    if mutation == "final-validation":
        journal["milestones"]["finalValidation"] = "passed"
    elif mutation == "node-receipt":
        journal["nodes"][0]["deleteMarkerVersionId"] = None
    else:
        journal["campaignSha256"] = "f" * 64
    stage2c._atomic_private_replace(journal_path, journal)

    with pytest.raises(stage2c.Stage2CError):
        _prepare_validation_plan(campaign_path, campaign_sha, _operations)

    assert not (campaign_path.parent / "validation.plan.json").exists()


def test_prepare_validation_rejects_existing_campaign_success(tmp_path: Path) -> None:
    campaign_path, campaign_sha, _operations = _seed_restored_terminal(tmp_path)
    stage2c._atomic_private_write(campaign_path.parent / "result.json", {"status": "pass"})

    with pytest.raises(stage2c.Stage2CError, match="successful Stage 2C evidence"):
        _prepare_validation_plan(campaign_path, campaign_sha, _operations)


def test_prepare_is_private_bounded_secret_free_and_exactly_two_tables(tmp_path: Path) -> None:
    path, digest = _plan(tmp_path)

    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    plan = json.loads(path.read_text())
    assert plan["scope"]["prefix"] == (f"integration/recovery/{RUN_ID}/stage1/warehouse")
    assert len(plan["scope"]["tables"]) == 2
    assert plan["contract"]["liveObjectiveSeconds"] == 1200
    assert plan["contract"]["compensationIgnoresObjective"] is True
    pins = stage2c._planned_images(plan["stack"])
    assert {name: pin.image_id for name, pin in pins.items()} == {
        name: "sha256:" + "2" * 64 for name in stage2c._IMAGE_REFERENCES
    }
    payload = path.read_text()
    assert _settings().run_secret not in payload
    assert "AWS_SECRET_ACCESS_KEY" not in payload
    assert "POSTGRES_PASSWORD" not in payload


def test_success_orders_catalog_backup_damage_restore_and_exact_validation(tmp_path: Path) -> None:
    operations = FakeOperations()

    result = _execute(tmp_path, operations)

    assert result["status"] == "pass"
    assert result["tableCount"] == 2
    first_delete = next(
        index for index, event in enumerate(operations.events) if event.startswith("delete:")
    )
    last_delete = max(
        index for index, event in enumerate(operations.events) if event.startswith("delete:")
    )
    assert operations.events.index("backup-a") < operations.events.index("point-b") < first_delete
    assert last_delete < operations.events.index("break-proof")
    assert operations.events.index("break-proof") < operations.events.index("restore-catalog")
    first_restore = next(
        index for index, event in enumerate(operations.events) if event.startswith("restore:")
    )
    assert operations.events.index("restore-catalog") < first_restore
    assert (
        first_restore
        < operations.events.index("validate-final")
        < operations.events.index("contain")
    )
    journal = json.loads((tmp_path / RUN_ID / "damage-journal.json").read_text())
    assert journal["milestones"] == {
        "deletes": "complete",
        "breakProof": "passed",
        "catalogRestore": "complete",
        "objectRestore": "complete",
        "finalValidation": "passed",
        "containment": "passed",
    }
    assert {entry["phase"] for entry in journal["nodes"]} == {"promoted"}


def test_failure_after_damage_compensates_without_obeying_live_cap(tmp_path: Path) -> None:
    operations = FakeOperations(fail_at="break-proof")
    ticks = iter([0.0, 1.0, 2.0, 3.0, 4.0, *([1199.0] * 20)])

    with pytest.raises(stage2c.Stage2CError, match="injected break failure"):
        _execute(tmp_path, operations, monotonic=lambda: next(ticks))

    assert all(state.exists and not state.delete_marker for state in operations.states.values())
    assert len([event for event in operations.events if event.startswith("restore:")]) == 2
    assert operations.events[-1] == "contain"
    journal = json.loads((tmp_path / RUN_ID / "damage-journal.json").read_text())
    assert journal["milestones"]["objectRestore"] == "complete"
    assert journal["milestones"]["containment"] == "passed"
    failure = json.loads((tmp_path / RUN_ID / "failure.json").read_text())
    assert failure["status"] == "failed-contained"
    assert failure["primaryErrorKind"] == "stage2-c-error"
    assert failure["failedAt"] == "break-proof"
    assert failure["objectCompensationErrorKind"] is None
    assert failure["containmentErrorKind"] is None


def test_incomplete_catalog_compensation_is_reported_without_skipping_objects(
    tmp_path: Path,
) -> None:
    class IncompleteCatalogCompensation(FakeOperations):
        def restore_catalog(self, target: Any) -> None:
            del target
            self.events.append("restore-catalog-failed")
            raise stage2c.Stage2CError("catalog compensation failed")

    operations = IncompleteCatalogCompensation(fail_at="break-proof")

    with pytest.raises(stage2c.Stage2CError, match="compensation or containment is incomplete"):
        _execute(tmp_path, operations)

    assert len([event for event in operations.events if event.startswith("restore:")]) == 2
    failure = json.loads((tmp_path / RUN_ID / "failure.json").read_text())
    assert failure["catalogCompensationErrorKind"] == "stage2-c-error"
    assert failure["objectCompensationErrorKind"] is None


def test_restore_only_resume_never_deletes_or_claims_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resumed = FakeOperations()
    path, digest = _seed_nonterminal_resume(tmp_path, resumed)

    monkeypatch.setattr(
        stage2c,
        "_binding",
        lambda _configuration: (_ for _ in ()).throw(
            AssertionError("resume recomputed drifted source/runtime")
        ),
    )
    drifted_settings = replace(
        _settings(),
        run_secret="changed-" * 8,  # secret-scan: allow
    )
    with pytest.raises(stage2c.Stage2CError, match="restoration only"):
        stage2c.execute_campaign(
            settings=drifted_settings,
            plan_path=path,
            expected_sha256=digest,
            operations_factory=lambda *_: resumed,
            clock=lambda: NOW + stage2c._PLAN_LIFETIME * 2,
            image_inspector=lambda _reference: (_ for _ in ()).throw(
                AssertionError("resume inspected mutable image tag")
            ),
            docker_fingerprint=lambda: (_ for _ in ()).throw(
                AssertionError("resume inspected changed Docker runtime")
            ),
        )

    assert not any(event.startswith("delete:") for event in resumed.events)
    assert "validate-final" not in resumed.events
    assert resumed.events[-1] == "contain"
    assert (path.parent / "restoration-only.json").exists()


def test_terminal_failure_receipt_blocks_replay(tmp_path: Path) -> None:
    operations = FakeOperations(fail_at="break-proof")
    path, digest = _plan(tmp_path)
    with pytest.raises(stage2c.Stage2CError):
        stage2c.execute_campaign(
            settings=_settings(),
            plan_path=path,
            expected_sha256=digest,
            operations_factory=lambda *_: operations,
            clock=lambda: NOW,
            image_inspector=_pin,
            docker_fingerprint=lambda: "3" * 64,
        )

    with pytest.raises(stage2c.Stage2CError, match="terminal evidence"):
        stage2c.execute_campaign(
            settings=_settings(),
            plan_path=path,
            expected_sha256=digest,
            operations_factory=lambda *_: pytest.fail("terminal replay created operations"),
            clock=lambda: NOW,
            image_inspector=_pin,
            docker_fingerprint=lambda: "3" * 64,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("bucket", "other-private-bucket"),
        ("region", "us-east-1"),
        ("storage_role_arn", "arn:aws:iam::999999999999:role/stage2c-test"),
    ),
)
def test_restore_only_still_enforces_planned_target(tmp_path: Path, field: str, value: str) -> None:
    operations = FakeOperations()
    path, digest = _seed_nonterminal_resume(tmp_path / field, operations)
    settings = replace(_settings(), **{field: value})

    with pytest.raises(stage2c.Stage2CError, match="target differs"):
        stage2c.execute_campaign(
            settings=settings,
            plan_path=path,
            expected_sha256=digest,
            operations_factory=lambda *_: pytest.fail("invalid target created operations"),
            clock=lambda: NOW + stage2c._PLAN_LIFETIME * 2,
            image_inspector=_pin,
            docker_fingerprint=lambda: "3" * 64,
        )


def test_nonblocking_execution_lock_rejects_concurrent_owner(tmp_path: Path) -> None:
    path, digest = _plan(tmp_path)
    with stage2c._execution_lock(path.parent):
        with pytest.raises(stage2c.Stage2CError, match="another Stage 2C execution"):
            stage2c.execute_campaign(
                settings=_settings(),
                plan_path=path,
                expected_sha256=digest,
                operations_factory=lambda *_: pytest.fail("concurrent run created operations"),
                clock=lambda: NOW,
                image_inspector=_pin,
                docker_fingerprint=lambda: "3" * 64,
            )


@pytest.mark.parametrize("terminal_name", ("result.json", "failure.json", "restoration-only.json"))
def test_any_terminal_evidence_consumes_plan(tmp_path: Path, terminal_name: str) -> None:
    path, digest = _plan(tmp_path / terminal_name)
    stage2c._atomic_private_write(path.parent / terminal_name, {"status": "terminal"})

    with pytest.raises(stage2c.Stage2CError, match="terminal evidence"):
        stage2c.execute_campaign(
            settings=_settings(),
            plan_path=path,
            expected_sha256=digest,
            operations_factory=lambda *_: pytest.fail("consumed plan created operations"),
            clock=lambda: NOW,
            image_inspector=_pin,
            docker_fingerprint=lambda: "3" * 64,
        )


def test_restore_only_rejects_changed_campaign_hash(tmp_path: Path) -> None:
    operations = FakeOperations()
    path, _digest = _seed_nonterminal_resume(tmp_path, operations)

    with pytest.raises(stage2c.Stage2CError, match="differs from approval"):
        stage2c.execute_campaign(
            settings=_settings(),
            plan_path=path,
            expected_sha256="f" * 64,
            operations_factory=lambda *_: pytest.fail("changed campaign created operations"),
            clock=lambda: NOW + stage2c._PLAN_LIFETIME * 2,
            image_inspector=_pin,
            docker_fingerprint=lambda: "3" * 64,
        )


def test_restore_only_rejects_changed_recovery_hash(tmp_path: Path) -> None:
    operations = FakeOperations()
    path, digest = _seed_nonterminal_resume(tmp_path, operations)
    recovery_path = path.parent / "recovery.plan.json"
    recovery_path.write_bytes(recovery_path.read_bytes() + b" \n")
    recovery_path.chmod(0o600)

    with pytest.raises(stage2c.Stage2CError, match="differs from recovery plan"):
        stage2c.execute_campaign(
            settings=_settings(),
            plan_path=path,
            expected_sha256=digest,
            operations_factory=lambda *_: pytest.fail("changed recovery created operations"),
            clock=lambda: NOW + stage2c._PLAN_LIFETIME * 2,
            image_inspector=_pin,
            docker_fingerprint=lambda: "3" * 64,
        )


def test_terminal_journal_without_receipt_cannot_resume(tmp_path: Path) -> None:
    operations = FakeOperations()
    path, digest = _seed_nonterminal_resume(tmp_path, operations)
    journal_path = path.parent / "damage-journal.json"
    journal = json.loads(journal_path.read_text())
    journal["milestones"]["containment"] = "passed"
    stage2c._atomic_private_replace(journal_path, journal)

    with pytest.raises(stage2c.Stage2CError, match="journal is already terminal"):
        stage2c.execute_campaign(
            settings=_settings(),
            plan_path=path,
            expected_sha256=digest,
            operations_factory=lambda *_: pytest.fail("terminal journal created operations"),
            clock=lambda: NOW,
            image_inspector=_pin,
            docker_fingerprint=lambda: "3" * 64,
        )


def test_deadline_expiry_during_restore_forces_compensation_and_cannot_pass(
    tmp_path: Path,
) -> None:
    operations = FakeOperations()

    def deadline_clock() -> float:
        return 2001.0 if "restore-catalog" in operations.events else 0.0

    with pytest.raises(stage2c.Stage2CError, match="success objective expired"):
        _execute(tmp_path, operations, monotonic=deadline_clock)

    assert len([event for event in operations.events if event == "restore-catalog"]) == 2
    assert all(state.exists and not state.delete_marker for state in operations.states.values())
    assert operations.events[-1] == "contain"
    assert not (tmp_path / RUN_ID / "result.json").exists()
    assert (tmp_path / RUN_ID / "failure.json").exists()


def test_pre_damage_objective_blocks_journal_and_first_delete(tmp_path: Path) -> None:
    operations = FakeOperations()
    ticks = iter([0.0, 1.0, 2.0, 3.0, 4.0, 1201.0])

    with pytest.raises(stage2c.Stage2CError, match="objective expired"):
        _execute(tmp_path, operations, monotonic=lambda: next(ticks))

    assert not any(event.startswith("delete:") for event in operations.events)
    assert "contain" in operations.events
    assert not (tmp_path / RUN_ID / "damage-journal.json").exists()


def test_damage_selection_is_recomputed_from_point_b_live_dependencies_only() -> None:
    scope = stage2c._scope(RUN_ID)
    points = tuple(_point(table, index) for index, table in enumerate(scope.tables))
    point_b = tuple(_point_b(point, index) for index, point in enumerate(points))

    selected = stage2c._damage_nodes(points, point_b)

    assert len(selected) == 2
    assert {node.kind for node in selected} == {"data"}
    assert all(node.key in point_b[index].graph_keys for index, node in enumerate(selected))
    recovery = stage2c._recovery_plan(
        campaign_sha256="a" * 64,
        scope=scope,
        bucket="private-test-bucket",
        canary=ir.GraphNode(
            f"{scope.prefix}/capability-canary.bin",
            "capability-canary",
            "canary-source",
            '"canary"',
            7,
            hashlib.sha256(b"canary\n").hexdigest(),
            0,
        ),
        point_a=points,
        target=stage2c.RecoveryTarget(f"stage2c_target_{RUN_ID}"),
        point_b=point_b,
    )
    assert [item["key"] for item in recovery["damageNodes"]] == [node.key for node in selected]


def test_validation_prefix_fingerprint_rejects_foreign_keys() -> None:
    operations = object.__new__(stage2c.LiveJointRecoveryOperations)
    operations.store = SimpleNamespace(prefix_keys=lambda: frozenset({"foreign/key"}))
    points = tuple(
        _point(table, index) for index, table in enumerate(stage2c._scope(RUN_ID).tables)
    )
    point_b = tuple(_point_b(point, index) for index, point in enumerate(points))

    with pytest.raises(stage2c.Stage2CError, match="foreign or missing keys"):
        operations.prefix_timeline_sha256(_canary(), points, point_b)


def test_break_proof_uses_exact_stage1_uri_boundaries() -> None:
    location = "s3://private-test-bucket/path/data.parquet"
    assert (
        stage2c.LiveJointRecoveryOperations._missing_location(
            FileNotFoundError(f'missing "{location}"'), {location}
        )
        == location
    )
    for confused in (
        f"{location}.suffix",
        f"prefix{location}",
        f"{location}/child",
    ):
        assert (
            stage2c.LiveJointRecoveryOperations._missing_location(
                FileNotFoundError(confused), {location}
            )
            is None
        )


def test_break_proof_rejects_cross_table_missing_object_match() -> None:
    operations = object.__new__(stage2c.LiveJointRecoveryOperations)
    operations.settings = _settings()
    points = tuple(
        _point(table, index) for index, table in enumerate(stage2c._scope(RUN_ID).tables)
    )
    point_b = tuple(_point_b(point, index) for index, point in enumerate(points))
    approved = tuple(point.capture.nodes[-1] for point in points)
    beta_location = f"s3://{_settings().bucket}/{approved[1].key}"

    class BrokenTable:
        def scan(self) -> Any:
            return self

        def to_arrow(self) -> Any:
            raise FileNotFoundError(beta_location)

    operations._point_b_tables = {state.table: BrokenTable() for state in point_b}
    operations._point_b_ios = {}

    with pytest.raises(stage2c.Stage2CError, match="not an approved missing object"):
        operations.prove_point_b_broken(point_b, approved)


def test_catalog_read_retries_only_bounded_server_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pyiceberg.exceptions import ServerError

    marker = object()

    class Catalog:
        calls = 0

        def load_table(self, identifier: tuple[str, str]) -> object:
            assert identifier == ("namespace", "table")
            self.calls += 1
            if self.calls < stage2c._CATALOG_READ_ATTEMPTS:
                raise ServerError("bounded transient")
            return marker

    sleeps: list[float] = []
    monkeypatch.setattr(stage2c.time, "sleep", sleeps.append)
    catalog = Catalog()
    operations = object.__new__(stage2c.LiveJointRecoveryOperations)

    assert operations._load_table(catalog, ("namespace", "table")) is marker
    assert catalog.calls == stage2c._CATALOG_READ_ATTEMPTS
    assert sleeps == [stage2c._CATALOG_RETRY_DELAY_SECONDS] * 2

    from pyiceberg.exceptions import UnauthorizedError

    class UnauthorizedCatalog:
        calls = 0

        def load_table(self, identifier: tuple[str, str]) -> object:
            del identifier
            self.calls += 1
            raise UnauthorizedError("not retriable")

    unauthorized = UnauthorizedCatalog()
    with pytest.raises(UnauthorizedError):
        operations._load_table(unauthorized, ("namespace", "table"))
    assert unauthorized.calls == 1
    assert sleeps == [stage2c._CATALOG_RETRY_DELAY_SECONDS] * 2


def test_ambiguous_append_response_reconciles_only_exact_committed_successor() -> None:
    from pyiceberg.exceptions import CommitStateUnknownException

    expected = ({"event_id": 1, "generation": "point-a", "value": 10},)
    marker = object()
    append_calls: list[object] = []

    class BeforeTable:
        metadata_location = "s3://private-test-bucket/table/metadata/00000.json"
        metadata = SimpleNamespace(table_uuid="table-uuid", snapshots=[], metadata_log=[])

        def current_snapshot(self) -> None:
            return None

        def append(self, batch: object) -> None:
            append_calls.append(batch)
            raise CommitStateUnknownException("commit response lost")

    def after_table(mutation: str | None = None) -> Any:
        metadata_location = "s3://private-test-bucket/table/metadata/00001.json"
        table_uuid = "table-uuid"
        metadata_log = [SimpleNamespace(metadata_file=BeforeTable.metadata_location)]
        snapshots = [SimpleNamespace(snapshot_id=101, parent_snapshot_id=None)]
        if mutation == "uuid":
            table_uuid = "other-uuid"
        elif mutation == "metadata":
            metadata_location = BeforeTable.metadata_location
        elif mutation == "lineage":
            metadata_log = []
        elif mutation == "snapshots":
            snapshots = []
        elif mutation == "parent":
            snapshots[0].parent_snapshot_id = 999
        return SimpleNamespace(
            metadata_location=metadata_location,
            metadata=SimpleNamespace(
                table_uuid=table_uuid,
                snapshots=snapshots,
                metadata_log=metadata_log,
            ),
            current_snapshot=lambda: snapshots[-1] if snapshots else None,
        )

    class Catalog:
        def __init__(self, mutation: str | None = None) -> None:
            self.mutation = mutation

        def load_table(self, identifier: tuple[str, str]) -> Any:
            assert identifier == ("namespace", "table")
            return after_table(self.mutation)

    operations = object.__new__(stage2c.LiveJointRecoveryOperations)
    operations._fence = lambda table: table  # type: ignore[method-assign]
    operations._rows = lambda table: expected  # type: ignore[method-assign]

    reconciled = operations._append_and_reload(
        catalog=Catalog(),
        identifier=("namespace", "table"),
        table=BeforeTable(),
        batch=marker,
        expected_rows=expected,
        expected_snapshots=1,
    )
    assert reconciled.metadata.table_uuid == "table-uuid"
    assert append_calls == [marker]

    for mutation in ("uuid", "metadata", "lineage", "snapshots", "parent"):
        append_calls.clear()
        with pytest.raises(stage2c.Stage2CError, match="exact expected successor"):
            operations._append_and_reload(
                catalog=Catalog(mutation),
                identifier=("namespace", "table"),
                table=BeforeTable(),
                batch=marker,
                expected_rows=expected,
                expected_snapshots=1,
            )
        assert append_calls == [marker]

    append_calls.clear()
    operations._rows = lambda table: ()  # type: ignore[method-assign]
    with pytest.raises(stage2c.Stage2CError, match="exact expected successor"):
        operations._append_and_reload(
            catalog=Catalog(),
            identifier=("namespace", "table"),
            table=BeforeTable(),
            batch=marker,
            expected_rows=expected,
            expected_snapshots=1,
        )
    assert append_calls == [marker]


def test_complete_inventory_enforces_point_b_bytes_and_actual_version_metadata() -> None:
    scope = stage2c._scope(RUN_ID)
    points = tuple(_point(table, index) for index, table in enumerate(scope.tables))
    point_b = tuple(_point_b(point, index) for index, point in enumerate(points))
    canary = ir.GraphNode(
        f"{scope.prefix}/capability-canary.bin",
        "capability-canary",
        "canary-source",
        '"canary"',
        7,
        hashlib.sha256(b"canary\n").hexdigest(),
        0,
    )
    current = stage2c._complete_nodes(canary, points, point_b)

    class ExactStore:
        corrupt_key: str | None = None

        def prefix_keys(self) -> frozenset[str]:
            return frozenset(current)

        def list_versions(self, key: str) -> tuple[Any, ...]:
            node = current[key]
            size = node.size + 1 if key == self.corrupt_key else node.size
            return (ir.VersionEntry(key, "current", True, False, node.etag, size),)

        def current_state(self, node: Any) -> Any:
            return ir.ObjectState(True, False, "current", node.size, node.sha256)

        def exact_source_state(self, node: Any) -> Any:
            return ir.ObjectState(True, False, node.source_version_id, node.size, node.sha256)

    operations = object.__new__(stage2c.LiveJointRecoveryOperations)
    operations.store = ExactStore()
    operations.verify_prefix_inventory(canary, points, point_b)
    operations.store.corrupt_key = next(iter(current))
    with pytest.raises(stage2c.Stage2CError, match="version metadata"):
        operations.verify_prefix_inventory(canary, points, point_b)

    huge = ir.GraphNode(
        point_b[0].nodes[-1].key,
        "metadata",
        "huge-version",
        '"huge"',
        stage2c._MAX_BYTES,
        "f" * 64,
        0,
    )
    oversized_b = (
        stage2c.PointBState(
            point_b[0].table,
            point_b[0].metadata_location,
            point_b[0].snapshot_id,
            point_b[0].rows_sha256,
            (*point_b[0].nodes[:-1], huge),
        ),
        point_b[1],
    )
    with pytest.raises(stage2c.Stage2CError, match="aggregate byte limit"):
        stage2c._complete_nodes(canary, points, oversized_b)


def test_scope_bounds_disjointness_and_exact_point_a_equality() -> None:
    scope = stage2c._scope(RUN_ID)
    points = tuple(_point(table, index) for index, table in enumerate(scope.tables))
    assert len(stage2c._validate_point_a(scope, points)) == 4

    overlapping = stage2c.TablePoint(
        points[1].table,
        ir.TableCapture(
            bucket=points[1].capture.bucket,
            table_uuid=points[1].capture.table_uuid,
            metadata_location=points[1].capture.metadata_location,
            snapshot_id=points[1].capture.snapshot_id,
            schema_sha256=points[1].capture.schema_sha256,
            row_count=3,
            rows_sha256=points[1].capture.rows_sha256,
            nodes=(points[0].capture.nodes[0],),
        ),
        stage2c._logical_graph_sha256((points[0].capture.nodes[0],)),
    )
    with pytest.raises(stage2c.Stage2CError, match="table prefix"):
        stage2c._validate_point_a(scope, (points[0], overlapping))

    changed = stage2c.TablePoint(
        points[1].table,
        ir.TableCapture(
            **{
                **points[1].capture.__dict__,
                "rows_sha256": "f" * 64,
            }
        ),
        points[1].logical_graph_sha256,
    )
    with pytest.raises(stage2c.Stage2CError, match="exact point A"):
        stage2c._validate_final(
            points,
            (points[0], changed),
            tuple(_point_b(point, index) for index, point in enumerate(points)),
        )


def test_final_live_validation_uses_fresh_restored_pitr_gateway() -> None:
    validation_source = inspect.getsource(stage2c.LiveJointRecoveryOperations.validate_restored)
    gateway_source = inspect.getsource(stage2c.LiveJointRecoveryOperations._gateway)
    restored_url_source = inspect.getsource(stage2c.LocalJointStack.restored_url.fget)

    assert "_gateway(restored=True)" in validation_source
    assert "self.stack.restored_url if restored else self.stack.source_url" in gateway_source
    assert "start_restored_polaris" in restored_url_source


def test_graph_capture_snapshot_count_is_parameterized_and_stage1_default_remains_one() -> None:
    class Metadata:
        format_version = 2
        current_snapshot_id = 1
        refs = {"main": type("Ref", (), {"snapshot_id": 1})()}
        metadata_log: list[Any] = []
        statistics: list[Any] = []
        partition_statistics: list[Any] = []

        def __init__(self, count: int) -> None:
            self.snapshots = [object()] * count

    class Snapshot:
        snapshot_id = 1
        manifest_list = "s3://bucket/prefix/list.avro"

        def manifests(self, _io: Any) -> list[Any]:
            return []

    class Table:
        metadata_location = "s3://bucket/prefix/metadata.json"
        io = object()

        def __init__(self, count: int) -> None:
            self.metadata = Metadata(count)

        def current_snapshot(self) -> Any:
            return Snapshot()

    assert len(ir.capture_iceberg_graph(Table(1))) == 2
    assert len(ir.capture_iceberg_graph(Table(2), expected_snapshot_count=2)) == 2
    with pytest.raises(ir.DrillError, match="unexpected snapshot count"):
        ir.capture_iceberg_graph(Table(2))


class RecordingExecutor:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []
        self.inputs: list[str | None] = []

    def run(self, command: Any, *, stdin: str | None = None) -> Any:
        self.commands.append(tuple(command))
        self.inputs.append(stdin)
        stdout = ""
        stderr = ""
        returncode = 0
        if tuple(command[:2]) == ("docker", "port"):
            stdout = "127.0.0.1:49152\n"
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    def spawn(self, command: Any, *, stdin: str) -> Any:
        self.commands.append(tuple(command))
        self.inputs.append(stdin)

        class Child:
            def wait(self, timeout: int | None = None) -> int:
                del timeout
                return 0

        return Child()


def test_local_stack_launches_only_deserialized_immutable_image_ids() -> None:
    source = inspect.getsource(stage2c.LocalJointStack)
    assert "_POSTGRES_IMAGE" not in source
    assert "_ADMIN_IMAGE" not in source
    assert "_POLARIS_IMAGE" not in source
    assert ".image_id" in source


def test_each_container_role_uses_its_own_pinned_image_id() -> None:
    executor = RecordingExecutor()
    scope = stage2c._scope(RUN_ID)
    pins = {
        name: ir.ImagePin(
            reference,
            f"sha256:{index}" + "0" * 63,
            ("/entrypoint",),
            ("run",),
        )
        for index, (name, reference) in enumerate(stage2c._IMAGE_REFERENCES.items(), start=1)
    }
    stack = stage2c.LocalJointStack(
        scope=scope,
        resources=stage2c._resources(scope),
        images=pins,
        campaign_sha256="a" * 64,
        credentials=ir.RunCredentials("db-secret-value", "client-id", "client-secret-value"),
        aws_credentials=ir.AwsCredentials("A" * 20, "s" * 40, "t" * 40),
        region="us-west-1",
        executor=executor,
    )
    stack._owned_inventory = lambda *, require_retained: {}  # type: ignore[method-assign]
    stack._owned_id = lambda name: f"owned-{name}"  # type: ignore[method-assign]
    stack._remove_owned = lambda name: None  # type: ignore[method-assign]

    stack.create()

    commands = "\n".join(" ".join(command) for command in executor.commands)
    assert all(pin.image_id in commands for pin in pins.values())
    assert all(pin.reference not in commands for pin in pins.values())


def _local_stack(executor: Any) -> Any:
    scope = stage2c._scope(RUN_ID)
    return stage2c.LocalJointStack(
        scope=scope,
        resources=stage2c._resources(scope),
        images={name: _pin(reference) for name, reference in stage2c._IMAGE_REFERENCES.items()},
        campaign_sha256="a" * 64,
        credentials=ir.RunCredentials("db-secret-value", "client-id", "client-secret-value"),
        aws_credentials=ir.AwsCredentials(
            "A" * 20, "aws-secret-value" * 3, "session-token-value" * 2
        ),
        region="us-west-1",
        executor=executor,
    )


def test_watchdog_containment_and_container_start_share_a_latched_effect_boundary() -> None:
    stack = _local_stack(RecordingExecutor())
    entered = threading.Event()
    release = threading.Event()
    order: list[str] = []

    def start_unlocked() -> None:
        entered.set()
        assert release.wait(timeout=2)
        order.append("start")

    def contain_unlocked() -> None:
        order.append("contain")

    stack._launch_retained_restored_catalog_unlocked = start_unlocked  # type: ignore[method-assign]
    stack._wait_postgres = lambda _name: None  # type: ignore[method-assign]
    stack._validate_restored_postgres = lambda _name: None  # type: ignore[method-assign]
    stack._contain_unlocked = contain_unlocked  # type: ignore[method-assign]
    starter = threading.Thread(target=stack.start_retained_restored_catalog)
    container = threading.Thread(target=stack.contain)
    starter.start()
    assert entered.wait(timeout=2)
    container.start()
    assert container.is_alive()
    release.set()
    starter.join(timeout=2)
    container.join(timeout=2)

    assert not starter.is_alive()
    assert not container.is_alive()
    assert order == ["start", "contain"]
    with pytest.raises(stage2c.Stage2CError, match="containment-latched"):
        stack.start_retained_restored_catalog()
    assert order == ["start", "contain"]


def test_retained_catalog_start_uses_restored_volume_without_pgbackrest_restore() -> None:
    class RetainedExecutor(RecordingExecutor):
        def run(self, command: Any, *, stdin: str | None = None) -> Any:
            completed = super().run(command, stdin=stdin)
            joined = " ".join(command)
            if "SELECT phase,value" in joined:
                return subprocess.CompletedProcess(command, 0, "A|101", "")
            if "SELECT pg_is_in_recovery" in joined:
                return subprocess.CompletedProcess(command, 0, "f", "")
            return completed

    executor = RetainedExecutor()
    stack = _local_stack(executor)
    stack._owned_inventory = lambda *, require_retained: {}  # type: ignore[method-assign]
    stack._owned_id = lambda name: f"owned-{name}"  # type: ignore[method-assign]
    stack._wait_postgres = lambda name: None  # type: ignore[method-assign]

    stack.start_retained_restored_catalog()

    commands = [" ".join(command) for command in executor.commands]
    joined = "\n".join(commands)
    assert stack.resources["restoredVolume"] in joined
    assert stack.resources["repositoryVolume"] in joined
    assert stack.resources["sourceVolume"] not in joined
    assert stack.resources["sourcePostgres"] not in joined
    assert f"{stack.resources['restoredPostgres']}-restore" not in joined
    assert "pgbackrest" not in joined
    assert "archive_mode=off" in joined
    assert any("SELECT phase,value" in command for command in commands)
    assert any("SELECT pg_is_in_recovery" in command for command in commands)


@pytest.mark.parametrize(
    ("rows", "promoted"),
    (("A|101\nB|202", "f"), ("A|101", "t")),
)
def test_retained_catalog_start_rejects_wrong_catalog_boundary(rows: str, promoted: str) -> None:
    class WrongBoundaryExecutor(RecordingExecutor):
        def run(self, command: Any, *, stdin: str | None = None) -> Any:
            completed = super().run(command, stdin=stdin)
            joined = " ".join(command)
            if "SELECT phase,value" in joined:
                return subprocess.CompletedProcess(command, 0, rows, "")
            if "SELECT pg_is_in_recovery" in joined:
                return subprocess.CompletedProcess(command, 0, promoted, "")
            return completed

    stack = _local_stack(WrongBoundaryExecutor())
    stack._owned_inventory = lambda *, require_retained: {}  # type: ignore[method-assign]
    stack._owned_id = lambda name: f"owned-{name}"  # type: ignore[method-assign]
    stack._wait_postgres = lambda name: None  # type: ignore[method-assign]

    with pytest.raises(stage2c.Stage2CError, match="does not bracket point A and B"):
        stack.start_retained_restored_catalog()


def test_point_a_backup_restarts_polaris_after_postgres_archive_restart() -> None:
    executor = RecordingExecutor()
    stack = _local_stack(executor)
    stack._owned_id = lambda name: f"owned-{name}"  # type: ignore[method-assign]
    stack._wait_postgres = lambda name: None  # type: ignore[method-assign]
    removed: list[str] = []
    started: list[str] = []

    def remove(name: str) -> None:
        removed.append(name)
        executor.commands.append(("test-event", "remove-polaris"))

    stack._remove_owned = remove  # type: ignore[method-assign]

    def start(name: str) -> str:
        started.append(name)
        executor.commands.append(("test-event", "start-polaris"))
        return "http://127.0.0.1:49153"

    stack._start_polaris = start  # type: ignore[method-assign]
    target = stack.backup_point_a()

    source_polaris = stack.resources["sourcePolaris"]
    assert removed == [source_polaris]
    assert started == [source_polaris]
    assert stack.source_url == "http://127.0.0.1:49153"
    assert target.name == f"stage2c_target_{RUN_ID}"
    commands = [" ".join(command) for command in executor.commands]
    assert any("archive_mode=on" in command for command in commands)
    backup_index = next(i for i, command in enumerate(commands) if "--type=full backup" in command)
    target_index = next(
        i for i, command in enumerate(commands) if "pg_create_restore_point" in command
    )
    check_indexes = [i for i, command in enumerate(commands) if "--stanza=polaris check" in command]
    remove_index = commands.index("test-event remove-polaris")
    start_index = commands.index("test-event start-polaris")
    assert backup_index < target_index < check_indexes[-1] < remove_index < start_index

    replacement_url = "http://127.0.0.1:49153"

    class RestartingStack:
        source_url = "http://127.0.0.1:49152"

        def backup_point_a(self) -> Any:
            self.source_url = replacement_url
            return target

    operations = object.__new__(stage2c.LiveJointRecoveryOperations)
    operations.stack = RestartingStack()
    operations.settings = _settings()
    operations.credentials = ir.RunCredentials(
        "db-secret-value", "client-id", "client-secret-value"
    )
    operations._source_gateway = ir.PolarisGateway(
        config=ir.RuntimeConfig.isolated(
            settings=operations.settings,
            polaris_url="http://127.0.0.1:49152",
            credentials=operations.credentials,
        )
    )
    assert operations.backup_point_a() == target
    assert operations._source_gateway is None
    assert operations._gateway().base_url == replacement_url


def _owned_postgres_container(stack: Any) -> tuple[str, dict[str, object]]:
    name = stack.resources["sourcePostgres"]
    container_id = "a" * 64
    network_id = "network-id"
    return container_id, {
        "Id": container_id,
        "Name": f"/{name}",
        "Image": stack.images["postgres"].image_id,
        "Path": "/bin/sh",
        "Args": ["-ceu", "while :; do sleep 3600; done"],
        "Config": {
            "Image": stack.images["postgres"].image_id,
            "Entrypoint": ["/bin/sh"],
            "Cmd": ["-ceu", "while :; do sleep 3600; done"],
            "Env": list(stack.images["postgres"].environment),
            "User": stack.images["postgres"].user,
            "WorkingDir": stack.images["postgres"].working_directory,
            "Labels": stack._label_map(),
        },
        "HostConfig": {
            "NetworkMode": stack.resources["network"],
            "Privileged": False,
            "AutoRemove": False,
            "ReadonlyRootfs": False,
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "Binds": None,
            "PortBindings": {},
        },
        "NetworkSettings": {
            "Networks": {
                stack.resources["network"]: {
                    "NetworkID": network_id,
                    "Aliases": ["postgres", name, container_id[:12]],
                }
            }
        },
        "Mounts": [
            {
                "Type": "volume",
                "Name": stack.resources["sourceVolume"],
                "Destination": "/var/lib/postgresql/data",
                "RW": True,
            },
            {
                "Type": "volume",
                "Name": stack.resources["repositoryVolume"],
                "Destination": "/repo",
                "RW": True,
            },
        ],
    }


def test_polaris_ownership_accepts_ephemeral_config_and_exact_runtime_loopback_port() -> None:
    stack = _local_stack(RecordingExecutor())
    name = stack.resources["sourcePolaris"]
    container_id = "b" * 64
    network_id = "network-id"
    container = {
        "Id": container_id,
        "Name": f"/{name}",
        "Image": stack.images["polaris"].image_id,
        "Path": "/bin/sh",
        "Args": ["-ceu", "while :; do sleep 3600; done"],
        "Config": {
            "Image": stack.images["polaris"].image_id,
            "Entrypoint": ["/bin/sh"],
            "Cmd": ["-ceu", "while :; do sleep 3600; done"],
            "Env": list(stack.images["polaris"].environment),
            "User": stack.images["polaris"].user,
            "WorkingDir": stack.images["polaris"].working_directory,
            "Labels": {**stack._label_map(), "vendor.image-label": "retained"},
        },
        "HostConfig": {
            "NetworkMode": stack.resources["network"],
            "Privileged": False,
            "AutoRemove": False,
            "ReadonlyRootfs": False,
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "Binds": None,
            "PortBindings": {"8181/tcp": [{"HostIp": "127.0.0.1", "HostPort": ""}]},
        },
        "NetworkSettings": {
            "Networks": {
                stack.resources["network"]: {
                    "NetworkID": network_id,
                    "Aliases": [name, container_id[:12]],
                }
            },
            "Ports": {
                "8080/tcp": None,
                "8181/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49152"}],
                "8182/tcp": None,
            },
        },
        "Mounts": [],
    }

    stack._validate_container(name, container, network_id=network_id, attachment_id=container_id)
    container["NetworkSettings"]["Ports"]["8181/tcp"][0]["HostIp"] = "0.0.0.0"
    with pytest.raises(stage2c.Stage2CError, match="runtime API port"):
        stack._validate_container(
            name, container, network_id=network_id, attachment_id=container_id
        )


def test_restore_helper_ownership_accepts_only_docker_none_network_shape() -> None:
    stack = _local_stack(RecordingExecutor())
    name = f"{stack.resources['restoredPostgres']}-restore"
    container_id = "c" * 64
    container = {
        "Id": container_id,
        "Name": f"/{name}",
        "Image": stack.images["postgres"].image_id,
        "Path": "/bin/sh",
        "Args": ["-ceu", "while :; do sleep 3600; done"],
        "Config": {
            "Image": stack.images["postgres"].image_id,
            "Entrypoint": ["/bin/sh"],
            "Cmd": ["-ceu", "while :; do sleep 3600; done"],
            "Env": list(stack.images["postgres"].environment),
            "User": stack.images["postgres"].user,
            "WorkingDir": stack.images["postgres"].working_directory,
            "Labels": stack._label_map(),
        },
        "HostConfig": {
            "NetworkMode": "none",
            "Privileged": False,
            "AutoRemove": False,
            "ReadonlyRootfs": False,
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "Binds": None,
            "PortBindings": {},
        },
        "NetworkSettings": {
            "Networks": {
                "none": {
                    "NetworkID": "none-network-id",
                    "Aliases": None,
                    "DNSNames": None,
                    "Gateway": "",
                    "IPAddress": "",
                    "IPv6Gateway": "",
                    "GlobalIPv6Address": "",
                    "MacAddress": "",
                }
            },
            "Ports": {"5432/tcp": None},
        },
        "Mounts": [
            {
                "Type": "volume",
                "Name": stack.resources["restoredVolume"],
                "Destination": "/var/lib/postgresql/data",
                "RW": True,
            },
            {
                "Type": "volume",
                "Name": stack.resources["repositoryVolume"],
                "Destination": "/repo",
                "RW": True,
            },
        ],
    }

    stack._validate_container(name, container, network_id="campaign-network-id", attachment_id=None)
    container["NetworkSettings"]["Networks"]["none"]["IPAddress"] = "192.0.2.10"
    with pytest.raises(stage2c.Stage2CError, match="unexpected network attachment"):
        stack._validate_container(
            name, container, network_id="campaign-network-id", attachment_id=None
        )


@pytest.mark.parametrize("mutation", ("label", "image", "mount", "alias", "port"))
def test_container_ownership_rejects_any_identity_drift(mutation: str) -> None:
    stack = _local_stack(RecordingExecutor())
    container_id, container = _owned_postgres_container(stack)
    name = stack.resources["sourcePostgres"]
    stack._validate_container(name, container, network_id="network-id", attachment_id=container_id)
    changed = json.loads(json.dumps(container))
    if mutation == "label":
        changed["Config"]["Labels"]["com.databox.run"] = "other"
    elif mutation == "image":
        changed["Image"] = "sha256:" + "9" * 64
    elif mutation == "mount":
        changed["Mounts"][0]["Name"] = "foreign-volume"
    elif mutation == "alias":
        changed["NetworkSettings"]["Networks"][stack.resources["network"]]["Aliases"].append(
            "foreign-alias"
        )
    else:
        changed["HostConfig"]["PortBindings"] = {"9999/tcp": []}
    with pytest.raises(stage2c.Stage2CError):
        stack._validate_container(
            name, changed, network_id="network-id", attachment_id=container_id
        )


def test_owned_inventory_rejects_unknown_network_attachment_and_volume_consumer() -> None:
    stack = _local_stack(RecordingExecutor())
    container_id, container = _owned_postgres_container(stack)
    name = stack.resources["sourcePostgres"]
    labels = stack._label_map()
    network = {
        "Id": "network-id",
        "Name": stack.resources["network"],
        "Labels": labels,
        "Driver": "bridge",
        "Scope": "local",
        "Internal": False,
        "Attachable": False,
        "Ingress": False,
        "Containers": {
            container_id: {"Name": name},
            "b" * 64: {"Name": "foreign-container"},
        },
    }
    volumes = {
        key: {
            "Name": stack.resources[key],
            "Labels": labels,
            "Driver": "local",
            "Scope": "local",
        }
        for key in ("sourceVolume", "restoredVolume", "repositoryVolume")
    }
    present = {
        ("network", stack.resources["network"]): network,
        ("volume", stack.resources["sourceVolume"]): volumes["sourceVolume"],
        ("volume", stack.resources["restoredVolume"]): volumes["restoredVolume"],
        ("volume", stack.resources["repositoryVolume"]): volumes["repositoryVolume"],
        ("container", name): container,
    }
    stack._listed_names = (  # type: ignore[method-assign]
        lambda resource, item: (item,) if (resource, item) in present else ()
    )
    stack._inspect = lambda resource, item: present[(resource, item)]  # type: ignore[method-assign]
    stack._volume_consumers = lambda _volume: {}  # type: ignore[method-assign]
    with pytest.raises(stage2c.Stage2CError, match="unknown attachments"):
        stack._owned_inventory(require_retained=True)

    network["Containers"].pop("b" * 64)
    stack._volume_consumers = (  # type: ignore[method-assign]
        lambda volume: (
            {name: container_id[:12], "foreign-container": "b" * 12}
            if volume == stack.resources["sourceVolume"]
            else (
                {name: container_id[:12]} if volume == stack.resources["repositoryVolume"] else {}
            )
        )
    )
    with pytest.raises(stage2c.Stage2CError, match="unknown consumers"):
        stack._owned_inventory(require_retained=True)


def test_owned_removal_uses_verified_container_id_and_confirms_name_absent() -> None:
    executor = RecordingExecutor()
    stack = _local_stack(executor)
    name = stack.resources["sourcePostgres"]
    container_id, container = _owned_postgres_container(stack)
    stack._owned_inventory = (  # type: ignore[method-assign]
        lambda *, require_retained: {name: (container_id, container)}
    )
    stack._listed_names = lambda _resource, _name: ()  # type: ignore[method-assign]

    stack._remove_owned(name)

    assert ("docker", "rm", "--force", container_id) in executor.commands
    assert ("docker", "rm", "--force", name) not in executor.commands


def test_bounded_subprocess_timeout_is_mandatory(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {}

    def fake_run(command: Any, **kwargs: Any) -> Any:
        observed.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(stage2c.subprocess, "run", fake_run)
    stage2c._bounded_run(("example",), text=True, capture_output=True, check=False)
    assert observed["timeout"] == stage2c._COMMAND_TIMEOUT_SECONDS


def test_all_live_aws_cli_adapters_receive_the_bounded_runner() -> None:
    source = inspect.getsource(stage2c._verify_live_aws_bounded)
    assert source.count("runner=_bounded_run") == 3
    assert "ir.AwsCliVersionStore" in source


def test_spawned_docker_exec_has_watchdog_and_bounded_termination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timer_state: dict[str, object] = {}

    class Timer:
        daemon = False

        def __init__(self, interval: float, callback: Any) -> None:
            timer_state["interval"] = interval
            timer_state["callback"] = callback

        def start(self) -> None:
            timer_state["started"] = True

        def cancel(self) -> None:
            timer_state["cancelled"] = True

    class Process:
        running = True
        waits: list[float] = []

        def poll(self) -> int | None:
            return None if self.running else 0

        def terminate(self) -> None:
            timer_state["terminated"] = True

        def kill(self) -> None:
            self.running = False
            timer_state["killed"] = True

        def wait(self, *, timeout: float) -> int:
            self.waits.append(timeout)
            if len(self.waits) == 1:
                raise subprocess.TimeoutExpired("docker exec", timeout)
            return 0

    monkeypatch.setattr(stage2c.threading, "Timer", Timer)
    process = Process()
    bounded = stage2c.BoundedProcess(process)
    bounded.close()

    assert timer_state["interval"] == stage2c._SERVICE_PROCESS_TIMEOUT_SECONDS
    assert timer_state["started"] is True
    assert timer_state["cancelled"] is True
    assert timer_state["terminated"] is True
    assert timer_state["killed"] is True
    assert process.waits == [
        stage2c._SERVICE_STOP_TIMEOUT_SECONDS,
        stage2c._SERVICE_STOP_TIMEOUT_SECONDS,
    ]


def test_secret_values_use_stdin_not_commands_or_evidence(tmp_path: Path) -> None:
    executor = RecordingExecutor()
    credentials = ir.RunCredentials("db-secret-value", "client-id", "client-secret-value")
    aws = ir.AwsCredentials("A" * 20, "aws-secret-value" * 3, "session-token-value" * 2)
    scope = stage2c._scope(RUN_ID)
    resources = stage2c._resources(scope)
    stack = stage2c.LocalJointStack(
        scope=scope,
        resources=resources,
        images={name: _pin(reference) for name, reference in stage2c._IMAGE_REFERENCES.items()},
        campaign_sha256="a" * 64,
        credentials=credentials,
        aws_credentials=aws,
        region="us-west-1",
        executor=executor,
    )
    stack._owned_inventory = lambda *, require_retained: {}  # type: ignore[method-assign]
    stack._owned_id = lambda name: f"owned-{name}"  # type: ignore[method-assign]
    stack._remove_owned = lambda name: None  # type: ignore[method-assign]

    stack.create()

    commands = "\n".join(" ".join(command) for command in executor.commands)
    for secret in (
        credentials.postgres_password,
        credentials.polaris_client_secret,
        aws.secret_access_key,
        aws.session_token,
    ):
        assert secret not in commands
    assert credentials.postgres_password in "\n".join(value or "" for value in executor.inputs)
    assert _pin(stage2c._POSTGRES_IMAGE).image_id in commands
    assert stage2c._POSTGRES_IMAGE not in commands
    assert stage2c._ADMIN_IMAGE not in commands
    assert stage2c._POLARIS_IMAGE not in commands
    assert not list(tmp_path.rglob("*"))


def test_static_contract_excludes_purge_cloud_backup_active_and_cleanup_operations() -> None:
    source = SCRIPT.read_text()
    forbidden_runtime_tokens = (
        "DeleteObjectVersion",
        '"--version-id"',
        "databox-polaris-catalog-backup",
        "catalog-backup-readiness",
        "docker volume rm",
        "docker network rm",
        "databox-iceberg-postgres-1",
        "databox-iceberg-polaris-1",
    )
    for token in forbidden_runtime_tokens:
        assert token not in source
    assert "repo1-type=posix" in source
    assert "--type=name" in source
    assert "--target-action=promote" in source
    assert "_MAX_KEYS = 64" in source
    assert "_MAX_BYTES = 32 * 1024 * 1024" in source


def test_taskfile_forwards_stage2c_prepare_and_execute_arguments() -> None:
    taskfile = (ROOT / "Taskfile.yaml").read_text()
    assert "catalog:recovery-stage2c:" in taskfile
    assert "scripts/platform/catalog_warehouse_recovery_stage2c.py {{.CLI_ARGS}}" in taskfile
