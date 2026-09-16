import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pyarrow as pa
import pytest
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import BadRequestError, ForbiddenError
from pyiceberg.schema import Schema
from pyiceberg.types import LongType, NestedField, StringType

ROOT = Path(__file__).parents[2]
GITIGNORE = ROOT / ".gitignore"
RUNBOOK = ROOT / "docs/runbook.md"
TASKFILE = ROOT / "Taskfile.yaml"


def _load():
    spec = spec_from_file_location(
        "iceberg_recovery_drill",
        ROOT / "scripts/platform/iceberg_recovery_drill.py",
    )
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


drill = _load()


def test_recovery_settings_uses_drill_only_storage_role_without_a_role_pair(
    monkeypatch,
) -> None:
    values = {
        "DATABOX_AWS_S3_BUCKET": "private-bucket",
        "DATABOX_AWS_REGION": "us-west-1",
        "DATABOX_AWS_ROLE_ARN": "arn:aws:iam::123456789012:role/production-storage-role",
        "DATABOX_RECOVERY_STORAGE_ROLE_ARN": (
            "arn:aws:iam::123456789012:role/recovery-storage-role"
        ),
        "DATABOX_RECOVERY_PROFILE": "operator",
        "DATABOX_RECOVERY_IDENTITY_SHA256": "a" * 64,
        "DATABOX_RECOVERY_RUN_SECRET": "synthetic-run-secret-placeholder",  # secret-scan: allow
    }
    monkeypatch.setattr(drill, "dotenv_values", lambda path: values)
    monkeypatch.setattr(drill.os, "environ", {})

    assert drill.RecoverySettings.load() == drill.RecoverySettings(
        bucket="private-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/recovery-storage-role",
        profile="operator",
        identity_sha256="a" * 64,
        run_secret="synthetic-run-secret-placeholder",  # secret-scan: allow
    )


def test_recovery_settings_never_falls_back_to_production_storage_role(
    monkeypatch,
) -> None:
    values = {
        "DATABOX_AWS_S3_BUCKET": "private-bucket",
        "DATABOX_AWS_REGION": "us-west-1",
        "DATABOX_AWS_ROLE_ARN": "arn:aws:iam::123456789012:role/production-storage-role",
        "DATABOX_RECOVERY_PROFILE": "operator",
        "DATABOX_RECOVERY_IDENTITY_SHA256": "a" * 64,
        "DATABOX_RECOVERY_RUN_SECRET": "synthetic-run-secret-placeholder",  # secret-scan: allow
    }
    monkeypatch.setattr(drill, "dotenv_values", lambda path: values)
    monkeypatch.setattr(drill.os, "environ", {})

    with pytest.raises(drill.DrillError, match="required private recovery settings"):
        drill.RecoverySettings.load()


def test_prepare_generates_run_scope_and_atomic_private_manifest(tmp_path: Path) -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    observed = {}

    class Operations:
        def prepare(self, scope, rows):
            observed["scope"] = scope
            observed["rows"] = tuple(rows)
            prefix = scope.prefix
            return drill.TableCapture(
                bucket="private-bucket",
                table_uuid="table-uuid",
                metadata_location=f"s3://private-bucket/{prefix}/metadata/root.json",
                snapshot_id=42,
                schema_sha256="1" * 64,
                row_count=3,
                rows_sha256="2" * 64,
                nodes=(
                    drill.GraphNode(
                        key=f"{prefix}/metadata/root.json",
                        kind="metadata",
                        source_version_id="private-version-root",
                        etag='"root-etag"',
                        size=128,
                        sha256="3" * 64,
                        depth=0,
                    ),
                    drill.GraphNode(
                        key=f"{prefix}/data/rows.parquet",
                        kind="data",
                        source_version_id="private-version-data",
                        etag='"data-etag"',
                        size=256,
                        sha256="4" * 64,
                        depth=3,
                    ),
                ),
            )

    runtime_binding = drill.RuntimeBinding(
        source_revision="a" * 40,
        script_sha256="b" * 64,
        python_version="3.12.7",
        pyiceberg_version="0.11.1",
        pyarrow_version="18.1.0",
        configuration_sha256="c" * 64,
    )
    result = drill.prepare_drill(
        operations=Operations(),
        evidence_root=tmp_path / ".recovery" / "iceberg",
        token_factory=lambda: token,
        runtime_binding=runtime_binding,
    )

    scope = observed["scope"]
    assert scope == drill.DrillScope(
        run_id=token,
        prefix=f"integration/recovery/{token}/stage1/warehouse",
        catalog=f"recovery_{token}",
        namespace=f"drill_{token}",
        table=f"events_{token}",
    )
    assert observed["rows"] == (
        {"event_id": 1, "generation": "point-a", "value": 10},
        {"event_id": 2, "generation": "point-a", "value": 20},
        {"event_id": 3, "generation": "point-a", "value": 30},
    )

    manifest_path = Path(result["manifest"])
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    assert result == {
        "status": "prepared",
        "runId": token,
        "manifest": str(manifest_path),
        "manifestSha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "logicalGraphSha256": manifest["graph"]["logicalSha256"],
        "nodeCount": 2,
        "rowCount": 3,
    }
    assert manifest["schemaVersion"] == 2
    assert manifest["runtime"] == runtime_binding.as_manifest()
    parsed = drill._manifest_contract(manifest_path, result["manifestSha256"])
    assert parsed[4] == runtime_binding
    assert manifest["scope"] == {
        "runId": token,
        "prefix": f"integration/recovery/{token}/stage1/warehouse",
        "catalog": f"recovery_{token}",
        "namespace": f"drill_{token}",
        "table": f"events_{token}",
    }
    assert manifest["table"]["bucket"] == "private-bucket"
    assert manifest["table"]["metadataLocation"].endswith("/metadata/root.json")
    assert manifest["table"]["snapshotId"] == 42
    assert [node["kind"] for node in manifest["graph"]["nodes"]] == ["metadata", "data"]
    assert manifest["graph"]["nodes"][0]["sourceVersionId"] == "private-version-root"
    assert stat.S_IMODE(manifest_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(manifest_path.stat().st_mode) == 0o600
    assert list(manifest_path.parent.glob("*.tmp")) == []
    rendered_result = json.dumps(result)
    assert "private-bucket" not in rendered_result
    assert "private-version" not in rendered_result


def test_prepare_seed_plan_is_mutation_free_private_and_contains_no_run_secret(
    tmp_path: Path,
) -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    inspected = []
    settings = drill.RecoverySettings(
        bucket="private-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/storage-role",
        profile="operator",
        identity_sha256="a" * 64,
        run_secret="synthetic-run-secret-placeholder",  # secret-scan: allow
    )

    def inspect_image(reference):
        inspected.append(reference)
        return drill.ImagePin(
            reference=reference,
            image_id="sha256:" + hashlib.sha256(reference.encode()).hexdigest(),
            entrypoint=("/entrypoint",),
            command=("serve",),
        )

    result = drill.prepare_seed_plan(
        settings=settings,
        evidence_root=tmp_path / ".recovery" / "iceberg",
        token_factory=lambda: token,
        clock=lambda: drill.datetime(2026, 9, 14, 12, 0, tzinfo=drill.UTC),
        image_inspector=inspect_image,
        docker_fingerprint=lambda: "d" * 64,
    )

    assert inspected == [
        "postgres:17.6-bookworm",
        "apache/polaris-admin-tool:1.7.0",
        "apache/polaris:1.7.0",
    ]
    plan_path = Path(result["plan"])
    payload = plan_path.read_bytes()
    plan = json.loads(payload)
    assert result == {
        "status": "planned",
        "planType": "seed-a",
        "runId": token,
        "plan": str(plan_path),
        "planSha256": hashlib.sha256(payload).hexdigest(),
    }
    assert plan["schemaVersion"] == 2
    assert plan["planType"] == "seed-a"
    assert plan["identities"] == {
        "profile": "operator",
        "identitySha256": "a" * 64,
        "storageRoleArn": "arn:aws:iam::123456789012:role/storage-role",
        "separatePrincipalProof": False,
    }
    parsed = drill._seed_plan_contract(
        plan_path,
        result["planSha256"],
        clock=lambda: drill.datetime(2026, 9, 14, 12, 1, tzinfo=drill.UTC),
    )
    assert parsed[1] == drill._scope(token)
    assert parsed[4] == result["planSha256"]
    drill._settings_match_seed_plan(settings, parsed[0], parsed[1])
    assert plan["scope"]["prefix"] == f"integration/recovery/{token}/stage1/warehouse"
    assert plan["stack"]["resources"]["postgresVolume"].endswith("-pgdata")
    assert plan["contract"]["operations"][:3] == [
        "operator-canary-put-ordinary-delete",
        "operator-canary-exact-version-promotion",
        "validate-canary-only-prefix",
    ]
    assert plan["contract"]["maxStage1Objects"] == 64
    assert plan["contract"]["maxGraphObjects"] == 63
    assert plan["contract"]["retainedCanaryObjects"] == 1
    assert plan["contract"]["prohibited"] == [
        "active-polaris",
        "canonical-catalog-or-warehouse",
        "delete-object-version",
        "delete-marker-removal",
        "bucket-control-change",
        "network-or-volume-removal",
        "automatic-cleanup",
    ]
    assert settings.run_secret not in payload.decode()
    assert stat.S_IMODE(plan_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(plan_path.stat().st_mode) == 0o600


def test_atomic_private_write_never_replaces_a_racing_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tmp_path.chmod(0o700)
    receipt = tmp_path / "seed-a.plan.json"
    winner = b"concurrently-published-receipt"
    real_link = drill.os.link

    def racing_link(source, destination, *, follow_symlinks):
        Path(destination).write_bytes(winner)
        Path(destination).chmod(0o600)
        return real_link(source, destination, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(drill.os, "link", racing_link)

    with pytest.raises(drill.DrillError, match="already exists"):
        drill._atomic_private_write(receipt, b"losing-receipt")

    assert receipt.read_bytes() == winner
    assert stat.S_IMODE(receipt.stat().st_mode) == 0o600
    assert not tuple(tmp_path.glob("*.tmp"))


def test_execute_seed_plan_closes_isolated_stack_before_recovery_plan(
    tmp_path: Path,
) -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    evidence_root = tmp_path / ".recovery" / "iceberg"
    settings = drill.RecoverySettings(
        bucket="private-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/storage-role",
        profile="operator",
        identity_sha256="a" * 64,
        run_secret="synthetic-run-secret-placeholder",  # secret-scan: allow
    )

    def inspect_image(reference):
        return drill.ImagePin(
            reference=reference,
            image_id="sha256:" + hashlib.sha256(reference.encode()).hexdigest(),
            entrypoint=("/entrypoint",),
            command=("serve",),
        )

    planned = drill.prepare_seed_plan(
        settings=settings,
        evidence_root=evidence_root,
        token_factory=lambda: token,
        clock=lambda: drill.datetime(2026, 9, 14, 12, 0, tzinfo=drill.UTC),
        image_inspector=inspect_image,
        docker_fingerprint=lambda: "d" * 64,
    )
    calls = []

    class RecoveryStore:
        def verify_empty_prefix(self):
            calls.append("empty-prefix")

        def verify_only_key(self, key):
            assert key == f"{scope.prefix}/capability-canary.bin"
            calls.append("canary-only-prefix")

        def current_state(self, candidate):
            calls.append("canary-current")
            return drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id="restored-canary",
                size=candidate.size,
                sha256=candidate.sha256,
            )

        def exact_source_state(self, candidate):
            calls.append("canary-source")
            return drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id=candidate.source_version_id,
                size=candidate.size,
                sha256=candidate.sha256,
            )

        def prefix_keys(self):
            calls.append("complete-prefix")
            return frozenset(
                {
                    f"{scope.prefix}/capability-canary.bin",
                    f"{scope.prefix}/metadata/root.json",
                }
            )

    aws = drill.VerifiedAwsContext(
        environment={"AWS_PROFILE": "operator"},
        identity=drill.CallerIdentity(
            "123456789012",
            "arn:aws:sts::123456789012:assumed-role/storage-role/operator-session",
            "a" * 64,
        ),
        credentials=drill.AwsCredentials(
            "A" * 20,
            "s" * 40,
            "temporary-session-token",
        ),
        store=RecoveryStore(),
    )

    class Stack:
        def __init__(self, **kwargs):
            calls.append(("stack", kwargs["scope"].run_id))

        def create_seed_resources(self):
            calls.append("create-resources")

        def start(self, credentials, exported, *, bootstrap, region):
            assert credentials.polaris_client_id == f"recovery-{token}"
            assert exported.session_token == "temporary-session-token"
            assert bootstrap is True
            assert region == "us-west-1"
            calls.append("start-stack")
            return "http://127.0.0.1:32123"

        def close(self):
            assert not (evidence_root / token / "manifest.json").exists()
            calls.append("close-stack")

        def retained_resources_sha256(self):
            calls.append("retained-fingerprint")
            return "8" * 64

    scope = drill._scope(token)
    canary_node = drill.GraphNode(
        key=f"{scope.prefix}/capability-canary.bin",
        kind="capability-canary",
        source_version_id="source-canary",
        etag='"canary"',
        size=7,
        sha256=hashlib.sha256(b"canary\n").hexdigest(),
        depth=0,
    )
    node = drill.GraphNode(
        key=f"{scope.prefix}/metadata/root.json",
        kind="metadata",
        source_version_id="source-root",
        etag='"root"',
        size=10,
        sha256="c" * 64,
        depth=0,
    )
    capture = drill.TableCapture(
        bucket="private-bucket",
        table_uuid="table-uuid",
        metadata_location=f"s3://private-bucket/{node.key}",
        snapshot_id=42,
        schema_sha256="e" * 64,
        row_count=3,
        rows_sha256="f" * 64,
        nodes=(node,),
    )

    class Operations:
        gateway = None

        def prepare(self, requested_scope, rows, *, capability_canary=None):
            assert requested_scope == scope
            assert tuple(rows) == drill._DETERMINISTIC_ROWS
            assert capability_canary == canary_node
            calls.append("seed-table")
            return capture

    class Gateway:
        def catalog_fingerprint(self, requested_scope):
            assert requested_scope == scope
            calls.append("catalog-fingerprint")
            return "9" * 64

    result = drill.execute_seed_plan(
        settings=settings,
        plan_path=Path(planned["plan"]),
        expected_sha256=planned["planSha256"],
        clock=lambda: drill.datetime(2026, 9, 14, 12, 1, tzinfo=drill.UTC),
        image_inspector=inspect_image,
        docker_fingerprint=lambda: "d" * 64,
        live_aws_factory=lambda **kwargs: aws,
        capability_checker=lambda **kwargs: calls.append("capability-canary") or canary_node,
        stack_factory=Stack,
        operations_factory=lambda **kwargs: Operations(),
        credential_exporter=lambda **kwargs: drill.AwsCredentials(
            "ABCDEFGHIJKLMNOP",
            "s" * 40,
            "temporary-session-token",
        ),
        gateway_waiter=lambda config: Gateway(),
    )

    assert calls == [
        "empty-prefix",
        "capability-canary",
        "canary-only-prefix",
        "canary-current",
        "canary-source",
        ("stack", token),
        "create-resources",
        "start-stack",
        "seed-table",
        "complete-prefix",
        "catalog-fingerprint",
        "close-stack",
        "retained-fingerprint",
    ]
    recovery_plan = json.loads(Path(result["plan"]).read_text())
    assert result["status"] == "recovery-planned"
    assert recovery_plan["schemaVersion"] == 4
    assert recovery_plan["planType"] == "recovery-a"
    assert recovery_plan["parentSeedPlanSha256"] == planned["planSha256"]
    assert recovery_plan["contract"] == drill._recovery_contract()

    recovery_calls = []

    class RecoveryStack:
        def __init__(self, **kwargs):
            assert kwargs["seed_plan_sha256"] == planned["planSha256"]
            assert kwargs["execution_plan_sha256"] == result["planSha256"]

        def use_retained_resources(self, expected_sha256):
            assert expected_sha256 == "8" * 64
            recovery_calls.append("use-retained")

        def start(self, credentials, exported, *, bootstrap, region):
            del credentials, exported
            assert bootstrap is False
            assert region == "us-west-1"
            recovery_calls.append("start-recovery-stack")
            return "http://127.0.0.1:32124"

        def close(self):
            recovery_calls.append("close-recovery-stack")

    class RecoveryGateway:
        def catalog_fingerprint(self, requested_scope):
            assert requested_scope == scope
            recovery_calls.append("verify-catalog-fingerprint")
            return "9" * 64

    class RecoveryOperations:
        gateway = None

        def __init__(self):
            resumed = (evidence_root / token / "damage-started.json").exists()
            self.state = drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id="restored-root" if resumed else node.source_version_id,
                size=node.size,
                sha256=node.sha256,
            )

        def current_state(self, candidate):
            assert candidate == node
            return self.state

        def _verify_capability_canary(self):
            assert not (evidence_root / token / "damage-started.json").exists()
            recovery_calls.append("capability-canary")

        def delete_current(self, candidate):
            assert candidate == node
            recovery_calls.append("delete")
            self.state = drill.ObjectState(
                exists=False,
                delete_marker=True,
                version_id="marker-root",
            )
            return drill.DeleteResult(True, "marker-root")

        def assert_table_unreadable(self, approved_manifest):
            assert approved_manifest["planType"] == "recovery-a"
            recovery_calls.append("break-proof")

        def restore(self, candidate):
            assert candidate == node
            recovery_calls.append("restore")
            self.state = drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id="restored-root",
                size=node.size,
                sha256=node.sha256,
            )
            return self.state

        def validate(self, approved_manifest):
            recovery_calls.append("validate")
            table = approved_manifest["table"]
            graph = approved_manifest["graph"]
            return drill.ValidationResult(
                table_uuid=table["tableUuid"],
                metadata_location=table["metadataLocation"],
                snapshot_id=table["snapshotId"],
                logical_graph_sha256=graph["logicalSha256"],
                row_count=table["rowCount"],
                rows_sha256=table["rowsSha256"],
            )

    def recovery_live_aws(**kwargs):
        del kwargs
        recovery_calls.append("aws-preflight")
        return aws

    recovered = drill.execute_recovery_plan(
        settings=settings,
        plan_path=Path(result["plan"]),
        expected_sha256=result["planSha256"],
        clock=lambda: drill.datetime(2026, 9, 14, 12, 2, tzinfo=drill.UTC),
        image_inspector=inspect_image,
        docker_fingerprint=lambda: "d" * 64,
        live_aws_factory=recovery_live_aws,
        stack_factory=RecoveryStack,
        operations_factory=lambda **kwargs: RecoveryOperations(),
        credential_exporter=lambda **kwargs: drill.AwsCredentials(
            "ABCDEFGHIJKLMNOP",
            "s" * 40,
            "temporary-session-token",
        ),
        gateway_waiter=lambda config: RecoveryGateway(),
    )

    assert recovered["status"] == "pass"
    assert recovery_calls == [
        "use-retained",
        "aws-preflight",
        "start-recovery-stack",
        "verify-catalog-fingerprint",
        "validate",
        "capability-canary",
        "delete",
        "break-proof",
        "restore",
        "validate",
        "close-recovery-stack",
    ]

    resumed = drill.execute_recovery_plan(
        settings=settings,
        plan_path=Path(result["plan"]),
        expected_sha256=result["planSha256"],
        clock=lambda: drill.datetime(2026, 9, 14, 20, 0, tzinfo=drill.UTC),
        image_inspector=inspect_image,
        docker_fingerprint=lambda: "d" * 64,
        live_aws_factory=recovery_live_aws,
        stack_factory=RecoveryStack,
        operations_factory=lambda **kwargs: RecoveryOperations(),
        credential_exporter=lambda **kwargs: drill.AwsCredentials(
            "ABCDEFGHIJKLMNOP",
            "s" * 40,
            "temporary-session-token",
        ),
        gateway_waiter=lambda config: RecoveryGateway(),
    )
    assert resumed["status"] == "recovered-after-interruption"
    assert recovery_calls.count("delete") == 1
    assert recovery_calls.count("capability-canary") == 1
    assert recovery_calls[-6:] == [
        "use-retained",
        "aws-preflight",
        "start-recovery-stack",
        "verify-catalog-fingerprint",
        "validate",
        "close-recovery-stack",
    ]

    (evidence_root / token / "damage-started.json").unlink()
    aws_preflight_count = recovery_calls.count("aws-preflight")
    with pytest.raises(drill.DrillError, match="damage marker is unreadable"):
        drill.execute_recovery_plan(
            settings=settings,
            plan_path=Path(result["plan"]),
            expected_sha256=result["planSha256"],
            clock=lambda: drill.datetime(2026, 9, 14, 20, 0, tzinfo=drill.UTC),
            image_inspector=inspect_image,
            docker_fingerprint=lambda: "d" * 64,
            live_aws_factory=recovery_live_aws,
            stack_factory=RecoveryStack,
            operations_factory=lambda **kwargs: RecoveryOperations(),
        )
    assert recovery_calls[-1] == "use-retained"
    assert recovery_calls.count("aws-preflight") == aws_preflight_count


def test_isolated_stack_uses_resource_specific_list_format_fields() -> None:
    scope = drill._scope("0123456789abcdef")
    resources = drill._stack_resources(scope)
    commands = []

    def runner(command, **kwargs):
        del kwargs
        commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    images = {
        name: drill.ImagePin(
            reference=name,
            image_id="sha256:" + character * 64,
            entrypoint=("/entrypoint",),
            command=("serve",),
        )
        for name, character in (
            ("postgres", "1"),
            ("polarisAdmin", "2"),
            ("polaris", "3"),
        )
    }
    stack = drill.IsolatedStage1Stack(
        scope=scope,
        resources=resources,
        images=images,
        seed_plan_sha256="a" * 64,
        execution_plan_sha256="b" * 64,
        runner=runner,
    )

    assert stack._listed_names("container", resources["postgresContainer"]) == ()
    assert commands[-1][-1] == "{{.Names}}"
    assert stack._listed_names("network", resources["network"]) == ()
    assert commands[-1][-1] == "{{.Name}}"
    assert stack._listed_names("volume", resources["postgresVolume"]) == ()
    assert commands[-1][-1] == "{{.Name}}"


def test_isolated_stack_reports_sanitized_start_stage(monkeypatch) -> None:
    scope = drill._scope("0123456789abcdef")
    resources = drill._stack_resources(scope)

    def runner(command, **kwargs):
        del kwargs
        returncode = int(
            command[:3] == ["docker", "exec", "--interactive"]
            and resources["bootstrapContainer"] in command
        )
        return subprocess.CompletedProcess(command, returncode, "", "")

    images = {
        name: drill.ImagePin(
            reference=name,
            image_id="sha256:" + character * 64,
            entrypoint=("/entrypoint",),
            command=("serve",),
        )
        for name, character in (
            ("postgres", "1"),
            ("polarisAdmin", "2"),
            ("polaris", "3"),
        )
    }
    stack = drill.IsolatedStage1Stack(
        scope=scope,
        resources=resources,
        images=images,
        seed_plan_sha256="a" * 64,
        execution_plan_sha256="b" * 64,
        runner=runner,
    )
    monkeypatch.setattr(stack, "_spawn", lambda command, payload: None)
    monkeypatch.setattr(stack, "_wait_postgres", lambda: None)

    with pytest.raises(drill.SeedStageError) as captured:
        stack.start(
            drill.RunCredentials("database-password", "client-id", "client-secret"),
            drill.AwsCredentials("A" * 16, "s" * 32, "t" * 16),
            bootstrap=True,
            region="us-west-1",
        )

    assert captured.value.stage == "polaris-bootstrap"


def test_isolated_stack_commands_are_generated_labeled_and_secret_free() -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    scope = drill._scope(token)
    commands = []
    private_inputs = []

    def runner(command, **kwargs):
        del kwargs
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    class Stdin:
        def write(self, value):
            private_inputs.append(value)

        def close(self):
            private_inputs.append("closed")

    class Process:
        stdin = Stdin()

    def popen(command, **kwargs):
        del kwargs
        commands.append(command)
        return Process()

    images = {
        name: drill.ImagePin(
            reference=name,
            image_id="sha256:" + character * 64,
            entrypoint=("/entrypoint",),
            command=("serve",),
        )
        for name, character in (
            ("postgres", "1"),
            ("polarisAdmin", "2"),
            ("polaris", "3"),
        )
    }
    stack = drill.IsolatedStage1Stack(
        scope=scope,
        resources=drill._stack_resources(scope),
        images=images,
        seed_plan_sha256="a" * 64,
        execution_plan_sha256="b" * 64,
        runner=runner,
        popen_factory=popen,
    )

    stack._create_sleeper(
        name=drill._stack_resources(scope)["polarisContainer"],
        image=images["polaris"],
        phase="recovery",
        network_alias="polaris",
        publish_api=True,
    )
    stack._spawn(
        ("docker", "exec", "--interactive", "generated", "/bin/sh"),
        "private-secret-value\n",
    )

    rendered_commands = json.dumps(commands)
    assert "private-secret-value" not in rendered_commands
    assert "databox-iceberg" not in rendered_commands
    assert f"com.databox.run={token}" in rendered_commands
    assert "com.databox.phase=recovery" in rendered_commands
    assert "127.0.0.1::8181" in rendered_commands
    assert private_inputs == ["private-secret-value\n", "closed"]


def _recovery_stack_fixture(variant: str = "exact"):
    token = "0123456789abcdef"  # secret-scan: allow
    scope = drill._scope(token)
    resources = drill._stack_resources(scope)
    images = {
        "postgres": drill.ImagePin(
            "postgres",
            "sha256:" + "1" * 64,
            ("/entrypoint",),
            ("postgres",),
            ("PATH=/usr/bin",),
        ),
        "polarisAdmin": drill.ImagePin("polaris-admin", "sha256:" + "2" * 64, ("/admin",), ()),
        "polaris": drill.ImagePin(
            "polaris",
            "sha256:" + "3" * 64,
            ("/entrypoint",),
            ("serve",),
            ("LANG=C.UTF-8",),
            "1000",
            "/app",
        ),
    }
    commands = []
    base_labels = {
        "com.databox.owner": "iceberg-recovery",
        "com.databox.run": token,
        "com.databox.stage": "stage1",
        "com.databox.seed-plan": "a" * 64,
    }
    recovery_labels = {
        **base_labels,
        "com.databox.phase": "recovery",
        "com.databox.approved-plan": "b" * 64,
    }
    network = {
        "Name": resources["network"],
        "Id": "network-id",
        "Created": "2026-09-14T12:00:00Z",
        "Scope": "local",
        "Driver": "bridge",
        "EnableIPv6": False,
        "IPAM": {"Driver": "default", "Options": None, "Config": []},
        "Internal": False,
        "Attachable": False,
        "Ingress": False,
        "ConfigFrom": {"Network": ""},
        "ConfigOnly": False,
        "Containers": {},
        "Options": {},
        "Labels": base_labels,
    }
    volume = {
        "CreatedAt": "2026-09-14T12:00:00Z",
        "Driver": "local",
        "Labels": base_labels,
        "Mountpoint": "/private/docker/volumes/run-owned/_data",
        "Name": resources["postgresVolume"],
        "Options": None,
        "Scope": "local",
    }

    def container(key, *, alias, port_bindings, mounts):
        image_key = "postgres" if key == "postgresContainer" else "polaris"
        pin = images[image_key]
        name = resources[key]
        container_id = "1" * 64 if key == "postgresContainer" else "3" * 64
        return {
            "Id": container_id,
            "Name": f"/{name}",
            "Image": pin.image_id,
            "Path": "/bin/sh",
            "Args": ["-ceu", "exec sleep 21600"],
            "Config": {
                "Image": pin.image_id,
                "Entrypoint": ["/bin/sh"],
                "Cmd": ["-ceu", "exec sleep 21600"],
                "Env": list(pin.environment),
                "User": pin.user,
                "WorkingDir": pin.working_directory,
                "Labels": recovery_labels,
            },
            "HostConfig": {
                "NetworkMode": resources["network"],
                "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
                "AutoRemove": False,
                "Privileged": False,
                "ReadonlyRootfs": False,
                "Binds": None,
                "PortBindings": port_bindings,
            },
            "NetworkSettings": {
                "Networks": {
                    resources["network"]: {
                        "NetworkID": "network-id",
                        "Aliases": [name, alias],
                    }
                }
            },
            "Mounts": mounts,
        }

    postgres_mount = {
        "Type": "volume",
        "Name": resources["postgresVolume"],
        "Destination": "/var/lib/postgresql/data",
        "RW": True,
    }
    containers = {
        resources["postgresContainer"]: container(
            "postgresContainer", alias="postgres", port_bindings={}, mounts=[postgres_mount]
        ),
        resources["polarisContainer"]: container(
            "polarisContainer",
            alias="polaris",
            port_bindings={"8181/tcp": [{"HostIp": "127.0.0.1", "HostPort": "32124"}]},
            mounts=[],
        ),
    }
    for name, value in containers.items():
        network["Containers"][value["Id"]] = {"Name": name}
    network_projection = dict(network)
    network_projection.pop("Containers")
    expected_sha256 = hashlib.sha256(
        drill._canonical_json({"network": network_projection, "volume": volume})
    ).hexdigest()

    if variant == "unknown-attachment":
        network["Containers"]["4" * 64] = {"Name": "unrelated-container"}
    elif variant == "unknown-volume-consumer":
        containers["unrelated-volume-consumer"] = {
            "Id": "4" * 64,
            "Mounts": [
                {
                    "Type": "volume",
                    "Name": resources["postgresVolume"],
                    "Destination": "/unknown",
                    "RW": True,
                }
            ],
        }
    elif variant == "bootstrap-remnant":
        bootstrap = resources["bootstrapContainer"]
        containers[bootstrap] = {"Name": f"/{bootstrap}"}
        network["Containers"]["bootstrap"] = {"Name": bootstrap}
    elif variant == "public-port":
        containers[resources["polarisContainer"]]["HostConfig"]["PortBindings"]["8181/tcp"][0][
            "HostIp"
        ] = "0.0.0.0"
    elif variant == "changed-network":
        network["Options"] = {"com.example.changed": "true"}

    def runner(command, **kwargs):
        del kwargs
        commands.append(list(command))
        if command[:3] == ["docker", "network", "inspect"]:
            stdout = json.dumps([network])
        elif command[:3] == ["docker", "volume", "inspect"]:
            stdout = json.dumps([volume])
        elif command[:3] == ["docker", "container", "ls"]:
            filter_value = command[command.index("--filter") + 1]
            if filter_value.startswith("volume="):
                consumers = []
                for name, value in containers.items():
                    if any(
                        mount.get("Name") == resources["postgresVolume"]
                        for mount in value.get("Mounts", [])
                    ):
                        consumers.append(f"{value['Id'][:12]}\t{name}")
                stdout = "\n".join(consumers) + ("\n" if consumers else "")
            else:
                name = filter_value[len("name=^") : -1]
                stdout = f"{name}\n" if name in containers else ""
        elif command[:3] == ["docker", "container", "inspect"]:
            stdout = json.dumps([containers[command[3]]])
        elif command[:3] == ["docker", "rm", "--force"]:
            name = command[3]
            containers.pop(name)
            network["Containers"] = {
                key: value
                for key, value in network["Containers"].items()
                if value.get("Name") != name
            }
            stdout = ""
        else:
            raise AssertionError(f"unexpected Docker command: {command}")
        return subprocess.CompletedProcess(command, 0, stdout, "")

    stack = drill.IsolatedStage1Stack(
        scope=scope,
        resources=resources,
        images=images,
        seed_plan_sha256="a" * 64,
        execution_plan_sha256="b" * 64,
        runner=runner,
    )
    return stack, expected_sha256, commands


def test_recovery_stack_removes_only_exact_pinned_remnants() -> None:
    stack, expected_sha256, commands = _recovery_stack_fixture()

    stack.use_retained_resources(expected_sha256)

    removals = [command for command in commands if command[:3] == ["docker", "rm", "--force"]]
    assert len(removals) == 2
    assert not any(
        command[:2] in (["docker", "network"], ["docker", "volume"]) and "rm" in command
        for command in commands
    )


@pytest.mark.parametrize(
    ("variant", "message"),
    [
        ("unknown-attachment", "unknown attachments"),
        ("unknown-volume-consumer", "volume has unknown consumers"),
        ("bootstrap-remnant", "cannot own a bootstrap"),
        ("public-port", "port is not loopback-only"),
        ("changed-network", "changed after Seed-A"),
    ],
)
def test_recovery_stack_refuses_unknown_or_changed_remnants(variant, message) -> None:
    stack, expected_sha256, commands = _recovery_stack_fixture(variant)

    with pytest.raises(drill.DrillError, match=message):
        stack.use_retained_resources(expected_sha256)

    assert not any(command[:3] == ["docker", "rm", "--force"] for command in commands)


@pytest.mark.parametrize(
    "stage",
    [
        "point-a-empty-prefix",
        "canary-put",
        "canary-delete",
        "canary-marker-read",
        "canary-marker-validation",
        "canary-source-read",
        "canary-restore",
        "canary-restore-validation",
        "canary-restored-source-read",
        "canary-residual-validation",
        "catalog-provision",
        "namespace-create",
        "table-schema-construction",
        "table-create",
        "table-fileio-fence",
        "point-a-append",
        "point-a-capture",
        "stage1-prefix-validation",
    ],
)
def test_point_a_stages_sanitize_generic_errors_and_persist_only_stage(
    tmp_path: Path, stage: str
) -> None:
    private = tmp_path / stage
    private.mkdir(mode=0o700)
    plan_path = private / "seed-a.plan.json"

    def fail() -> None:
        raise RuntimeError("private provider detail")

    with pytest.raises(drill.SeedStageError) as captured:
        drill._seed_stage(
            "point-a-preparation",
            lambda: drill._seed_stage(stage, fail),
        )

    assert captured.value.stage == stage
    assert "private provider detail" not in str(captured.value)
    receipt_path = drill._write_seed_failure_receipt(
        plan_path=plan_path,
        plan_sha256="a" * 64,
        error=captured.value,
    )
    receipt = json.loads(receipt_path.read_text())
    assert receipt["errorStage"] == stage
    assert receipt["errorKind"] == "unclassified"
    assert "private provider detail" not in receipt_path.read_text()
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600


def test_live_capability_canary_reports_sanitized_put_stage() -> None:
    scope = drill._scope("0123456789abcdef")

    class FailingWriterStore:
        def put_canary(self, key, payload):
            del key, payload
            raise drill.DrillError("private provider detail")

    operations = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=object(),
        writer_store=FailingWriterStore(),
        recovery_store=object(),
    )

    with pytest.raises(drill.SeedStageError) as captured:
        operations._verify_capability_canary()

    assert captured.value.stage == "canary-put"
    assert "private provider detail" not in str(captured.value)


def test_preverified_canary_cannot_mask_foreign_prefix_state() -> None:
    scope = drill._scope("0123456789abcdef")
    node = drill.GraphNode(
        key=f"{scope.prefix}/capability-canary.bin",
        kind="capability-canary",
        source_version_id="source-canary",
        etag='"canary"',
        size=7,
        sha256=hashlib.sha256(b"canary\n").hexdigest(),
        depth=0,
    )

    class RecoveryStore:
        def verify_only_key(self, key):
            assert key == node.key
            raise drill.DrillError("foreign private key detail")

    operations = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=object(),
        writer_store=object(),
        recovery_store=RecoveryStore(),
    )

    with pytest.raises(drill.SeedStageError) as captured:
        operations.prepare(
            scope,
            drill._DETERMINISTIC_ROWS,
            capability_canary=node,
        )

    assert captured.value.stage == "canary-residual-validation"
    assert "foreign private key detail" not in str(captured.value)


def test_live_prepare_nests_table_location_beneath_explicit_namespace_location() -> None:
    scope = drill._scope("0123456789abcdef")
    canary = drill.GraphNode(
        key=f"{scope.prefix}/capability-canary.bin",
        kind="capability-canary",
        source_version_id="source-canary",
        etag='"canary"',
        size=7,
        sha256=hashlib.sha256(b"canary\n").hexdigest(),
        depth=0,
    )
    calls = []

    class RecoveryStore:
        def verify_only_key(self, key):
            assert key == canary.key

        def current_state(self, node):
            assert node == canary
            return drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id="restored-canary",
                size=canary.size,
                sha256=canary.sha256,
            )

        def exact_source_state(self, node):
            assert node == canary

    class Catalog:
        def create_namespace(self, namespace, properties=None):
            calls.append(("namespace", namespace, properties or {}))

        def create_table(self, identifier, *, schema, location, properties):
            del schema
            calls.append(("table", identifier, location, properties))
            raise RuntimeError("stop after recording the table request")

    class Gateway:
        def provision(self, requested_scope):
            assert requested_scope == scope
            return Catalog()

    operations = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=Gateway(),
        writer_store=object(),
        recovery_store=RecoveryStore(),
    )

    with pytest.raises(drill.SeedStageError) as captured:
        operations.prepare(
            scope,
            drill._DETERMINISTIC_ROWS,
            capability_canary=canary,
        )

    namespace_location = f"s3://private-bucket/{scope.prefix}/{scope.namespace}"
    assert captured.value.stage == "table-create"
    assert calls == [
        ("namespace", scope.namespace, {"location": namespace_location}),
        (
            "table",
            (scope.namespace, scope.table),
            f"{namespace_location}/{scope.table}",
            {"format-version": "2"},
        ),
    ]


def test_stage1_prefix_validation_rejects_orphans_and_more_than_64_keys() -> None:
    scope = drill._scope("0123456789abcdef")
    canary = drill.GraphNode(
        key=f"{scope.prefix}/capability-canary.bin",
        kind="capability-canary",
        source_version_id="source-canary",
        etag='"canary"',
        size=7,
        sha256=hashlib.sha256(b"canary\n").hexdigest(),
        depth=0,
    )
    graph_node = drill.GraphNode(
        key=f"{scope.prefix}/table/metadata/root.json",
        kind="metadata",
        source_version_id="source-root",
        etag='"root"',
        size=10,
        sha256="a" * 64,
        depth=0,
    )
    capture = drill.TableCapture(
        bucket="private-bucket",
        table_uuid="table-uuid",
        metadata_location=f"s3://private-bucket/{graph_node.key}",
        snapshot_id=42,
        schema_sha256="b" * 64,
        row_count=3,
        rows_sha256="c" * 64,
        nodes=(graph_node,),
    )

    class OrphanStore:
        def prefix_keys(self):
            return frozenset({canary.key, graph_node.key, f"{scope.prefix}/foreign.bin"})

    with pytest.raises(drill.DrillError, match="does not exactly match"):
        drill._validate_stage1_prefix(OrphanStore(), canary, capture)

    oversized = drill.TableCapture(
        bucket=capture.bucket,
        table_uuid=capture.table_uuid,
        metadata_location=capture.metadata_location,
        snapshot_id=capture.snapshot_id,
        schema_sha256=capture.schema_sha256,
        row_count=capture.row_count,
        rows_sha256=capture.rows_sha256,
        nodes=tuple(
            drill.GraphNode(
                key=f"{scope.prefix}/table/data/{index}.parquet",
                kind="data",
                source_version_id=f"source-{index}",
                etag=f'"etag-{index}"',
                size=1,
                sha256=f"{index:064x}",
                depth=3,
            )
            for index in range(64)
        ),
    )
    with pytest.raises(drill.DrillError, match="exceeds the object-count"):
        drill._validate_stage1_prefix(OrphanStore(), canary, oversized)


def test_live_capability_canary_uses_writer_delete_and_recovery_exact_restore() -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    scope = drill._scope(token)
    calls = []
    node = drill.GraphNode(
        key=f"{scope.prefix}/capability-canary.bin",
        kind="capability-canary",
        source_version_id="source-canary",
        etag='"canary"',
        size=7,
        sha256=hashlib.sha256(b"canary\n").hexdigest(),
        depth=0,
    )

    class WriterStore:
        def put_canary(self, key, payload):
            calls.append(("writer-put", key, payload))
            return node

        def delete_current(self, candidate):
            calls.append(("writer-delete", candidate.key))
            return drill.DeleteResult(delete_marker=True, version_id="marker-canary")

        def current_state(self, candidate):
            calls.append(("writer-marker", candidate.key))
            return drill.ObjectState(
                exists=False,
                delete_marker=True,
                version_id="marker-canary",
            )

    class RecoveryStore:
        def exact_source_state(self, candidate):
            calls.append(("recovery-source", candidate.key))
            return drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id=candidate.source_version_id,
                size=candidate.size,
                sha256=candidate.sha256,
            )

        def restore(self, candidate):
            calls.append(("recovery-restore", candidate.key))
            return drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id="restored-canary",
                size=candidate.size,
                sha256=candidate.sha256,
            )

    operations = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=object(),
        writer_store=WriterStore(),
        recovery_store=RecoveryStore(),
    )

    operations._verify_capability_canary()

    assert calls == [
        ("writer-put", node.key, b"canary\n"),
        ("writer-delete", node.key),
        ("writer-marker", node.key),
        ("recovery-source", node.key),
        ("recovery-restore", node.key),
        ("recovery-source", node.key),
    ]


def test_catalog_table_requires_vended_session_credentials_before_file_access() -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    scope = drill._scope(token)

    class FileIO:
        properties = {
            "s3.access-key-id": "temporary-access-key",
            "s3.secret-access-key": "temporary-secret-key",
        }

    class Table:
        metadata_location = f"s3://private-bucket/{scope.prefix}/metadata/root.json"
        io = FileIO()

    operations = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=object(),
        writer_store=object(),
        recovery_store=object(),
    )

    with pytest.raises(drill.DrillError, match="lacks vended session credentials"):
        operations._fence_table(Table())


def test_fenced_file_io_rejects_external_location_before_delegate_access() -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    scope = drill._scope(token)

    class Delegate:
        properties = {}

        def new_input(self, location):
            raise AssertionError(f"external location was opened: {location}")

    operations = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=object(),
        writer_store=object(),
        recovery_store=object(),
    )
    fenced = drill._PrefixFencedFileIO(Delegate(), operations._key)

    with pytest.raises(drill.DrillError, match="external or malformed"):
        fenced.new_input("s3://other-bucket/outside/manifest.avro")


def test_fenced_file_io_binds_real_pyiceberg_missing_input_to_requested_location(
    tmp_path: Path,
) -> None:
    from urllib.parse import urlparse

    from pyiceberg.catalog.sql import SqlCatalog

    warehouse = tmp_path / "warehouse"
    warehouse.mkdir()
    catalog = SqlCatalog(
        "missing-object-repro",
        uri=f"sqlite:///{tmp_path / 'catalog.db'}",
        warehouse=warehouse.as_uri(),
    )
    catalog.create_namespace("ns")
    schema = Schema(
        NestedField(1, "event_id", LongType(), required=True),
        NestedField(2, "generation", StringType(), required=True),
        NestedField(3, "value", LongType(), required=True),
    )
    table = catalog.create_table(("ns", "tbl"), schema)
    table.append(
        pa.Table.from_pylist(
            [
                {"event_id": 1, "generation": "a", "value": 10},
                {"event_id": 2, "generation": "a", "value": 20},
                {"event_id": 3, "generation": "a", "value": 30},
            ],
            schema=pa.schema(
                [
                    pa.field("event_id", pa.int64(), nullable=False),
                    pa.field("generation", pa.string(), nullable=False),
                    pa.field("value", pa.int64(), nullable=False),
                ]
            ),
        )
    )
    point_a = catalog.load_table(("ns", "tbl"))
    snapshot = point_a.current_snapshot()
    assert snapshot is not None
    manifest_list = snapshot.manifest_list
    requested_locations = []

    def validate(location):
        requested_locations.append(location)

    point_a.io = drill._PrefixFencedFileIO(point_a.io, validate)
    Path(urlparse(manifest_list).path).unlink()

    with pytest.raises(FileNotFoundError) as missing:
        list(point_a.scan().plan_files())

    assert manifest_list in requested_locations
    assert manifest_list in str(missing.value)
    assert isinstance(missing.value.__cause__, FileNotFoundError)


def test_capture_rejects_aggregate_size_before_version_body_reads(monkeypatch) -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    scope = drill._scope(token)
    objects = tuple(
        drill.GraphObject(
            location=f"s3://private-bucket/{scope.prefix}/metadata/object-{index}.json",
            kind="metadata" if index == 0 else "metadata-ancestor",
            depth=index,
        )
        for index in range(2)
    )

    def fake_graph(table, *, location_validator):
        del table
        for item in objects:
            location_validator(item.location)
        return objects

    monkeypatch.setattr(drill, "capture_iceberg_graph", fake_graph)

    class Store:
        def list_versions(self, key):
            return (
                drill.VersionEntry(
                    key=key,
                    version_id=f"version-{key[-6:]}",
                    latest=True,
                    delete_marker=False,
                    etag='"etag"',
                    size=20 * 1024 * 1024,
                ),
            )

        def _version_state(self, entry):
            raise AssertionError(f"oversized graph body was read: {entry}")

    operations = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=object(),
        writer_store=object(),
        recovery_store=Store(),
    )

    with pytest.raises(drill.DrillError, match="before object reads"):
        operations._capture(object())


def test_break_proof_rejects_catalog_or_auth_unavailability() -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    scope = drill._scope(token)

    class UnavailableCatalog:
        def list_namespaces(self):
            raise RuntimeError("catalog unavailable")

        def load_table(self, identifier):
            raise AssertionError(f"unexpected table load: {identifier}")

    class Gateway:
        def open(self, requested_scope):
            assert requested_scope == scope
            return UnavailableCatalog()

    operations = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=Gateway(),
        writer_store=object(),
        recovery_store=object(),
    )
    manifest = {"scope": {"runId": token}}

    with pytest.raises(drill.RecoveryStageError) as failure:
        operations.assert_table_unreadable(manifest)
    assert failure.value.stage == "break-proof"
    assert failure.value.error_kind == "catalog-health"


def test_break_proof_requires_expected_markers_and_readable_historical_sources() -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    scope = drill._scope(token)
    key = f"{scope.prefix}/metadata/root.json"
    source = drill.VersionEntry(
        key=key,
        version_id="source-version",
        latest=False,
        delete_marker=False,
        etag='"source"',
        size=10,
    )
    marker = drill.VersionEntry(
        key=key,
        version_id="delete-marker",
        latest=True,
        delete_marker=True,
    )

    class VendedIO:
        properties = {
            "s3.access-key-id": "temporary-access-key",
            "s3.secret-access-key": "temporary-secret-key",
            "s3.session-token": "temporary-session-token",
        }

    class BrokenTable:
        metadata_location = f"s3://private-bucket/{key}"
        io = VendedIO()

        class Scan:
            def plan_files(self):
                raise FileNotFoundError(f"expected missing graph object: s3://private-bucket/{key}")

        def scan(self):
            return self.Scan()

    class Catalog:
        def list_namespaces(self):
            return [(scope.namespace,)]

        def load_table(self, identifier):
            assert identifier == (scope.namespace, scope.table)
            return BrokenTable()

    class Gateway:
        def open(self, requested_scope):
            assert requested_scope == scope
            return Catalog()

    class Store:
        def __init__(self, timeline):
            self.timeline = timeline

        def list_versions(self, requested_key):
            assert requested_key == key
            return self.timeline

        def _version_state(self, entry):
            assert entry == source
            return drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id=entry.version_id,
                size=10,
                sha256="a" * 64,
            )

    class ExactMissingInput:
        def __init__(self, location):
            self.location = location

        def open(self):
            raise FileNotFoundError(f"exact approved graph object is absent: {self.location}")

    class ExactMissingIO:
        def new_input(self, location):
            assert location == f"s3://private-bucket/{key}"
            return ExactMissingInput(location)

    class UnexpectedProofInput:
        def open(self):
            raise RuntimeError("network or authentication failure")

    class UnexpectedProofIO:
        def new_input(self, location):
            assert location == f"s3://private-bucket/{key}"
            return UnexpectedProofInput()

    manifest = {
        "scope": {"runId": token},
        "graph": {
            "nodes": [
                {
                    "key": key,
                    "kind": "metadata",
                    "sourceVersionId": "source-version",
                    "etag": '"source"',
                    "size": 10,
                    "sha256": "a" * 64,
                    "depth": 0,
                }
            ]
        },
    }
    missing_source = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=Gateway(),
        writer_store=object(),
        recovery_store=Store((marker,)),
    )
    missing_source._break_proof_table = BrokenTable()
    missing_source._break_proof_io = ExactMissingIO()
    with pytest.raises(drill.RecoveryStageError) as invalid_source:
        missing_source.assert_table_unreadable(manifest)
    assert invalid_source.value.stage == "break-proof"
    assert invalid_source.value.error_kind == "missing-proof-invalid"
    assert "historical source" in str(invalid_source.value.__cause__)

    expected_failure = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=Gateway(),
        writer_store=object(),
        recovery_store=Store((source, marker)),
    )
    expected_failure._break_proof_table = BrokenTable()
    expected_failure._break_proof_io = ExactMissingIO()
    expected_failure.assert_table_unreadable(manifest)

    class MissingMetadataCatalog(Catalog):
        def load_table(self, identifier):
            assert identifier == (scope.namespace, scope.table)
            raise FileNotFoundError(f"confirmed PyIceberg missing metadata: {key}")

    class MissingMetadataGateway:
        def open(self, requested_scope):
            assert requested_scope == scope
            return MissingMetadataCatalog()

    missing_metadata = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=MissingMetadataGateway(),
        writer_store=object(),
        recovery_store=Store((source, marker)),
    )
    missing_metadata._break_proof_table = BrokenTable()
    missing_metadata._break_proof_io = ExactMissingIO()
    missing_metadata.assert_table_unreadable(manifest)

    class UnrelatedMissingTable:
        class Scan:
            def plan_files(self):
                raise FileNotFoundError(
                    f"unrelated local configuration mentions {key} but not its S3 location"
                )

        def scan(self):
            return self.Scan()

    class UnrelatedMissingCatalog(Catalog):
        def load_table(self, identifier):
            assert identifier == (scope.namespace, scope.table)
            raise FileNotFoundError("unrelated missing local configuration")

    class UnrelatedMissingGateway:
        def open(self, requested_scope):
            assert requested_scope == scope
            return UnrelatedMissingCatalog()

    unrelated_missing = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=UnrelatedMissingGateway(),
        writer_store=object(),
        recovery_store=Store((source, marker)),
    )
    unrelated_missing._break_proof_io = ExactMissingIO()
    unrelated_missing._break_proof_table = UnrelatedMissingTable()
    with pytest.raises(drill.RecoveryStageError) as unrelated_query_failure:
        unrelated_missing.assert_table_unreadable(manifest)
    assert unrelated_query_failure.value.stage == "break-proof"
    assert unrelated_query_failure.value.error_kind == "missing-query-unexpected-error"

    class SubstringMissingTable:
        class Scan:
            def plan_files(self):
                raise FileNotFoundError(f"wrong object: s3://private-bucket/{key}-backup")

        def scan(self):
            return self.Scan()

    substring_missing = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=Gateway(),
        writer_store=object(),
        recovery_store=Store((source, marker)),
    )
    substring_missing._break_proof_table = SubstringMissingTable()
    substring_missing._break_proof_io = ExactMissingIO()
    with pytest.raises(drill.RecoveryStageError) as substring_failure:
        substring_missing.assert_table_unreadable(manifest)
    assert substring_failure.value.stage == "break-proof"
    assert substring_failure.value.error_kind == "missing-query-unexpected-error"

    for uri_suffix in ("?other", "#other"):

        class UriContinuationTable:
            def __init__(self, suffix):
                self.suffix = suffix

            class Scan:
                def __init__(self, suffix):
                    self.suffix = suffix

                def plan_files(self):
                    raise FileNotFoundError(f"wrong object: s3://private-bucket/{key}{self.suffix}")

            def scan(self):
                return self.Scan(self.suffix)

        uri_continuation = drill.LiveWarehouseDrillOperations(
            scope=scope,
            bucket="private-bucket",
            gateway=Gateway(),
            writer_store=object(),
            recovery_store=Store((source, marker)),
        )
        uri_continuation._break_proof_table = UriContinuationTable(uri_suffix)
        uri_continuation._break_proof_io = ExactMissingIO()
        with pytest.raises(drill.RecoveryStageError) as uri_failure:
            uri_continuation.assert_table_unreadable(manifest)
        assert uri_failure.value.stage == "break-proof"
        assert uri_failure.value.error_kind == "missing-query-unexpected-error"

    class NetworkFailureTable:
        metadata_location = f"s3://private-bucket/{key}"
        io = VendedIO()

        class Scan:
            def plan_files(self):
                raise RuntimeError("network or authentication failure")

        def scan(self):
            return self.Scan()

    class NetworkFailureCatalog(Catalog):
        def load_table(self, identifier):
            assert identifier == (scope.namespace, scope.table)
            return NetworkFailureTable()

    class NetworkFailureGateway:
        def open(self, requested_scope):
            assert requested_scope == scope
            return NetworkFailureCatalog()

    unrelated_failure = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=NetworkFailureGateway(),
        writer_store=object(),
        recovery_store=Store((source, marker)),
    )
    unrelated_failure._break_proof_io = ExactMissingIO()
    unrelated_failure._break_proof_table = NetworkFailureTable()
    with pytest.raises(drill.RecoveryStageError) as unexpected_query:
        unrelated_failure.assert_table_unreadable(manifest)
    assert unexpected_query.value.stage == "break-proof"
    assert unexpected_query.value.error_kind == "missing-query-unexpected-error"

    class TranslatedMissingTable:
        metadata_location = f"s3://private-bucket/{key}"
        io = VendedIO()

        class Scan:
            def plan_files(self):
                try:
                    raise FileNotFoundError(
                        f"exact approved graph object is absent: s3://private-bucket/{key}"
                    )
                except FileNotFoundError as missing:
                    raise RuntimeError("translated missing object") from missing

        def scan(self):
            return self.Scan()

    class TranslatedMissingCatalog(Catalog):
        def load_table(self, identifier):
            assert identifier == (scope.namespace, scope.table)
            return TranslatedMissingTable()

    class TranslatedMissingGateway:
        def open(self, requested_scope):
            assert requested_scope == scope
            return TranslatedMissingCatalog()

    translated_missing = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=TranslatedMissingGateway(),
        writer_store=object(),
        recovery_store=Store((source, marker)),
    )
    translated_missing._break_proof_io = ExactMissingIO()
    translated_missing._break_proof_table = TranslatedMissingTable()
    translated_missing.assert_table_unreadable(manifest)


def test_break_proof_correlates_query_and_direct_fileio_location() -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    scope = drill._scope(token)
    metadata_key = f"{scope.prefix}/metadata/root.json"
    data_key = f"{scope.prefix}/data/part.parquet"
    nodes = (
        {
            "key": metadata_key,
            "kind": "metadata",
            "sourceVersionId": "metadata-source",
            "etag": '"metadata"',
            "size": 10,
            "sha256": "a" * 64,
            "depth": 0,
        },
        {
            "key": data_key,
            "kind": "data",
            "sourceVersionId": "data-source",
            "etag": '"data"',
            "size": 20,
            "sha256": "b" * 64,
            "depth": 3,
        },
    )
    manifest = {"scope": {"runId": token}, "graph": {"nodes": list(nodes)}}
    versions = {
        node["key"]: (
            drill.VersionEntry(
                key=node["key"],
                version_id=node["sourceVersionId"],
                latest=False,
                delete_marker=False,
                etag=node["etag"],
                size=node["size"],
            ),
            drill.VersionEntry(
                key=node["key"],
                version_id=f"{node['kind']}-marker",
                latest=True,
                delete_marker=True,
            ),
        )
        for node in nodes
    }
    digests = {node["key"]: node["sha256"] for node in nodes}

    class Store:
        def list_versions(self, key):
            return versions[key]

        def _version_state(self, entry):
            return drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id=entry.version_id,
                size=entry.size,
                sha256=digests[entry.key],
            )

    location = f"s3://private-bucket/{metadata_key}"

    class MissingTable:
        class Scan:
            def plan_files(self):
                raise FileNotFoundError(f"query requires {location}")

        def scan(self):
            return self.Scan()

    class MissingInput:
        def open(self):
            raise FileNotFoundError(f"direct read requires {location}")

    class RecordingIO:
        def __init__(self):
            self.locations = []

        def new_input(self, requested_location):
            self.locations.append(requested_location)
            return MissingInput()

    class Catalog:
        def list_namespaces(self):
            return [(scope.namespace,)]

    class Gateway:
        def open(self, requested_scope):
            assert requested_scope == scope
            return Catalog()

    direct_io = RecordingIO()
    operations = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=Gateway(),
        writer_store=object(),
        recovery_store=Store(),
    )
    operations._break_proof_table = MissingTable()
    operations._break_proof_io = direct_io

    operations.assert_table_unreadable(manifest)

    assert direct_io.locations == [location]

    wrong_location = f"s3://private-bucket/{data_key}"

    class MismatchedInput:
        def open(self):
            raise FileNotFoundError(f"direct read failed for {wrong_location}")

    class MismatchedIO:
        def new_input(self, requested_location):
            assert requested_location == location
            return MismatchedInput()

    mismatch = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=Gateway(),
        writer_store=object(),
        recovery_store=Store(),
    )
    mismatch._break_proof_table = MissingTable()
    mismatch._break_proof_io = MismatchedIO()
    with pytest.raises(drill.RecoveryStageError) as mismatch_failure:
        mismatch.assert_table_unreadable(manifest)
    assert mismatch_failure.value.stage == "break-proof"
    assert mismatch_failure.value.error_kind == "missing-proof-unexpected-error"


def test_validate_caches_fenced_table_and_fileio_for_break_proof(monkeypatch) -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    scope = drill._scope(token)
    key = f"{scope.prefix}/metadata/root.json"
    node = drill.GraphNode(
        key=key,
        kind="metadata",
        source_version_id="source-version",
        etag='"etag"',
        size=10,
        sha256="c" * 64,
        depth=0,
    )
    capture = drill.TableCapture(
        bucket="private-bucket",
        table_uuid="table-uuid",
        metadata_location=f"s3://private-bucket/{key}",
        snapshot_id=42,
        schema_sha256="a" * 64,
        row_count=len(drill._DETERMINISTIC_ROWS),
        rows_sha256=drill._rows_digest(drill._DETERMINISTIC_ROWS),
        nodes=(node,),
    )
    graph, _logical_sha = drill._validate_capture(scope, capture)

    class VendedIO:
        properties = {
            "s3.access-key-id": "temporary-access-key",
            "s3.secret-access-key": "temporary-secret-key",
            "s3.session-token": "temporary-session-token",
        }

    class Table:
        metadata_location = capture.metadata_location
        io = VendedIO()

    table = Table()

    class Catalog:
        def load_table(self, identifier):
            assert identifier == (scope.namespace, scope.table)
            return table

    class Gateway:
        def open(self, requested_scope):
            assert requested_scope == scope
            return Catalog()

    class Store:
        def list_versions(self, requested_key):
            assert requested_key == key
            return (
                drill.VersionEntry(
                    key=key,
                    version_id=node.source_version_id,
                    latest=True,
                    delete_marker=False,
                    etag=node.etag,
                    size=node.size,
                ),
            )

    operations = drill.LiveWarehouseDrillOperations(
        scope=scope,
        bucket="private-bucket",
        gateway=Gateway(),
        writer_store=object(),
        recovery_store=Store(),
    )

    def capture_table(received_table):
        assert received_table is table
        assert isinstance(received_table.io, drill._PrefixFencedFileIO)
        return capture

    monkeypatch.setattr(operations, "_capture", capture_table)
    operations.validate(
        {
            "scope": {"runId": token},
            "graph": graph,
            "table": {"tableUuid": capture.table_uuid},
        }
    )

    assert operations._break_proof_table is table
    assert operations._break_proof_io is table.io
    assert isinstance(operations._break_proof_io, drill._PrefixFencedFileIO)


def test_execute_rejects_oversized_manifest_before_any_effect(tmp_path: Path) -> None:
    token = "0123456789abcdef"  # secret-scan: allow

    class PrepareOnly:
        def prepare(self, scope, rows):
            del rows
            key = f"{scope.prefix}/metadata/root.json"
            return drill.TableCapture(
                bucket="private-bucket",
                table_uuid="table-uuid",
                metadata_location=f"s3://private-bucket/{key}",
                snapshot_id=42,
                schema_sha256="a" * 64,
                row_count=3,
                rows_sha256="b" * 64,
                nodes=(
                    drill.GraphNode(
                        key=key,
                        kind="metadata",
                        source_version_id="source-version",
                        etag='"etag"',
                        size=10,
                        sha256="c" * 64,
                        depth=0,
                    ),
                ),
            )

    prepared = drill.prepare_drill(
        operations=PrepareOnly(),
        evidence_root=tmp_path / ".recovery" / "iceberg",
        token_factory=lambda: token,
    )
    manifest_path = Path(prepared["manifest"])
    oversized = b" " * (drill._MAX_PRIVATE_RESPONSE_BYTES + 1) + manifest_path.read_bytes()
    manifest_path.write_bytes(oversized)

    class NoEffects:
        def current_state(self, node):
            raise AssertionError(f"unexpected effect for {node}")

    with pytest.raises(drill.DrillError, match="exceeds"):
        drill.execute_drill(
            operations=NoEffects(),
            manifest_path=manifest_path,
            expected_sha256=hashlib.sha256(oversized).hexdigest(),
        )


def test_execute_requires_hash_marks_damage_and_restores_leaf_to_root(tmp_path: Path) -> None:
    token = "fedcba9876543210"  # secret-scan: allow

    class Operations:
        def __init__(self):
            self.calls = []
            self.states = {}
            self.marker_path = None

        def prepare(self, scope, rows):
            del rows
            prefix = scope.prefix
            nodes = (
                drill.GraphNode(
                    key=f"{prefix}/metadata/root.json",
                    kind="metadata",
                    source_version_id="source-root",
                    etag='"root"',
                    size=100,
                    sha256="a" * 64,
                    depth=0,
                ),
                drill.GraphNode(
                    key=f"{prefix}/metadata/manifest.avro",
                    kind="manifest",
                    source_version_id="source-manifest",
                    etag='"manifest"',
                    size=200,
                    sha256="b" * 64,
                    depth=2,
                ),
                drill.GraphNode(
                    key=f"{prefix}/data/rows.parquet",
                    kind="data",
                    source_version_id="source-data",
                    etag='"data"',
                    size=300,
                    sha256="c" * 64,
                    depth=3,
                ),
            )
            self.states = {
                node.key: drill.ObjectState(
                    exists=True,
                    delete_marker=False,
                    version_id=node.source_version_id,
                    size=node.size,
                    sha256=node.sha256,
                )
                for node in nodes
            }
            return drill.TableCapture(
                bucket="private-bucket",
                table_uuid="table-uuid",
                metadata_location=f"s3://private-bucket/{nodes[0].key}",
                snapshot_id=42,
                schema_sha256="d" * 64,
                row_count=3,
                rows_sha256="e" * 64,
                nodes=nodes,
            )

        def current_state(self, node):
            return self.states[node.key]

        def delete_current(self, node):
            assert self.marker_path is not None and self.marker_path.is_file()
            assert stat.S_IMODE(self.marker_path.stat().st_mode) == 0o600
            self.calls.append(("delete", node.kind))
            marker = f"marker-{node.kind}"
            self.states[node.key] = drill.ObjectState(
                exists=False,
                delete_marker=True,
                version_id=marker,
            )
            return drill.DeleteResult(delete_marker=True, version_id=marker)

        def assert_table_unreadable(self, manifest):
            self.calls.append(("unreadable", manifest["scope"]["table"]))

        def restore(self, node):
            self.calls.append(("restore", node.kind))
            state = drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id=f"restored-{node.kind}",
                size=node.size,
                sha256=node.sha256,
            )
            self.states[node.key] = state
            return state

        def validate(self, manifest):
            self.calls.append(("validate", manifest["scope"]["table"]))
            table = manifest["table"]
            graph = manifest["graph"]
            return drill.ValidationResult(
                table_uuid=table["tableUuid"],
                metadata_location=table["metadataLocation"],
                snapshot_id=table["snapshotId"],
                logical_graph_sha256=graph["logicalSha256"],
                row_count=table["rowCount"],
                rows_sha256=table["rowsSha256"],
            )

    operations = Operations()
    prepared = drill.prepare_drill(
        operations=operations,
        evidence_root=tmp_path / ".recovery" / "iceberg",
        token_factory=lambda: token,
    )
    manifest_path = Path(prepared["manifest"])
    operations.marker_path = manifest_path.parent / "damage-started.json"

    result = drill.execute_drill(
        operations=operations,
        manifest_path=manifest_path,
        expected_sha256=prepared["manifestSha256"],
    )

    assert operations.calls == [
        ("validate", f"events_{token}"),
        ("delete", "data"),
        ("delete", "manifest"),
        ("delete", "metadata"),
        ("unreadable", f"events_{token}"),
        ("restore", "data"),
        ("restore", "manifest"),
        ("restore", "metadata"),
        ("validate", f"events_{token}"),
    ]
    marker = json.loads(operations.marker_path.read_text())
    assert marker["schemaVersion"] == 2
    assert marker["manifestSha256"] == prepared["manifestSha256"]
    assert marker["runId"] == token
    assert marker["milestones"] == {
        "deletes": "complete",
        "breakProof": "passed",
        "restoration": "complete",
        "finalValidation": "passed",
        "containment": "pending",
    }
    assert [entry["phase"] for entry in marker["nodes"]] == [
        "promoted",
        "promoted",
        "promoted",
    ]
    assert [entry["deleteMarkerVersionId"] for entry in marker["nodes"]] == [
        "marker-data",
        "marker-manifest",
        "marker-metadata",
    ]
    assert [entry["promotedVersionId"] for entry in marker["nodes"]] == [
        "restored-data",
        "restored-manifest",
        "restored-metadata",
    ]
    assert result == {
        "status": "recovery-validated",
        "runId": token,
        "manifestSha256": prepared["manifestSha256"],
        "logicalGraphSha256": prepared["logicalGraphSha256"],
        "nodeCount": 3,
        "rowCount": 3,
    }


def test_execute_with_existing_damage_marker_is_restore_only(tmp_path: Path) -> None:
    token = "aabbccddeeff0011"  # secret-scan: allow

    class Operations:
        def __init__(self):
            self.calls = []
            self.node = None

        def prepare(self, scope, rows):
            del rows
            self.node = drill.GraphNode(
                key=f"{scope.prefix}/metadata/root.json",
                kind="metadata",
                source_version_id="source-root",
                etag='"root"',
                size=100,
                sha256="a" * 64,
                depth=0,
            )
            return drill.TableCapture(
                bucket="private-bucket",
                table_uuid="table-uuid",
                metadata_location=f"s3://private-bucket/{self.node.key}",
                snapshot_id=42,
                schema_sha256="b" * 64,
                row_count=3,
                rows_sha256="c" * 64,
                nodes=(self.node,),
            )

        def current_state(self, node):
            self.calls.append(("current", node.kind))
            return drill.ObjectState(
                exists=False,
                delete_marker=True,
                version_id="marker-root",
            )

        def delete_current(self, node):
            raise AssertionError(f"restore-only resume attempted delete: {node}")

        def assert_table_unreadable(self, manifest):
            raise AssertionError(f"restore-only resume attempted break proof: {manifest}")

        def restore(self, node):
            self.calls.append(("restore", node.kind))
            return drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id="restored-root",
                size=node.size,
                sha256=node.sha256,
            )

        def validate(self, manifest):
            self.calls.append(("validate", manifest["scope"]["table"]))
            table = manifest["table"]
            graph = manifest["graph"]
            return drill.ValidationResult(
                table_uuid=table["tableUuid"],
                metadata_location=table["metadataLocation"],
                snapshot_id=table["snapshotId"],
                logical_graph_sha256=graph["logicalSha256"],
                row_count=table["rowCount"],
                rows_sha256=table["rowsSha256"],
            )

    operations = Operations()
    prepared = drill.prepare_drill(
        operations=operations,
        evidence_root=tmp_path / ".recovery" / "iceberg",
        token_factory=lambda: token,
    )
    manifest_path = Path(prepared["manifest"])
    marker = drill._initial_damage_marker(
        scope=drill._scope(token),
        manifest_sha256=prepared["manifestSha256"],
        nodes=(operations.node,),
    )
    marker["nodes"][0]["phase"] = "deleted"
    marker["nodes"][0]["deleteMarkerVersionId"] = "marker-root"
    marker["milestones"]["deletes"] = "complete"
    marker["milestones"]["breakProof"] = "passed"
    drill._atomic_private_write(
        manifest_path.parent / "damage-started.json",
        drill._canonical_json(marker),
    )

    result = drill.execute_drill(
        operations=operations,
        manifest_path=manifest_path,
        expected_sha256=prepared["manifestSha256"],
    )

    assert result["status"] == "recovery-validated-after-interruption"
    assert operations.calls == [
        ("current", "metadata"),
        ("restore", "metadata"),
        ("validate", f"events_{token}"),
    ]


def test_legacy_damage_marker_restores_but_can_never_pass(tmp_path: Path) -> None:
    token = "0f1e2d3c4b5a6978"  # secret-scan: allow

    class Operations:
        def __init__(self):
            self.node = None
            self.state = None
            self.calls = []

        def prepare(self, scope, rows):
            del rows
            self.node = drill.GraphNode(
                key=f"{scope.prefix}/metadata/root.json",
                kind="metadata",
                source_version_id="source-root",
                etag='"root"',
                size=100,
                sha256="a" * 64,
                depth=0,
            )
            return drill.TableCapture(
                bucket="private-bucket",
                table_uuid="table-uuid",
                metadata_location=f"s3://private-bucket/{self.node.key}",
                snapshot_id=42,
                schema_sha256="b" * 64,
                row_count=3,
                rows_sha256="c" * 64,
                nodes=(self.node,),
            )

        def current_state(self, node):
            assert node == self.node
            self.calls.append("current")
            return self.state

        def restore(self, node):
            assert node == self.node
            self.calls.append("restore")
            self.state = drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id="restored-root",
                size=node.size,
                sha256=node.sha256,
            )
            return self.state

        def delete_current(self, node):
            raise AssertionError(f"legacy resume attempted delete: {node}")

        def assert_table_unreadable(self, manifest):
            raise AssertionError(f"legacy resume attempted break proof: {manifest}")

        def validate(self, manifest):
            raise AssertionError(f"legacy resume attempted final validation: {manifest}")

    operations = Operations()
    prepared = drill.prepare_drill(
        operations=operations,
        evidence_root=tmp_path / ".recovery" / "iceberg",
        token_factory=lambda: token,
    )
    manifest_path = Path(prepared["manifest"])
    operations.state = drill.ObjectState(
        exists=False,
        delete_marker=True,
        version_id="marker-root",
    )
    legacy_marker = {
        "schemaVersion": 1,
        "manifestSha256": prepared["manifestSha256"],
        "runId": token,
        "nodes": [
            {
                "key": operations.node.key,
                "sourceVersionId": operations.node.source_version_id,
                "phase": "deleted",
                "deleteMarkerVersionId": "marker-root",
                "promotedVersionId": None,
            }
        ],
    }
    drill._atomic_private_write(
        manifest_path.parent / "damage-started.json",
        drill._canonical_json(legacy_marker),
    )

    with pytest.raises(drill.RecoveryStageError) as failure:
        drill.execute_drill(
            operations=operations,
            manifest_path=manifest_path,
            expected_sha256=prepared["manifestSha256"],
        )
    assert failure.value.stage == "legacy-evidence"
    assert failure.value.error_kind == "inconclusive"
    assert operations.calls == ["current", "restore"]
    assert operations.state.exists
    assert operations.state.version_id == "restored-root"


def test_failed_break_proof_compensation_can_never_resume_as_success(tmp_path: Path) -> None:
    token = "f0e1d2c3b4a59687"  # secret-scan: allow

    class Operations:
        def __init__(self):
            self.node = None
            self.state = None
            self.delete_calls = 0
            self.break_calls = 0

        def prepare(self, scope, rows):
            del rows
            self.node = drill.GraphNode(
                key=f"{scope.prefix}/metadata/root.json",
                kind="metadata",
                source_version_id="source-root",
                etag='"root"',
                size=100,
                sha256="a" * 64,
                depth=0,
            )
            self.state = drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id=self.node.source_version_id,
                size=self.node.size,
                sha256=self.node.sha256,
            )
            return drill.TableCapture(
                bucket="private-bucket",
                table_uuid="table-uuid",
                metadata_location=f"s3://private-bucket/{self.node.key}",
                snapshot_id=42,
                schema_sha256="b" * 64,
                row_count=3,
                rows_sha256="c" * 64,
                nodes=(self.node,),
            )

        def current_state(self, node):
            assert node == self.node
            return self.state

        def delete_current(self, node):
            assert node == self.node
            self.delete_calls += 1
            self.state = drill.ObjectState(
                exists=False,
                delete_marker=True,
                version_id="marker-root",
            )
            return drill.DeleteResult(delete_marker=True, version_id="marker-root")

        def assert_table_unreadable(self, manifest):
            del manifest
            self.break_calls += 1
            raise drill.DrillError("break proof did not produce the required failure")

        def restore(self, node):
            assert node == self.node
            self.state = drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id="restored-root",
                size=node.size,
                sha256=node.sha256,
            )
            return self.state

        def validate(self, manifest):
            table = manifest["table"]
            graph = manifest["graph"]
            return drill.ValidationResult(
                table_uuid=table["tableUuid"],
                metadata_location=table["metadataLocation"],
                snapshot_id=table["snapshotId"],
                logical_graph_sha256=graph["logicalSha256"],
                row_count=table["rowCount"],
                rows_sha256=table["rowsSha256"],
            )

    operations = Operations()
    prepared = drill.prepare_drill(
        operations=operations,
        evidence_root=tmp_path / ".recovery" / "iceberg",
        token_factory=lambda: token,
    )
    manifest_path = Path(prepared["manifest"])

    with pytest.raises(drill.RecoveryStageError) as first_failure:
        drill.execute_drill(
            operations=operations,
            manifest_path=manifest_path,
            expected_sha256=prepared["manifestSha256"],
        )
    assert first_failure.value.stage == "break-proof"
    assert first_failure.value.error_kind == "unclassified"

    marker_path = manifest_path.parent / "damage-started.json"
    marker = json.loads(marker_path.read_text())
    assert marker["milestones"]["breakProof"] == "failed"
    assert marker["milestones"]["restoration"] == "complete"

    with pytest.raises(drill.RecoveryStageError) as resumed_failure:
        drill.execute_drill(
            operations=operations,
            manifest_path=manifest_path,
            expected_sha256=prepared["manifestSha256"],
        )
    assert resumed_failure.value.stage == "break-proof"
    assert resumed_failure.value.error_kind == "inconclusive"

    assert operations.delete_calls == 1
    assert operations.break_calls == 1


@pytest.mark.parametrize("break_outcome", ["passed", "failed"])
def test_break_proof_milestone_write_failure_still_restores_every_object(
    tmp_path: Path, monkeypatch, break_outcome: str
) -> None:
    token = "1029384756abcdef"  # secret-scan: allow

    class Operations:
        def __init__(self):
            self.node = None
            self.state = None

        def prepare(self, scope, rows):
            del rows
            self.node = drill.GraphNode(
                key=f"{scope.prefix}/metadata/root.json",
                kind="metadata",
                source_version_id="source-root",
                etag='"root"',
                size=100,
                sha256="a" * 64,
                depth=0,
            )
            self.state = drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id=self.node.source_version_id,
                size=self.node.size,
                sha256=self.node.sha256,
            )
            return drill.TableCapture(
                bucket="private-bucket",
                table_uuid="table-uuid",
                metadata_location=f"s3://private-bucket/{self.node.key}",
                snapshot_id=42,
                schema_sha256="b" * 64,
                row_count=3,
                rows_sha256="c" * 64,
                nodes=(self.node,),
            )

        def current_state(self, node):
            assert node == self.node
            return self.state

        def delete_current(self, node):
            assert node == self.node
            self.state = drill.ObjectState(
                exists=False,
                delete_marker=True,
                version_id="marker-root",
            )
            return drill.DeleteResult(delete_marker=True, version_id="marker-root")

        def assert_table_unreadable(self, manifest):
            del manifest
            if break_outcome == "failed":
                raise drill.DrillError("simulated break-proof mismatch")

        def restore(self, node):
            assert node == self.node
            self.state = drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id="restored-root",
                size=node.size,
                sha256=node.sha256,
            )
            return self.state

        def validate(self, manifest):
            table = manifest["table"]
            graph = manifest["graph"]
            return drill.ValidationResult(
                table_uuid=table["tableUuid"],
                metadata_location=table["metadataLocation"],
                snapshot_id=table["snapshotId"],
                logical_graph_sha256=graph["logicalSha256"],
                row_count=table["rowCount"],
                rows_sha256=table["rowsSha256"],
            )

    operations = Operations()
    prepared = drill.prepare_drill(
        operations=operations,
        evidence_root=tmp_path / ".recovery" / "iceberg",
        token_factory=lambda: token,
    )
    manifest_path = Path(prepared["manifest"])
    real_persist = drill._persist_damage_marker
    failed_once = False

    def fail_break_proof_persistence(path, marker):
        nonlocal failed_once
        milestones = marker.get("milestones")
        if (
            not failed_once
            and isinstance(milestones, dict)
            and milestones.get("breakProof") == break_outcome
        ):
            failed_once = True
            raise OSError("simulated private journal failure")
        real_persist(path, marker)

    monkeypatch.setattr(drill, "_persist_damage_marker", fail_break_proof_persistence)

    with pytest.raises(drill.RecoveryStageError) as failure:
        drill.execute_drill(
            operations=operations,
            manifest_path=manifest_path,
            expected_sha256=prepared["manifestSha256"],
        )
    assert failure.value.stage == "damage-journal"
    assert failed_once
    assert operations.state.exists
    assert operations.state.version_id == "restored-root"
    marker = json.loads((manifest_path.parent / "damage-started.json").read_text())
    assert marker["milestones"]["breakProof"] == "pending"
    assert marker["milestones"]["restoration"] == "complete"
    assert marker["nodes"][0]["phase"] == "promoted"


@pytest.mark.parametrize(
    ("failure_point", "expected_delete_milestone"),
    [("node-deleted", "failed"), ("deletes-complete", "pending")],
)
def test_delete_journal_write_failure_after_remote_delete_always_compensates(
    tmp_path: Path,
    monkeypatch,
    failure_point: str,
    expected_delete_milestone: str,
) -> None:
    token = "5647382910abcdef"  # secret-scan: allow

    class Operations:
        def __init__(self):
            self.node = None
            self.state = None
            self.break_calls = 0

        def prepare(self, scope, rows):
            del rows
            self.node = drill.GraphNode(
                key=f"{scope.prefix}/metadata/root.json",
                kind="metadata",
                source_version_id="source-root",
                etag='"root"',
                size=100,
                sha256="a" * 64,
                depth=0,
            )
            self.state = drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id=self.node.source_version_id,
                size=self.node.size,
                sha256=self.node.sha256,
            )
            return drill.TableCapture(
                bucket="private-bucket",
                table_uuid="table-uuid",
                metadata_location=f"s3://private-bucket/{self.node.key}",
                snapshot_id=42,
                schema_sha256="b" * 64,
                row_count=3,
                rows_sha256="c" * 64,
                nodes=(self.node,),
            )

        def current_state(self, node):
            assert node == self.node
            return self.state

        def delete_current(self, node):
            assert node == self.node
            self.state = drill.ObjectState(
                exists=False,
                delete_marker=True,
                version_id="marker-root",
            )
            return drill.DeleteResult(delete_marker=True, version_id="marker-root")

        def assert_table_unreadable(self, manifest):
            del manifest
            self.break_calls += 1

        def restore(self, node):
            assert node == self.node
            self.state = drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id="restored-root",
                size=node.size,
                sha256=node.sha256,
            )
            return self.state

        def validate(self, manifest):
            table = manifest["table"]
            graph = manifest["graph"]
            return drill.ValidationResult(
                table_uuid=table["tableUuid"],
                metadata_location=table["metadataLocation"],
                snapshot_id=table["snapshotId"],
                logical_graph_sha256=graph["logicalSha256"],
                row_count=table["rowCount"],
                rows_sha256=table["rowsSha256"],
            )

    operations = Operations()
    prepared = drill.prepare_drill(
        operations=operations,
        evidence_root=tmp_path / ".recovery" / "iceberg",
        token_factory=lambda: token,
    )
    manifest_path = Path(prepared["manifest"])
    real_persist = drill._persist_damage_marker
    failed_once = False

    def fail_selected_write(path, marker):
        nonlocal failed_once
        milestones = marker.get("milestones")
        nodes = marker.get("nodes")
        node_deleted = (
            isinstance(nodes, list)
            and len(nodes) == 1
            and isinstance(nodes[0], dict)
            and nodes[0].get("phase") == "deleted"
        )
        deletes_complete = isinstance(milestones, dict) and milestones.get("deletes") == "complete"
        should_fail = (failure_point == "node-deleted" and node_deleted) or (
            failure_point == "deletes-complete" and deletes_complete
        )
        if not failed_once and should_fail:
            failed_once = True
            raise OSError("simulated private journal failure")
        real_persist(path, marker)

    monkeypatch.setattr(drill, "_persist_damage_marker", fail_selected_write)

    with pytest.raises(drill.RecoveryStageError) as failure:
        drill.execute_drill(
            operations=operations,
            manifest_path=manifest_path,
            expected_sha256=prepared["manifestSha256"],
        )
    assert failure.value.stage == "damage-journal"
    assert failed_once
    assert operations.break_calls == 0
    assert operations.state.exists
    assert operations.state.version_id == "restored-root"
    marker = json.loads((manifest_path.parent / "damage-started.json").read_text())
    assert marker["milestones"]["deletes"] == expected_delete_milestone
    assert marker["milestones"]["breakProof"] == "pending"
    assert marker["milestones"]["restoration"] == "complete"
    assert marker["nodes"][0]["phase"] == "promoted"


def test_restore_journal_refuses_unknown_marker_or_same_bytes_version(tmp_path: Path) -> None:
    token = "1122334455667788"  # secret-scan: allow
    scope = drill._scope(token)
    node = drill.GraphNode(
        key=f"{scope.prefix}/metadata/root.json",
        kind="metadata",
        source_version_id="source-root",
        etag='"root"',
        size=100,
        sha256="a" * 64,
        depth=0,
    )

    class UnknownMarkerOperations:
        def current_state(self, candidate):
            assert candidate == node
            return drill.ObjectState(
                exists=False,
                delete_marker=True,
                version_id="unknown-marker",
            )

        def restore(self, candidate):
            raise AssertionError(f"unknown marker was overwritten: {candidate}")

    marker = drill._initial_damage_marker(
        scope=scope,
        manifest_sha256="b" * 64,
        nodes=(node,),
    )
    marker["nodes"][0]["phase"] = "deleted"
    marker["nodes"][0]["deleteMarkerVersionId"] = "owned-marker"
    marker_path = tmp_path / "damage-started.json"
    drill._atomic_private_write(marker_path, drill._canonical_json(marker))
    with pytest.raises(drill.DrillError, match="unknown delete marker"):
        drill._restore_damaged(
            UnknownMarkerOperations(),
            (node,),
            marker,
            marker_path,
        )

    class UnknownSameBytesOperations:
        def current_state(self, candidate):
            assert candidate == node
            return drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id="unknown-same-bytes",
                size=node.size,
                sha256=node.sha256,
            )

        def restore(self, candidate):
            raise AssertionError(f"unknown current object was overwritten: {candidate}")

    pending = drill._initial_damage_marker(
        scope=scope,
        manifest_sha256="b" * 64,
        nodes=(node,),
    )
    with pytest.raises(drill.DrillError, match="unknown current version"):
        drill._restore_damaged(
            UnknownSameBytesOperations(),
            (node,),
            pending,
            marker_path,
        )


def test_delete_failure_restores_every_observed_damaged_key(tmp_path: Path) -> None:
    token = "0011223344556677"  # secret-scan: allow

    class Operations:
        def __init__(self):
            self.nodes = ()
            self.states = {}
            self.calls = []

        def prepare(self, scope, rows):
            del rows
            self.nodes = (
                drill.GraphNode(
                    key=f"{scope.prefix}/metadata/root.json",
                    kind="metadata",
                    source_version_id="source-root",
                    etag='"root"',
                    size=100,
                    sha256="a" * 64,
                    depth=0,
                ),
                drill.GraphNode(
                    key=f"{scope.prefix}/data/rows.parquet",
                    kind="data",
                    source_version_id="source-data",
                    etag='"data"',
                    size=200,
                    sha256="b" * 64,
                    depth=3,
                ),
            )
            self.states = {
                node.key: drill.ObjectState(
                    exists=True,
                    delete_marker=False,
                    version_id=node.source_version_id,
                    size=node.size,
                    sha256=node.sha256,
                )
                for node in self.nodes
            }
            return drill.TableCapture(
                bucket="private-bucket",
                table_uuid="table-uuid",
                metadata_location=f"s3://private-bucket/{self.nodes[0].key}",
                snapshot_id=42,
                schema_sha256="c" * 64,
                row_count=3,
                rows_sha256="d" * 64,
                nodes=self.nodes,
            )

        def current_state(self, node):
            return self.states[node.key]

        def delete_current(self, node):
            self.calls.append(("delete", node.kind))
            marker = f"marker-{node.kind}"
            self.states[node.key] = drill.ObjectState(
                exists=False,
                delete_marker=True,
                version_id=marker,
            )
            if node.kind == "metadata":
                raise RuntimeError("lost response after remote delete")
            return drill.DeleteResult(delete_marker=True, version_id=marker)

        def assert_table_unreadable(self, manifest):
            raise AssertionError(f"unexpected unreadable check: {manifest}")

        def restore(self, node):
            self.calls.append(("restore", node.kind))
            state = drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id=f"restored-{node.kind}",
                size=node.size,
                sha256=node.sha256,
            )
            self.states[node.key] = state
            return state

        def validate(self, manifest):
            self.calls.append(("validate", manifest["scope"]["table"]))
            table = manifest["table"]
            graph = manifest["graph"]
            return drill.ValidationResult(
                table_uuid=table["tableUuid"],
                metadata_location=table["metadataLocation"],
                snapshot_id=table["snapshotId"],
                logical_graph_sha256=graph["logicalSha256"],
                row_count=table["rowCount"],
                rows_sha256=table["rowsSha256"],
            )

    operations = Operations()
    prepared = drill.prepare_drill(
        operations=operations,
        evidence_root=tmp_path / ".recovery" / "iceberg",
        token_factory=lambda: token,
    )

    with pytest.raises(drill.RecoveryStageError) as failure:
        drill.execute_drill(
            operations=operations,
            manifest_path=Path(prepared["manifest"]),
            expected_sha256=prepared["manifestSha256"],
        )
    assert failure.value.stage == "delete"
    assert failure.value.error_kind == "unclassified"

    assert operations.calls == [
        ("validate", f"events_{token}"),
        ("delete", "data"),
        ("delete", "metadata"),
        ("restore", "data"),
        ("restore", "metadata"),
    ]
    for node in operations.nodes:
        state = operations.states[node.key]
        assert state.exists
        assert not state.delete_marker
        assert state.sha256 == node.sha256


def test_bucket_preflight_requires_exact_two_deny_root_exception_policy() -> None:
    root_arn = "arn:aws:iam::123456789012:root"
    bucket_arn = "arn:aws:s3:::private-bucket"
    exact_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DenyNonRootVersionDeletion",
                "Effect": "Deny",
                "Principal": {"AWS": "*"},
                "Action": "s3:DeleteObjectVersion",
                "Resource": f"{bucket_arn}/*",
                "Condition": {"ArnNotEquals": {"aws:PrincipalArn": root_arn}},
            },
            {
                "Sid": "DenyNonRootProtectionChanges",
                "Effect": "Deny",
                "Principal": {"AWS": "*"},
                "Action": [
                    "s3:PutBucketVersioning",
                    "s3:PutLifecycleConfiguration",
                    "s3:PutBucketPolicy",
                    "s3:DeleteBucketPolicy",
                ],
                "Resource": bucket_arn,
                "Condition": {"ArnNotEquals": {"aws:PrincipalArn": root_arn}},
            },
        ],
    }

    def responses(policy):
        return iter(
            (
                {"LocationConstraint": "us-west-1"},
                {"Status": "Enabled"},
                {
                    "Rules": [
                        {
                            "ID": "expire-noncurrent-object-versions-after-30-days",
                            "Status": "Enabled",
                            "Filter": {"Prefix": ""},
                            "NoncurrentVersionExpiration": {"NoncurrentDays": 30},
                        }
                    ]
                },
                {"Policy": json.dumps(policy)},
            )
        )

    calls = []
    accepted = responses(exact_policy)

    def accepted_runner(command, **kwargs):
        calls.append(tuple(command))
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(next(accepted)), stderr="")

    store = drill.AwsCliVersionStore(
        bucket="private-bucket",
        prefix="integration/recovery/0123456789abcdef/warehouse",
        region="us-west-1",
        environ={"AWS_PROFILE": "recovery"},
        runner=accepted_runner,
    )
    store.verify_bucket_protection(root_arn=root_arn)
    assert [command[2] for command in calls] == [
        "get-bucket-location",
        "get-bucket-versioning",
        "get-bucket-lifecycle-configuration",
        "get-bucket-policy",
    ]

    drifted_policy = json.loads(json.dumps(exact_policy))
    drifted_policy["Statement"][1]["Action"].remove("s3:DeleteBucketPolicy")
    drifted = responses(drifted_policy)

    def drifted_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(next(drifted)), stderr="")

    drifted_store = drill.AwsCliVersionStore(
        bucket="private-bucket",
        prefix="integration/recovery/0123456789abcdef/warehouse",
        region="us-west-1",
        environ={"AWS_PROFILE": "recovery"},
        runner=drifted_runner,
    )
    with pytest.raises(drill.DrillError, match="bucket policy"):
        drifted_store.verify_bucket_protection(root_arn=root_arn)


def test_polaris_gateway_rejects_redirect_without_reading_response_body() -> None:
    class Response:
        status = 302

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            raise AssertionError(f"redirect body must not be read: {size}")

    class Opener:
        def open(self, request, timeout):
            del request, timeout
            return Response()

    config = drill.RuntimeConfig(
        bucket="private-bucket",
        region="us-west-1",
        polaris_url="http://127.0.0.1:8181",
        polaris_client_id="client",
        polaris_client_secret="secret",
        storage_role_arn="arn:aws:iam::123456789012:role/storage-role",
    )
    gateway = drill.PolarisGateway(config=config, opener=Opener())

    with pytest.raises(drill.DrillError, match="redirect"):
        gateway._bounded_json(drill.Request("http://127.0.0.1:8181/private"))


def test_polaris_catalog_request_forces_finite_timeout_and_refuses_redirects() -> None:
    calls: list[dict[str, object]] = []

    class Response:
        status_code = 200

        def close(self) -> None:
            raise AssertionError("successful response must remain open")

    def request(**kwargs: object) -> Response:
        calls.append(dict(kwargs))
        return Response()

    response = drill.PolarisGateway._catalog_request(
        request,
        "GET",
        "http://127.0.0.1:8181/api/catalog/v1/config",
        timeout=None,
        allow_redirects=True,
    )

    assert isinstance(response, Response)
    assert calls == [
        {
            "method": "GET",
            "url": "http://127.0.0.1:8181/api/catalog/v1/config",
            "timeout": drill._POLARIS_REQUEST_TIMEOUT_SECONDS,
            "allow_redirects": False,
        }
    ]


def test_polaris_catalog_fingerprint_uses_direct_v1_7_catalog_response() -> None:
    token = "0123456789abcdef"  # secret-scan: allow
    scope = drill._scope(token)
    role_arn = "arn:aws:iam::123456789012:role/storage-role"
    config = drill.RuntimeConfig(
        bucket="private-bucket",
        region="us-west-1",
        polaris_url="http://127.0.0.1:8181",
        polaris_client_id="client",
        polaris_client_secret="secret",
        storage_role_arn=role_arn,
    )
    gateway = drill.PolarisGateway(config=config)
    warehouse = f"s3://private-bucket/{scope.prefix}"
    properties = {
        "default-base-location": warehouse,
        "management-default": "retained-in-fingerprint",
    }
    response = {
        "name": scope.catalog,
        "type": "INTERNAL",
        "properties": properties,
        "storageConfigInfo": {
            "storageType": "S3",
            "allowedLocations": [warehouse],
            "roleArn": role_arn,
        },
    }
    gateway._token = lambda: "token"
    gateway._management = lambda **kwargs: response

    expected = {
        "name": scope.catalog,
        "type": "INTERNAL",
        "propertiesSha256": hashlib.sha256(drill._canonical_json(properties)).hexdigest(),
        "defaultBaseLocation": warehouse,
        "storageType": "S3",
        "allowedLocations": [warehouse],
        "storageRoleSha256": hashlib.sha256(role_arn.encode()).hexdigest(),
    }

    assert (
        gateway.catalog_fingerprint(scope)
        == hashlib.sha256(drill._canonical_json(expected)).hexdigest()
    )


def test_identity_relationship_accepts_one_same_account_non_root_operator() -> None:
    operator = drill.CallerIdentity(
        account="123456789012",
        arn="arn:aws:iam::123456789012:user/operator",
        digest="a" * 64,
    )
    storage_role = "arn:aws:iam::123456789012:role/storage-role"

    assert (
        drill._require_identity_relationship(
            identity=operator,
            storage_role_arn=storage_role,
        )
        == "arn:aws:iam::123456789012:root"
    )

    cross_account_operator = drill.CallerIdentity(
        account="210987654321",
        arn="arn:aws:iam::210987654321:user/operator",
        digest="b" * 64,
    )
    with pytest.raises(drill.DrillError, match="do not align"):
        drill._require_identity_relationship(
            identity=cross_account_operator,
            storage_role_arn=storage_role,
        )


def test_assumed_role_identity_digest_is_stable_across_session_refresh() -> None:
    account = "123456789012"
    role_arn = f"arn:aws:iam::{account}:role/path/storage-role"
    expected_digest = hashlib.sha256(
        drill._canonical_json({"account": account, "arn": role_arn})
    ).hexdigest()

    def verify(session_name):
        def runner(command, **kwargs):
            assert kwargs["env"]["AWS_ACCESS_KEY_ID"] == "A" * 20
            response = {
                "Account": account,
                "Arn": f"arn:aws:sts::{account}:assumed-role/path/storage-role/{session_name}",
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(response), "")

        return drill._verify_non_root_identity(
            environ={
                "AWS_ACCESS_KEY_ID": "A" * 20,
                "AWS_SECRET_ACCESS_KEY": "s" * 40,
                "AWS_SESSION_TOKEN": "temporary-session-token",  # secret-scan: allow
            },
            expected_sha256=expected_digest,
            region="us-west-1",
            runner=runner,
        )

    first = verify("first-session")
    refreshed = verify("refreshed-session")

    assert first.authorization_principal == role_arn
    assert refreshed.authorization_principal == role_arn
    assert first.digest == refreshed.digest == expected_digest


def test_live_aws_verifies_and_reuses_one_exported_credential_set(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = drill.RecoverySettings(
        bucket="private-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/storage-role",
        profile="operator",
        identity_sha256="a" * 64,
        run_secret="synthetic-run-secret-placeholder",  # secret-scan: allow
    )
    credentials = drill.AwsCredentials("A" * 20, "s" * 40, "temporary-session-token")
    calls = []

    def export(*, environ):
        calls.append(("export", dict(environ)))
        return credentials

    def verify(*, environ, expected_sha256, region):
        calls.append(("verify", dict(environ), expected_sha256, region))
        return drill.CallerIdentity(
            "123456789012",
            "arn:aws:iam::123456789012:user/operator",
            "a" * 64,
        )

    class Store:
        def __init__(self, **kwargs):
            self.environment = dict(kwargs["environ"])
            calls.append(("store", self.environment, kwargs["expected_owner"]))

        def verify_bucket_protection(self, *, root_arn):
            calls.append(("protection", root_arn))

    monkeypatch.setattr(drill.os, "environ", {"HOME": "/private/home", "PATH": "/bin"})
    monkeypatch.setattr(drill, "_verify_non_root_identity", verify)
    monkeypatch.setattr(drill, "AwsCliVersionStore", Store)

    result = drill._verify_live_aws(
        settings=settings,
        scope=drill._scope("0123456789abcdef"),
        temp_root=tmp_path,
        credential_exporter=export,
    )

    assert calls[0][0] == "export"
    assert calls[0][1]["AWS_PROFILE"] == "operator"
    verified_environment = calls[1][1]
    assert "AWS_PROFILE" not in verified_environment
    assert verified_environment["AWS_ACCESS_KEY_ID"] == credentials.access_key_id
    assert calls[2] == ("store", verified_environment, "123456789012")
    assert calls[3] == ("protection", "arn:aws:iam::123456789012:root")
    assert result.environment == verified_environment
    assert result.credentials is credentials
    assert result.store.environment == verified_environment


def test_parent_sdk_environment_disables_ambient_aws_credentials_and_proxies() -> None:
    environment = {
        "HOME": "/private/home",
        "AWS_ACCESS_KEY_ID": "ambient",
        "AWS_SECRET_ACCESS_KEY": "ambient-secret",  # secret-scan: allow
        "AWS_SESSION_TOKEN": "ambient-token",  # secret-scan: allow
        "AWS_PROFILE": "root-profile",
        "AWS_WEB_IDENTITY_TOKEN_FILE": "/private/token",  # secret-scan: allow
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/credentials",  # secret-scan: allow
        "BOTO_CONFIG": "/private/legacy-boto.cfg",
        "HTTPS_PROXY": "https://proxy.invalid",
        "http_proxy": "http://proxy.invalid",
        "DATABOX_POLARIS_CLIENT_SECRET": "catalog-secret",  # secret-scan: allow
    }

    drill._isolate_parent_aws_environment(environment, region="us-west-1")

    assert environment["AWS_CONFIG_FILE"] == os.devnull
    assert environment["AWS_SHARED_CREDENTIALS_FILE"] == os.devnull
    assert environment["AWS_EC2_METADATA_DISABLED"] == "true"
    assert environment["BOTO_CONFIG"] == os.devnull
    assert environment["AWS_REGION"] == "us-west-1"
    assert environment["AWS_DEFAULT_REGION"] == "us-west-1"
    assert environment["NO_PROXY"] == "127.0.0.1,localhost,::1"
    assert environment["no_proxy"] == "127.0.0.1,localhost,::1"
    assert environment["DATABOX_POLARIS_CLIENT_SECRET"] == "catalog-secret"
    assert not any(
        key in environment
        for key in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_PROFILE",
            "AWS_WEB_IDENTITY_TOKEN_FILE",
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
            "HTTPS_PROXY",
            "http_proxy",
        )
    )


def test_profile_environment_strips_inherited_aws_credential_sources() -> None:
    result = drill._profile_environment(
        {
            "HOME": "/private/home",
            "PATH": "/private/bin",
            "LANG": "en_US.UTF-8",
            "AWS_ACCESS_KEY_ID": "inherited-key",  # secret-scan: allow
            "AWS_SECRET_ACCESS_KEY": "inherited-secret",  # secret-scan: allow
            "AWS_SESSION_TOKEN": "inherited-token",  # secret-scan: allow
            "AWS_PROFILE": "wrong-profile",
            "AWS_DEFAULT_PROFILE": "wrong-default",
            "AWS_WEB_IDENTITY_TOKEN_FILE": "/private/token",  # secret-scan: allow
            "AWS_ROLE_ARN": "inherited-role",
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/credentials",  # secret-scan: allow
            "AWS_CONTAINER_AUTHORIZATION_TOKEN": "inherited-container-token",  # secret-scan: allow
            "AWS_SHARED_CREDENTIALS_FILE": "/private/alternate-credentials",  # secret-scan: allow
            "AWS_CONFIG_FILE": "/private/alternate-config",
        },
        profile="approved-profile",
        region="us-west-1",
    )

    assert result == {
        "HOME": "/private/home",
        "PATH": "/private/bin",
        "LANG": "en_US.UTF-8",
        "AWS_PROFILE": "approved-profile",
        "AWS_REGION": "us-west-1",
        "AWS_DEFAULT_REGION": "us-west-1",
        "AWS_EC2_METADATA_DISABLED": "true",
    }


def test_aws_version_listing_paginates_and_filters_to_the_exact_key() -> None:
    key = "integration/recovery/0123456789abcdef/warehouse/metadata/root.json"
    calls = []
    responses = iter(
        (
            {
                "IsTruncated": True,
                "NextKeyMarker": key,
                "NextVersionIdMarker": "next-version",
                "Versions": [
                    {
                        "Key": key,
                        "VersionId": "version-two",
                        "IsLatest": False,
                        "ETag": '"etag-two"',
                        "Size": 22,
                    },
                    {
                        "Key": key + ".sibling",
                        "VersionId": "wrong-key",
                        "IsLatest": False,
                        "ETag": '"wrong"',
                        "Size": 99,
                    },
                ],
                "DeleteMarkers": [
                    {
                        "Key": key,
                        "VersionId": "delete-marker",
                        "IsLatest": True,
                    }
                ],
            },
            {
                "IsTruncated": False,
                "Versions": [
                    {
                        "Key": key,
                        "VersionId": "version-one",
                        "IsLatest": False,
                        "ETag": '"etag-one"',
                        "Size": 11,
                    }
                ],
                "DeleteMarkers": [],
            },
        )
    )

    def runner(command, **kwargs):
        calls.append((tuple(command), kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(next(responses)),
            stderr="",
        )

    store = drill.AwsCliVersionStore(
        bucket="private-bucket",
        prefix="integration/recovery/0123456789abcdef/warehouse",
        region="us-west-1",
        environ={"AWS_ACCESS_KEY_ID": "private"},
        runner=runner,
    )

    assert store.list_versions(key) == (
        drill.VersionEntry(
            key=key,
            version_id="version-two",
            latest=False,
            delete_marker=False,
            etag='"etag-two"',
            size=22,
        ),
        drill.VersionEntry(
            key=key,
            version_id="delete-marker",
            latest=True,
            delete_marker=True,
        ),
        drill.VersionEntry(
            key=key,
            version_id="version-one",
            latest=False,
            delete_marker=False,
            etag='"etag-one"',
            size=11,
        ),
    )
    assert calls[0] == (
        (
            "aws",
            "s3api",
            "list-object-versions",
            "--bucket",
            "private-bucket",
            "--prefix",
            key,
            "--max-keys",
            "1000",
            "--no-paginate",
            "--region",
            "us-west-1",
            "--output",
            "json",
            "--no-cli-pager",
        ),
        {
            "env": {"AWS_ACCESS_KEY_ID": "private"},
            "text": True,
            "capture_output": True,
            "check": False,
        },
    )
    second_command = calls[1][0]
    marker_index = second_command.index("--key-marker")
    assert second_command[marker_index : marker_index + 4] == (
        "--key-marker",
        key,
        "--version-id-marker",
        "next-version",
    )


def test_aws_canary_prefix_validation_rejects_foreign_keys() -> None:
    prefix = "integration/recovery/0123456789abcdef/stage1/warehouse"
    canary = f"{prefix}/capability-canary.bin"

    def runner(command, **kwargs):
        del kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "IsTruncated": False,
                    "Versions": [
                        {"Key": canary},
                        {"Key": f"{prefix}/foreign.bin"},
                    ],
                    "DeleteMarkers": [],
                }
            ),
            stderr="",
        )

    store = drill.AwsCliVersionStore(
        bucket="private-bucket",
        prefix=prefix,
        region="us-west-1",
        environ={"AWS_ACCESS_KEY_ID": "private"},
        expected_owner="123456789012",
        runner=runner,
    )

    with pytest.raises(drill.DrillError, match="unexpected key"):
        store.verify_only_key(canary)


def test_aws_put_canary_uses_raw_streaming_blob_path(tmp_path: Path) -> None:
    prefix = "integration/recovery/0123456789abcdef/stage1/warehouse"
    key = f"{prefix}/capability-canary.bin"
    payload = b"canary\n"
    commands = []

    def runner(command, **kwargs):
        del kwargs
        commands.append(tuple(command))
        operation = command[2]
        if operation == "put-object":
            body = command[command.index("--body") + 1]
            body_path = Path(body)
            assert body_path.is_file()
            assert body_path.read_bytes() == payload
            response = {"VersionId": "canary-version", "ETag": '"canary-etag"'}
        elif operation == "list-object-versions":
            response = {
                "IsTruncated": False,
                "Versions": [
                    {
                        "Key": key,
                        "VersionId": "canary-version",
                        "IsLatest": True,
                        "ETag": '"canary-etag"',
                        "Size": len(payload),
                    }
                ],
                "DeleteMarkers": [],
            }
        elif operation == "head-object":
            response = {
                "VersionId": "canary-version",
                "ContentLength": len(payload),
                "ETag": '"canary-etag"',
            }
        elif operation == "get-object":
            Path(command[-1]).write_bytes(payload)
            response = {"VersionId": "canary-version"}
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(response),
            stderr="",
        )

    store = drill.AwsCliVersionStore(
        bucket="private-bucket",
        prefix=prefix,
        region="us-west-1",
        environ={"AWS_ACCESS_KEY_ID": "private"},
        expected_owner="123456789012",
        temp_root=tmp_path,
        runner=runner,
    )

    node = store.put_canary(key, payload)

    assert node.source_version_id == "canary-version"
    put_command = next(command for command in commands if command[2] == "put-object")
    body = put_command[put_command.index("--body") + 1]
    assert not body.startswith(("file://", "fileb://"))
    assert not Path(body).exists()
    assert list(tmp_path.iterdir()) == []


def test_aws_cli_error_retains_only_sanitized_category(tmp_path: Path) -> None:
    private_detail = "arn:aws:iam::123456789012:user/private on private-key"

    def runner(command, **kwargs):
        del kwargs
        return subprocess.CompletedProcess(
            command,
            255,
            stdout="",
            stderr=(
                "An error occurred (AccessDenied) when calling the PutObject operation: "
                + private_detail
            ),
        )

    store = drill.AwsCliVersionStore(
        bucket="private-bucket",
        prefix="integration/recovery/0123456789abcdef/stage1/warehouse",
        region="us-west-1",
        environ={"AWS_ACCESS_KEY_ID": "private"},
        runner=runner,
    )

    with pytest.raises(drill.AwsCliOperationError) as captured:
        store._run_json(["aws", "s3api", "put-object"])

    assert captured.value.error_kind == "aws-accessdenied"
    assert private_detail not in str(captured.value)
    assert (
        drill._aws_cli_error_kind("Error parsing parameter '--body': private path")
        == "aws-parameter-parse"
    )
    with pytest.raises(drill.SeedStageError) as staged:
        drill._seed_stage("canary-put", lambda: store._run_json(["aws", "s3api", "put-object"]))
    assert staged.value.stage == "canary-put"
    assert staged.value.error_kind == "aws-accessdenied"
    private = tmp_path / "run"
    private.mkdir(mode=0o700)
    receipt = drill._write_seed_failure_receipt(
        plan_path=private / "seed-a.plan.json",
        plan_sha256="a" * 64,
        error=staged.value,
    )
    value = json.loads(receipt.read_text())
    assert value["errorKind"] == "aws-accessdenied"
    assert private_detail not in receipt.read_text()


def test_seed_stage_retains_only_pyiceberg_exception_category(tmp_path: Path) -> None:
    private_detail = "private response with account, bucket, and object key"

    def fail() -> None:
        raise BadRequestError(private_detail)

    with pytest.raises(drill.SeedStageError) as captured:
        drill._seed_stage("table-create", fail)

    assert captured.value.error_kind == "pyiceberg-bad-request-error"
    assert private_detail not in str(captured.value)
    private = tmp_path / "run"
    private.mkdir(mode=0o700)
    receipt = drill._write_seed_failure_receipt(
        plan_path=private / "seed-a.plan.json",
        plan_sha256="a" * 64,
        error=captured.value,
    )
    value = json.loads(receipt.read_text())
    assert value["errorKind"] == "pyiceberg-bad-request-error"
    assert private_detail not in receipt.read_text()


def test_seed_stage_retains_only_structured_polaris_error_type(tmp_path: Path) -> None:
    private_detail = "private principal, account, bucket, role, and object location"

    def fail() -> None:
        raise ForbiddenError(f"StorageIntegrationException: {private_detail}")

    with pytest.raises(drill.SeedStageError) as captured:
        drill._seed_stage("table-create", fail)

    assert captured.value.error_kind == ("pyiceberg-forbidden-error-storage-integration-exception")
    assert private_detail not in str(captured.value)
    private = tmp_path / "run"
    private.mkdir(mode=0o700)
    receipt = drill._write_seed_failure_receipt(
        plan_path=private / "seed-a.plan.json",
        plan_sha256="a" * 64,
        error=captured.value,
    )
    value = json.loads(receipt.read_text())
    assert value["errorKind"] == ("pyiceberg-forbidden-error-storage-integration-exception")
    assert private_detail not in receipt.read_text()


def test_aws_delete_is_ordinary_current_delete_and_requires_marker_response() -> None:
    key = "integration/recovery/0123456789abcdef/warehouse/data/rows.parquet"
    calls = []

    def runner(command, **kwargs):
        calls.append((tuple(command), kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"DeleteMarker": True, "VersionId": "new-marker"}),
            stderr="",
        )

    node = drill.GraphNode(
        key=key,
        kind="data",
        source_version_id="source-version",
        etag='"etag"',
        size=3,
        sha256="a" * 64,
        depth=3,
    )
    store = drill.AwsCliVersionStore(
        bucket="private-bucket",
        prefix="integration/recovery/0123456789abcdef/warehouse",
        region="us-west-1",
        environ={"AWS_PROFILE": "writer"},
        expected_owner="123456789012",
        runner=runner,
    )

    assert store.delete_current(node) == drill.DeleteResult(
        delete_marker=True,
        version_id="new-marker",
    )
    command = calls[0][0]
    assert command[:9] == (
        "aws",
        "s3api",
        "delete-object",
        "--bucket",
        "private-bucket",
        "--key",
        key,
        "--region",
        "us-west-1",
    )
    assert "--version-id" not in command
    owner_index = command.index("--expected-bucket-owner")
    assert command[owner_index + 1] == "123456789012"


def test_aws_restore_encodes_exact_source_version_and_verifies_current_bytes(
    tmp_path: Path,
) -> None:
    key = "integration/recovery/0123456789abcdef/warehouse/data/a b+?.parquet"
    payload = b"abc"
    calls = []

    def runner(command, **kwargs):
        calls.append((tuple(command), kwargs))
        operation = command[2]
        if operation == "copy-object":
            response = {
                "VersionId": "new-version",
                "CopyObjectResult": {"ETag": '"new-etag"'},
            }
        elif operation == "list-object-versions":
            response = {
                "IsTruncated": False,
                "Versions": [
                    {
                        "Key": key,
                        "VersionId": "new-version",
                        "IsLatest": True,
                        "ETag": '"new-etag"',
                        "Size": len(payload),
                    },
                    {
                        "Key": key,
                        "VersionId": "old+/=version",
                        "IsLatest": False,
                        "ETag": '"old-etag"',
                        "Size": len(payload),
                    },
                ],
                "DeleteMarkers": [],
            }
        elif operation == "head-object":
            response = {
                "VersionId": "new-version",
                "ContentLength": len(payload),
                "ETag": '"new-etag"',
            }
        elif operation == "get-object":
            output_path = Path(command[-1])
            output_path.write_bytes(payload)
            response = {"VersionId": "new-version"}
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(response),
            stderr="",
        )

    node = drill.GraphNode(
        key=key,
        kind="data",
        source_version_id="old+/=version",
        etag='"old-etag"',
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        depth=3,
    )
    store = drill.AwsCliVersionStore(
        bucket="private-bucket",
        prefix="integration/recovery/0123456789abcdef/warehouse",
        region="us-west-1",
        environ={"AWS_ACCESS_KEY_ID": "private"},
        expected_owner="123456789012",
        temp_root=tmp_path,
        runner=runner,
    )

    assert store.restore(node) == drill.ObjectState(
        exists=True,
        delete_marker=False,
        version_id="new-version",
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    copy_command = next(command for command, _kwargs in calls if command[2] == "copy-object")
    copy_source_index = copy_command.index("--copy-source")
    assert copy_command[copy_source_index + 1] == (
        "private-bucket/integration/recovery/0123456789abcdef/warehouse/"
        "data/a%20b%2B%3F.parquet?versionId=old%2B%2F%3Dversion"
    )
    match_index = copy_command.index("--copy-source-if-match")
    assert copy_command[match_index + 1] == '"old-etag"'
    source_owner_index = copy_command.index("--expected-source-bucket-owner")
    assert copy_command[source_owner_index + 1] == "123456789012"
    destination_owner_index = copy_command.index("--expected-bucket-owner")
    assert copy_command[destination_owner_index + 1] == "123456789012"
    assert list(tmp_path.iterdir()) == []


def test_pyiceberg_graph_follows_real_point_a_metadata_references(tmp_path: Path) -> None:
    catalog = load_catalog(
        "recovery_fixture",
        type="in-memory",
        warehouse=f"file://{tmp_path / 'warehouse'}",
    )
    catalog.create_namespace("drill_fixture")
    schema = Schema(
        NestedField(1, "event_id", LongType(), required=True),
        NestedField(2, "generation", StringType(), required=True),
        NestedField(3, "value", LongType(), required=True),
    )
    table = catalog.create_table(
        "drill_fixture.events",
        schema=schema,
        properties={"format-version": "2"},
    )
    table.append(
        pa.Table.from_pylist(
            [
                {"event_id": 1, "generation": "point-a", "value": 10},
                {"event_id": 2, "generation": "point-a", "value": 20},
                {"event_id": 3, "generation": "point-a", "value": 30},
            ],
            schema=schema.as_arrow(),
        )
    )
    table.refresh()

    graph = drill.capture_iceberg_graph(table)

    by_kind = {}
    for item in graph:
        by_kind.setdefault(item.kind, set()).add(item.location)
    snapshot = table.current_snapshot()
    assert snapshot is not None
    assert by_kind["metadata"] == {table.metadata_location}
    assert by_kind["manifest-list"] == {snapshot.manifest_list}
    assert by_kind["manifest"] == {
        manifest.manifest_path for manifest in snapshot.manifests(table.io)
    }
    assert by_kind["data"] == {task.file.file_path for task in table.scan().plan_files()}
    assert len(by_kind["metadata-ancestor"]) == 1
    assert len(graph) == len({item.location for item in graph})
    depths = {item.kind: item.depth for item in graph}
    assert depths["metadata"] == 0
    assert depths["metadata-ancestor"] == 1
    assert depths["manifest-list"] == 1
    assert depths["manifest"] == 2
    assert depths["data"] == 3


def test_main_dispatches_mutation_free_prepare_and_prints_only_bounded_result(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    settings = drill.RecoverySettings(
        bucket="private-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/storage-role",
        profile="operator",
        identity_sha256="a" * 64,
        run_secret="synthetic-run-secret-placeholder",  # secret-scan: allow
    )
    observed = {}

    def fake_prepare_seed_plan(*, settings, evidence_root, token_factory):
        observed["settings"] = settings
        observed["evidence_root"] = evidence_root
        observed["token"] = token_factory()
        return {
            "status": "planned",
            "planType": "seed-a",
            "runId": "0123456789abcdef",
            "planSha256": "a" * 64,
        }

    monkeypatch.setattr(drill, "prepare_seed_plan", fake_prepare_seed_plan)

    assert (
        drill.main(
            ["prepare", "--evidence-root", str(tmp_path)],
            settings=settings,
            token_factory=lambda: "0123456789abcdef",
        )
        == 0
    )
    assert observed == {
        "settings": settings,
        "evidence_root": tmp_path,
        "token": "0123456789abcdef",  # secret-scan: allow
    }
    assert json.loads(capsys.readouterr().out) == {
        "status": "planned",
        "planType": "seed-a",
        "runId": "0123456789abcdef",
        "planSha256": "a" * 64,
    }


def test_main_writes_private_seed_failure_receipt(tmp_path: Path, monkeypatch, capsys) -> None:
    tmp_path.chmod(0o700)
    plan_path = tmp_path / "seed-a.plan.json"
    payload = drill._canonical_json({"planType": "seed-a"})
    plan_path.write_bytes(payload)
    plan_path.chmod(0o600)
    plan_sha256 = hashlib.sha256(payload).hexdigest()
    settings = drill.RecoverySettings(
        bucket="private-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/storage-role",
        profile="operator",
        identity_sha256="a" * 64,
        run_secret="synthetic-run-secret-placeholder",  # secret-scan: allow
    )

    def fail_seed(**kwargs):
        del kwargs
        raise drill.SeedStageError("polaris-readiness")

    monkeypatch.setattr(drill, "execute_seed_plan", fail_seed)

    assert (
        drill.main(
            ["execute", "--manifest", str(plan_path), "--sha256", plan_sha256],
            settings=settings,
        )
        == 1
    )

    receipt_path = tmp_path / "seed-a-failure.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt == {
        "schemaVersion": 2,
        "receiptType": "seed-a-failure",
        "planSha256": plan_sha256,
        "errorStage": "polaris-readiness",
        "errorKind": "unclassified",
        "recordedAt": receipt["recordedAt"],
    }
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", receipt["recordedAt"])
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600
    output = capsys.readouterr()
    assert output.out == ""
    assert "refused" in output.err
    assert "polaris-readiness" not in output.err


def test_execute_recovery_plan_persists_primary_and_containment_failures(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    tmp_path.chmod(0o700)
    plan_path = tmp_path / "manifest.json"
    payload = drill._canonical_json({"planType": "recovery-a"})
    plan_path.write_bytes(payload)
    plan_path.chmod(0o600)
    plan_sha256 = hashlib.sha256(payload).hexdigest()
    parent_sha256 = "b" * 64
    retained_sha256 = "c" * 64
    scope = drill._scope("1234abcdef567890")
    resources = drill._stack_resources(scope)
    runtime = drill.RuntimeBinding("rev", "1" * 64, "python", "iceberg", "arrow", "2" * 64)
    node = drill.GraphNode(
        key=f"{scope.prefix}/metadata/root.json",
        kind="metadata",
        source_version_id="source-root",
        etag='"root"',
        size=100,
        sha256="d" * 64,
        depth=0,
    )
    capture = drill.TableCapture(
        bucket="private-bucket",
        table_uuid="table-uuid",
        metadata_location=f"s3://private-bucket/{node.key}",
        snapshot_id=42,
        schema_sha256="e" * 64,
        row_count=3,
        rows_sha256="f" * 64,
        nodes=(node,),
    )
    manifest = {
        "schemaVersion": 4,
        "planType": "recovery-a",
        "parentSeedPlanSha256": parent_sha256,
        "stack": {"resources": resources},
        "retainedResourcesSha256": retained_sha256,
        "catalogFingerprintSha256": "3" * 64,
    }
    seed_plan = {"stack": manifest["stack"]}
    monkeypatch.setattr(
        drill,
        "_manifest_contract",
        lambda *args, **kwargs: (manifest, scope, capture, plan_sha256, runtime),
    )
    monkeypatch.setattr(
        drill,
        "_seed_plan_contract",
        lambda *args, **kwargs: (seed_plan, scope, {}, runtime, parent_sha256),
    )
    monkeypatch.setattr(drill, "_settings_match_seed_plan", lambda *args: None)
    monkeypatch.setattr(drill, "_verify_pinned_docker", lambda *args, **kwargs: None)
    monkeypatch.setattr(drill, "_recovery_plan_expired", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        drill,
        "execute_drill",
        lambda **kwargs: (_ for _ in ()).throw(
            drill.RecoveryStageError("break-proof", error_kind="pyiceberg-file-not-found-error")
        ),
    )
    calls = []

    class FailingContainmentStack:
        def __init__(self, **kwargs):
            del kwargs

        def use_retained_resources(self, expected):
            assert expected == retained_sha256

        def start(self, *args, **kwargs):
            del args, kwargs
            return "http://127.0.0.1:32124"

        def close(self):
            calls.append("close")
            raise drill.AwsCliOperationError("docker-close-failed")

    class Gateway:
        def catalog_fingerprint(self, requested_scope):
            assert requested_scope == scope
            return "3" * 64

    class Operations:
        gateway = None

        def _verify_capability_canary(self):
            raise AssertionError("execute_drill was replaced before the canary")

    aws = drill.VerifiedAwsContext(
        environment={},
        identity=drill.CallerIdentity(
            "123456789012",
            "arn:aws:iam::123456789012:user/operator",
            "4" * 64,
        ),
        credentials=drill.AwsCredentials("A" * 20, "s" * 40, "temporary-token"),
        store=object(),
    )
    settings = drill.RecoverySettings(
        bucket="private-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/storage-role",
        profile="operator",
        identity_sha256="5" * 64,
        run_secret="synthetic-run-secret-placeholder",  # secret-scan: allow
    )
    original_execute = drill.execute_recovery_plan

    def execute_with_fakes(**kwargs):
        return original_execute(
            **kwargs,
            live_aws_factory=lambda **ignored: aws,
            stack_factory=FailingContainmentStack,
            operations_factory=lambda **ignored: Operations(),
            gateway_waiter=lambda config: Gateway(),
        )

    monkeypatch.setattr(drill, "execute_recovery_plan", execute_with_fakes)

    assert (
        drill.main(
            ["execute", "--manifest", str(plan_path), "--sha256", plan_sha256],
            settings=settings,
        )
        == 1
    )
    assert calls == ["close"]
    receipt = json.loads((tmp_path / "recovery-a-failure-001.json").read_text())
    assert receipt["errorStage"] == "break-proof"
    assert receipt["errorKind"] == "pyiceberg-file-not-found-error"
    assert receipt["containment"] == {
        "status": "failed",
        "errorKind": "docker-close-failed",
    }
    assert receipt["damageMarker"] == {"present": False}
    assert "refused" in capsys.readouterr().err


def test_main_writes_sanitized_private_recovery_failure_receipt(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    tmp_path.chmod(0o700)
    plan_path = tmp_path / "manifest.json"
    payload = drill._canonical_json({"planType": "recovery-a"})
    plan_path.write_bytes(payload)
    plan_path.chmod(0o600)
    plan_sha256 = hashlib.sha256(payload).hexdigest()
    settings = drill.RecoverySettings(
        bucket="private-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/storage-role",
        profile="operator",
        identity_sha256="a" * 64,
        run_secret="synthetic-run-secret-placeholder",  # secret-scan: allow
    )
    sensitive_message = "private identifier and object key must not be retained"

    def fail_recovery(**kwargs):
        del kwargs
        error = drill.DrillError(sensitive_message)
        error.stage = "private-identifier"
        error.error_kind = "private-object-key"
        raise error

    monkeypatch.setattr(drill, "execute_recovery_plan", fail_recovery)

    for _attempt in range(2):
        assert (
            drill.main(
                ["execute", "--manifest", str(plan_path), "--sha256", plan_sha256],
                settings=settings,
            )
            == 1
        )

    receipts = [
        json.loads((tmp_path / f"recovery-a-failure-{index:03d}.json").read_text())
        for index in (1, 2)
    ]
    for index, receipt in enumerate(receipts, start=1):
        assert receipt == {
            "schemaVersion": 2,
            "receiptType": "recovery-a-failure",
            "invocation": index,
            "planSha256": plan_sha256,
            "errorStage": "preflight",
            "errorKind": "unclassified",
            "containment": {"status": "not-recorded", "errorKind": None},
            "damageMarker": {"present": False},
            "recordedAt": receipt["recordedAt"],
        }
    for receipt_path in sorted(tmp_path.glob("recovery-a-failure-*.json")):
        assert sensitive_message not in receipt_path.read_text()
        assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.count("refused") == 2
    assert sensitive_message not in output.err


def test_main_records_recovery_stage_and_damage_summary_without_private_values(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    tmp_path.chmod(0o700)
    plan_path = tmp_path / "manifest.json"
    payload = drill._canonical_json({"planType": "recovery-a"})
    plan_path.write_bytes(payload)
    plan_path.chmod(0o600)
    plan_sha256 = hashlib.sha256(payload).hexdigest()
    scope = drill._scope("abcdef0123456789")
    node = drill.GraphNode(
        key=f"{scope.prefix}/metadata/private.json",
        kind="metadata",
        source_version_id="private-source-version",
        etag='"private-etag"',
        size=100,
        sha256="a" * 64,
        depth=0,
    )
    marker = drill._initial_damage_marker(
        scope=scope,
        manifest_sha256=plan_sha256,
        nodes=(node,),
    )
    marker["milestones"].update(
        {
            "deletes": "complete",
            "breakProof": "failed",
            "restoration": "complete",
            "containment": "passed",
        }
    )
    marker["nodes"][0].update(
        {
            "phase": "promoted",
            "deleteMarkerVersionId": "private-delete-marker",
            "promotedVersionId": "private-promoted-version",
        }
    )
    drill._atomic_private_write(tmp_path / "damage-started.json", drill._canonical_json(marker))
    settings = drill.RecoverySettings(
        bucket="private-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/storage-role",
        profile="operator",
        identity_sha256="a" * 64,
        run_secret="synthetic-run-secret-placeholder",  # secret-scan: allow
    )

    def fail_recovery(**kwargs):
        del kwargs
        raise drill.RecoveryStageError("break-proof", error_kind="pyiceberg-file-not-found-error")

    monkeypatch.setattr(drill, "execute_recovery_plan", fail_recovery)

    assert (
        drill.main(
            ["execute", "--manifest", str(plan_path), "--sha256", plan_sha256],
            settings=settings,
        )
        == 1
    )

    receipt_path = tmp_path / "recovery-a-failure-001.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["schemaVersion"] == 2
    assert receipt["invocation"] == 1
    assert receipt["errorStage"] == "break-proof"
    assert receipt["errorKind"] == "pyiceberg-file-not-found-error"
    assert receipt["containment"] == {"status": "passed", "errorKind": None}
    assert receipt["damageMarker"] == {
        "present": True,
        "readable": True,
        "schemaVersion": 2,
        "nodeCount": 1,
        "nodePhaseCounts": {
            "pending": 0,
            "delete-intent": 0,
            "deleted": 0,
            "promotion-intent": 0,
            "promoted": 1,
        },
        "milestones": {
            "deletes": "complete",
            "breakProof": "failed",
            "restoration": "complete",
            "finalValidation": "pending",
            "containment": "passed",
        },
    }
    serialized = receipt_path.read_text()
    for private_value in (
        node.key,
        node.source_version_id,
        "private-etag",
        "private-delete-marker",
        "private-promoted-version",
    ):
        assert private_value not in serialized
    assert capsys.readouterr().out == ""


def test_diagnose_recovery_plan_is_read_only_and_reports_legacy_unknowns(
    tmp_path: Path, monkeypatch
) -> None:
    run_id = "abcdef0123456789"
    scope = drill._scope(run_id)
    run_root = tmp_path / run_id
    run_root.mkdir(mode=0o700)
    manifest_path = run_root / "manifest.json"
    manifest_path.write_bytes(b"private manifest")
    manifest_path.chmod(0o600)
    manifest_sha256 = "a" * 64
    parent_sha256 = "b" * 64
    retained_sha256 = "c" * 64
    node = drill.GraphNode(
        key=f"{scope.prefix}/metadata/root.json",
        kind="metadata",
        source_version_id="source-root",
        etag='"root"',
        size=100,
        sha256="d" * 64,
        depth=0,
    )
    capture = drill.TableCapture(
        bucket="private-bucket",
        table_uuid="table-uuid",
        metadata_location=f"s3://private-bucket/{node.key}",
        snapshot_id=42,
        schema_sha256="e" * 64,
        row_count=3,
        rows_sha256="f" * 64,
        nodes=(node,),
    )
    runtime = drill.RuntimeBinding("rev", "1" * 64, "python", "iceberg", "arrow", "2" * 64)
    resources = drill._stack_resources(scope)
    manifest = {
        "schemaVersion": 4,
        "planType": "recovery-a",
        "parentSeedPlanSha256": parent_sha256,
        "stack": {"resources": resources},
        "retainedResourcesSha256": retained_sha256,
    }
    seed_plan = {"stack": {"resources": resources}}
    marker = {
        "schemaVersion": 1,
        "manifestSha256": manifest_sha256,
        "runId": run_id,
        "nodes": [
            {
                "key": node.key,
                "sourceVersionId": node.source_version_id,
                "phase": "promoted",
                "deleteMarkerVersionId": "marker-root",
                "promotedVersionId": "restored-root",
            }
        ],
    }
    drill._atomic_private_write(run_root / "damage-started.json", drill._canonical_json(marker))
    monkeypatch.setattr(
        drill,
        "_manifest_contract",
        lambda *args, **kwargs: (manifest, scope, capture, manifest_sha256, runtime),
    )
    monkeypatch.setattr(
        drill,
        "_seed_plan_contract",
        lambda *args, **kwargs: (seed_plan, scope, {}, runtime, parent_sha256),
    )
    monkeypatch.setattr(drill, "_settings_match_seed_plan", lambda *args: None)
    monkeypatch.setattr(drill, "_verify_pinned_docker", lambda *args, **kwargs: None)
    calls = []

    class ReadOnlyStore:
        def current_state(self, candidate):
            assert candidate == node
            calls.append("current-state")
            return drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id="restored-root",
                size=node.size,
                sha256=node.sha256,
            )

        def exact_source_state(self, candidate):
            assert candidate == node
            calls.append("historical-source")
            return drill.ObjectState(
                exists=True,
                delete_marker=False,
                version_id=node.source_version_id,
                size=node.size,
                sha256=node.sha256,
            )

        def prefix_keys(self):
            calls.append("prefix-keys")
            return frozenset({node.key, f"{scope.prefix}/capability-canary.bin"})

    aws = drill.VerifiedAwsContext(
        environment={},
        identity=drill.CallerIdentity(
            "123456789012",
            "arn:aws:iam::123456789012:user/operator",
            "3" * 64,
        ),
        credentials=drill.AwsCredentials("A" * 20, "s" * 40, "temporary-token"),
        store=ReadOnlyStore(),
    )

    class ReadOnlyStack:
        def __init__(self, **kwargs):
            assert kwargs["resources"] == resources
            calls.append("stack-constructed")

        def retained_resources_sha256(self):
            calls.append("retained-resources")
            return retained_sha256

    settings = drill.RecoverySettings(
        bucket="private-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/storage-role",
        profile="operator",
        identity_sha256="4" * 64,
        run_secret="synthetic-run-secret-placeholder",  # secret-scan: allow
    )
    result = drill.diagnose_recovery_plan(
        settings=settings,
        plan_path=manifest_path,
        expected_sha256=manifest_sha256,
        live_aws_factory=lambda **kwargs: aws,
        stack_factory=ReadOnlyStack,
    )

    assert result == {
        "status": "diagnosed-object-state",
        "planType": "recovery-a",
        "objectRestorationState": "verified",
        "nodeCount": 1,
        "currentPromotionsMatch": 1,
        "historicalSourcesMatch": 1,
        "retainedResourcesMatch": True,
        "prefixInventoryMatch": True,
        "breakProofState": "unknown",
        "finalValidationState": "unknown",
        "catalogReadbackState": "not-checked",
        "queryReadbackState": "not-checked",
    }
    assert calls == [
        "stack-constructed",
        "retained-resources",
        "current-state",
        "historical-source",
        "prefix-keys",
    ]


def test_main_dispatches_read_only_recovery_diagnosis(tmp_path: Path, monkeypatch, capsys) -> None:
    tmp_path.chmod(0o700)
    plan_path = tmp_path / "manifest.json"
    payload = drill._canonical_json({"planType": "recovery-a"})
    plan_path.write_bytes(payload)
    plan_path.chmod(0o600)
    plan_sha256 = hashlib.sha256(payload).hexdigest()
    settings = drill.RecoverySettings(
        bucket="private-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/storage-role",
        profile="operator",
        identity_sha256="a" * 64,
        run_secret="synthetic-run-secret-placeholder",  # secret-scan: allow
    )
    observed = {}

    def diagnose(**kwargs):
        observed.update(kwargs)
        return {
            "status": "diagnosed-object-state",
            "planType": "recovery-a",
            "objectRestorationState": "verified",
            "nodeCount": 5,
            "currentPromotionsMatch": 5,
            "historicalSourcesMatch": 5,
            "retainedResourcesMatch": True,
            "prefixInventoryMatch": True,
            "breakProofState": "unknown",
            "finalValidationState": "unknown",
            "catalogReadbackState": "not-checked",
            "queryReadbackState": "not-checked",
        }

    monkeypatch.setattr(drill, "diagnose_recovery_plan", diagnose)

    assert (
        drill.main(
            ["diagnose", "--manifest", str(plan_path), "--sha256", plan_sha256],
            settings=settings,
        )
        == 0
    )
    assert observed["settings"] == settings
    assert observed["plan_path"] == plan_path
    assert observed["expected_sha256"] == plan_sha256
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "diagnosed-object-state"
    assert output["nodeCount"] == 5
    assert set(output) == {
        "status",
        "planType",
        "objectRestorationState",
        "nodeCount",
        "currentPromotionsMatch",
        "historicalSourcesMatch",
        "retainedResourcesMatch",
        "prefixInventoryMatch",
        "breakProofState",
        "finalValidationState",
        "catalogReadbackState",
        "queryReadbackState",
    }


def test_live_main_rejects_custom_evidence_root_before_planning(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    settings = drill.RecoverySettings(
        bucket="private-bucket",
        region="us-west-1",
        storage_role_arn="arn:aws:iam::123456789012:role/storage-role",
        profile="operator",
        identity_sha256="a" * 64,
        run_secret="synthetic-run-secret-placeholder",  # secret-scan: allow
    )
    monkeypatch.setattr(
        drill.RecoverySettings,
        "load",
        classmethod(lambda cls: settings),
    )

    def unexpected_plan(**kwargs):
        raise AssertionError(f"unexpected Seed-A plan: {kwargs}")

    monkeypatch.setattr(drill, "prepare_seed_plan", unexpected_plan)

    assert drill.main(["prepare", "--evidence-root", str(tmp_path)]) == 1
    assert "refused" in capsys.readouterr().err


def test_private_recovery_evidence_root_is_ignored() -> None:
    assert "/.recovery/" in GITIGNORE.read_text().splitlines()


def test_runbook_keeps_real_drill_manual_approved_and_non_purging() -> None:
    runbook = RUNBOOK.read_text()
    section = runbook.split("## Real Iceberg object-recovery drill", 1)[1].split("\n## ", 1)[0]
    assert "task iceberg:recovery-drill:prepare" in section
    assert "task iceberg:recovery-drill:execute" in section
    assert "DATABOX_RECOVERY_PROFILE" in section
    assert "DATABOX_RECOVERY_IDENTITY_SHA256" in section
    assert ') + "\\n"' in section
    assert ') + "\\\\n"' not in section
    documented_payload = (
        json.dumps(
            {"account": "123456789012", "arn": "arn:aws:iam::123456789012:user/operator"},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    assert hashlib.sha256(documented_payload.encode()).hexdigest() == drill._identity_sha256(
        "123456789012", "arn:aws:iam::123456789012:user/operator"
    )
    assert "separate-principal privilege" in section
    assert "out of scope" in section
    assert "separate explicit approval" in section
    assert "restore-only" in section
    assert "never calls `DeleteObjectVersion`" in section
    assert "does not prove catalog PITR" in section
    assert "Cleanup is separate" in section


def test_taskfile_has_only_manual_prepare_and_execute_wrappers() -> None:
    taskfile = TASKFILE.read_text()
    assert "  iceberg:recovery-drill:prepare:" in taskfile
    assert "  iceberg:recovery-drill:execute:" in taskfile
    assert taskfile.count("scripts/platform/iceberg_recovery_drill.py") == 2
    assert (
        '"{{.VENV_DIR}}/bin/python scripts/platform/iceberg_recovery_drill.py prepare '
        '{{.CLI_ARGS}}"'
    ) in taskfile
    assert (
        '"{{.VENV_DIR}}/bin/python scripts/platform/iceberg_recovery_drill.py execute '
        '{{.CLI_ARGS}}"'
    ) in taskfile
