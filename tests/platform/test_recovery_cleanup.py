from __future__ import annotations

import hashlib
import json
import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = spec_from_file_location(
        "recovery_cleanup", ROOT / "scripts/platform/recovery_cleanup.py"
    )
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cleanup = _load()


def _entry(
    kind: str,
    version: str,
    *,
    latest: bool,
    key: str = "integration/recovery/0123456789abcdef/stage1/warehouse/data.bin",
    modified: str = "2026-01-01T00:00:00Z",
):
    record = {
        "Key": key,
        "VersionId": version,
        "IsLatest": latest,
        "LastModified": modified,
        "Owner": {"ID": "owner"},
    }
    if kind == "version":
        record.update({"ETag": '"etag"', "Size": 3, "StorageClass": "STANDARD"})
    return {"kind": kind, "record": record}


def test_generated_prefix_must_be_exact() -> None:
    run = "0123456789abcdef"
    expected = f"integration/recovery/{run}/stage1/warehouse/"
    assert cleanup._validate_generated_prefix(run, expected) == expected
    assert cleanup._validate_generated_prefix(run, expected.removesuffix("/")) == expected

    for invalid in (
        f"integration/recovery/{run}/stage1/warehouse-extra/",
        f"integration/recovery/{'f' * 16}/stage1/warehouse/",
        "warehouse/",
    ):
        with pytest.raises(cleanup.CleanupError):
            cleanup._validate_generated_prefix(run, invalid)


def test_version_inventory_uses_the_iam_bounded_max_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands = []

    def checked(command, *, env=None):
        commands.append(command)
        return json.dumps({"IsTruncated": False, "Versions": [], "DeleteMarkers": []})

    monkeypatch.setattr(cleanup, "_checked", checked)
    cleanup._timeline_inventory(
        "integration/recovery/0123456789abcdef/stage1/warehouse/",
        {
            "bucket": "private-bucket",
            "region": "us-east-1",
            "expectedOwner": "123456789012",
        },
        {},
    )
    assert "--max-keys" in commands[0]
    assert commands[0][commands[0].index("--max-keys") + 1] == "1000"


def test_ordinary_delete_command_never_selects_a_version() -> None:
    command = cleanup._aws_delete_command(
        "private-bucket", "private/key", "123456789012", "us-east-1"
    )
    assert command[:3] == ("aws", "s3api", "delete-object")
    assert "--version-id" not in command
    assert "delete-objects" not in command


def test_timeline_reconciliation_accepts_one_new_marker() -> None:
    old = _entry("version", "v1", latest=True)
    retained = json.loads(json.dumps(old))
    retained["record"]["IsLatest"] = False
    marker = _entry(
        "delete-marker",
        "m1",
        latest=True,
        modified="2026-01-01T00:01:00Z",
    )

    assert cleanup._reconcile_timeline([old], [marker, retained]) == "m1"


@pytest.mark.parametrize(
    "after",
    [
        [_entry("delete-marker", "m1", latest=True)],
        [
            _entry("delete-marker", "m1", latest=True),
            _entry("delete-marker", "m2", latest=False),
            _entry("version", "v1", latest=False),
        ],
        [
            _entry("delete-marker", "m1", latest=True),
            _entry("version", "v1", latest=False, modified="changed"),
        ],
    ],
)
def test_timeline_reconciliation_rejects_drift(after) -> None:
    with pytest.raises(cleanup.CleanupError):
        cleanup._reconcile_timeline([_entry("version", "v1", latest=True)], after)


def test_prefix_reconciliation_rejects_unrelated_key_drift() -> None:
    key = _entry("version", "v1", latest=True)["record"]["Key"]
    other_key = key.replace("data.bin", "other.bin")
    before = {
        key: [_entry("version", "v1", latest=True)],
        other_key: [_entry("version", "other-v1", latest=True, key=other_key)],
    }
    retained = json.loads(json.dumps(before[key][0]))
    retained["record"]["IsLatest"] = False
    marker = _entry("delete-marker", "m1", latest=True)
    after = {
        key: [marker, retained],
        other_key: [_entry("version", "other-v1", latest=True, key=other_key, modified="drift")],
    }
    with pytest.raises(cleanup.CleanupError, match="unrelated"):
        cleanup._reconcile_inventory(before, after, key)


def test_stage2b_nested_report_schema_is_supported() -> None:
    resources = {
        "network": "databox_polaris_recovery_drill_abcdefghijkl",
        "volume": "databox_polaris_recovery_drill_abcdefghijkl",
        "postgres_container": "databox-polaris-recovery-drill-postgres-abcdefghijkl",
        "polaris_container": "databox-polaris-recovery-drill-polaris-abcdefghijkl",
        "preserved": True,
    }
    nested = {"report": {"status": "pass", "resources": resources}}
    assert cleanup._stage2b_report(nested) == nested["report"]
    assert cleanup._stage2b_report(nested)["resources"] is resources


def test_stable_container_fingerprint_excludes_runtime_health_drift() -> None:
    inspected = {
        "Id": "a" * 64,
        "Name": "/recovery-postgres",
        "Image": "sha256:" + "b" * 64,
        "Config": {"Image": "postgres:pinned", "Labels": {"owned": "true"}},
        "HostConfig": {"NetworkMode": "recovery-net", "LogConfig": {"Type": "json-file"}},
        "Mounts": [{"Type": "volume", "Name": "recovery-data", "Destination": "/data", "RW": True}],
        "State": {"Running": True, "Health": {"Status": "starting", "Log": ["private"]}},
        "NetworkSettings": {
            "IPAddress": "172.20.0.2",
            "Networks": {"recovery-net": {"NetworkID": "d" * 64}},
        },
    }
    changed_runtime = json.loads(json.dumps(inspected))
    changed_runtime["State"] = {
        "Running": True,
        "Health": {"Status": "healthy", "Log": ["different"]},
    }
    changed_runtime["NetworkSettings"]["IPAddress"] = "172.20.0.9"
    assert cleanup._docker_fingerprint("container", inspected) == cleanup._docker_fingerprint(
        "container", changed_runtime
    )

    changed_mount = json.loads(json.dumps(changed_runtime))
    changed_mount["Mounts"][0]["Destination"] = "/different"
    assert cleanup._docker_fingerprint("container", inspected) != cleanup._docker_fingerprint(
        "container", changed_mount
    )
    changed_labels = json.loads(json.dumps(changed_runtime))
    changed_labels["Config"]["Labels"]["owned"] = "false"
    assert cleanup._docker_fingerprint("container", inspected) != cleanup._docker_fingerprint(
        "container", changed_labels
    )
    changed_network = json.loads(json.dumps(changed_runtime))
    changed_network["NetworkSettings"]["Networks"] = {"unexpected": {"NetworkID": "c" * 64}}
    assert cleanup._docker_fingerprint("container", inspected) != cleanup._docker_fingerprint(
        "container", changed_network
    )


def test_discovery_supports_partial_legacy_and_stage2a_resources() -> None:
    cases = (
        ("network", "databox-stage2a-0123456789abcdef", "stage2a"),
        ("volume", "databox_stage2a_diag_0123456789abcdef", "stage2a"),
        ("container", "databox-polaris-recovery-probe-20260908_214022", "stage2b"),
        ("network", "databox_polaris_recovery_validation_20260908_214022", "stage2b"),
        ("volume", "databox_polaris_recovery_20260905_162513_retry2", "stage2b"),
    )
    for kind, name, stage in cases:
        spec = cleanup._discovered_spec(kind, name)
        assert spec is not None and spec[0] == stage

    stage2a_volume = cleanup._discovered_spec("volume", "databox_stage2a_diag_0123456789abcdef")
    probe = cleanup._discovered_spec("container", "databox-polaris-recovery-probe-20260908_214022")
    assert stage2a_volume is not None and stage2a_volume[1] == {cleanup._STAGE_LABEL: "2a"}
    assert probe is not None and {cleanup._RUNTIME_LABEL: "true"} in probe[1]
    assert {cleanup._VALIDATION_LABEL: "postgres"} in probe[1]
    assert cleanup._postgres_recovery_container("databox-polaris-recovery-probe-20260908_214022")
    with pytest.raises(cleanup.CleanupError, match="unknown name"):
        cleanup._discovered_spec("volume", "databox_polaris_recovery_unknown")


def test_legacy_runtime_container_allows_only_default_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resource = {
        "kind": "container",
        "name": "databox-polaris-recovery-postgres-20260908-214022",
        "stage": "stage2b",
        "id": "a" * 64,
        "group": "stage2b-legacy:20260908_214022",
    }
    inspected = {
        "Config": {"Labels": {cleanup._RUNTIME_LABEL: "true"}},
        "NetworkSettings": {"Networks": {"bridge": {"NetworkID": "b" * 64}}},
    }
    monkeypatch.setattr(cleanup, "_docker_inspect", lambda _kind, _name: inspected)
    cleanup._validate_attachments([resource])

    inspected["NetworkSettings"]["Networks"]["unexpected"] = {"NetworkID": "c" * 64}
    with pytest.raises(cleanup.CleanupError, match="network membership"):
        cleanup._validate_attachments([resource])


def test_network_and_volume_with_same_stage2b_name_merge_independently() -> None:
    shared = "databox_polaris_recovery_drill_abcdefghijkl"
    network = {
        "kind": "network",
        "name": shared,
        "stage": "stage2b",
        "id": "net",
        "inspectSha256": "a",
        "source": "evidence",
        "group": "stage2b:abcdefghijkl",
        "running": False,
    }
    volume = {
        "kind": "volume",
        "name": shared,
        "stage": "stage2b",
        "id": shared,
        "inspectSha256": "b",
        "source": "evidence",
        "group": "stage2b:abcdefghijkl",
        "running": False,
    }
    assert len(cleanup._merge_resources([network, volume], [network, volume])) == 2


def test_bucket_protection_uses_target_owner_root(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class Store:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def verify_bucket_protection(self, *, root_arn):
            captured["root_arn"] = root_arn

    monkeypatch.setattr(cleanup.ir, "AwsCliVersionStore", Store)
    settings = SimpleNamespace(storage_role_arn="arn:aws:iam::123456789012:role/recovery")
    target = {
        "bucket": "private-bucket",
        "region": "us-east-1",
        "expectedOwner": "123456789012",
    }
    cleanup._verify_bucket_protection(settings, target, {"AWS_REGION": "us-east-1"})
    assert captured["expected_owner"] == "123456789012"
    assert captured["root_arn"] == "arn:aws:iam::123456789012:root"


def test_execute_requires_exact_rederived_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace()
    derived_resources = [
        {
            "stage": "stage2a",
            "kind": "volume",
            "name": "owned-volume",
            "id": "owned-volume",
            "inspectSha256": "a" * 64,
            "source": "docker-discovery",
            "group": "stage2a:0123456789abcdef",
            "running": False,
        }
    ]
    monkeypatch.setattr(
        cleanup,
        "_inventory_sources",
        lambda _settings: ([{"path": "source", "sha256": "b" * 64}], derived_resources, []),
    )
    plan = {
        "sources": [{"path": "source", "sha256": "b" * 64}],
        "resources": derived_resources,
        "prefixes": [],
    }
    cleanup._require_evidence_derived_plan(plan, settings)

    malicious = json.loads(json.dumps(plan))
    malicious["resources"][0]["name"] = cleanup._ACTIVE[0]
    with pytest.raises(cleanup.CleanupError, match="authorized inventory"):
        cleanup._require_evidence_derived_plan(malicious, settings)


def test_docker_removal_commands_do_not_force() -> None:
    commands = (
        cleanup._docker_remove_command("container", "a" * 64, "container-name"),
        cleanup._docker_remove_command("network", "b" * 64, "network-name"),
        cleanup._docker_remove_command("volume", "volume-name", "volume-name"),
    )
    assert commands[0] == ("docker", "container", "rm", "a" * 64)
    assert commands[2] == ("docker", "volume", "rm", "volume-name")
    assert all("--force" not in command and "-f" not in command for command in commands)


def test_source_evidence_hash_drift_is_rejected(tmp_path: Path) -> None:
    evidence = tmp_path / ".recovery" / "iceberg" / "0123456789abcdef"
    evidence.mkdir(parents=True)
    source = evidence / "seed-a.plan.json"
    source.write_text("original")
    plan = {
        "sources": [
            {
                "path": str(source.relative_to(tmp_path)),
                "sha256": hashlib.sha256(b"original").hexdigest(),
            }
        ]
    }
    cleanup._verify_source_hashes(plan, root=tmp_path)
    source.write_text("drift")
    with pytest.raises(cleanup.CleanupError, match="changed"):
        cleanup._verify_source_hashes(plan, root=tmp_path)


def _private_plan(tmp_path: Path) -> tuple[Path, str]:
    run_dir = tmp_path / "0123456789abcdef"
    run_dir.mkdir(mode=0o700)
    path = run_dir / "plan.json"
    payload = cleanup._canonical(
        {"schemaVersion": 1, "status": "planned", "sources": [], "prefixes": [], "resources": []}
    )
    path.write_bytes(payload)
    os.chmod(path, 0o600)
    return path, hashlib.sha256(payload).hexdigest()


def test_plan_hash_and_terminal_replay_are_rejected(tmp_path: Path) -> None:
    path, digest = _private_plan(tmp_path)
    assert cleanup._read_execution_plan(path, digest, cleanup_root=tmp_path)["status"] == "planned"

    with pytest.raises(cleanup.CleanupError, match="approved hash"):
        cleanup._read_execution_plan(path, "0" * 64, cleanup_root=tmp_path)

    result = path.parent / "result.json"
    result.write_text("{}")
    os.chmod(result, 0o600)
    with pytest.raises(cleanup.CleanupError, match="consumed"):
        cleanup._read_execution_plan(path, digest, cleanup_root=tmp_path)


def test_public_summary_never_contains_private_identifiers() -> None:
    private_values = (
        "private-bucket",
        "integration/recovery/0123456789abcdef/stage1/warehouse/secret-key",
        "databox-secret-network",
        "a" * 64,
    )
    key = private_values[1]
    plan = {
        "target": {"bucket": private_values[0]},
        "resources": [{"name": private_values[2], "id": private_values[3]}],
        "prefixes": [
            {
                "prefix": key.rsplit("/", 1)[0] + "/",
                "timelines": {key: [_entry("version", "private-version", latest=True, key=key)]},
            }
        ],
    }
    rendered = json.dumps(cleanup._public_summary("planned", plan), sort_keys=True)
    assert json.loads(rendered) == {
        "status": "planned",
        "prefixCount": 1,
        "objectCount": 1,
        "resourceCount": 1,
    }
    assert all(value not in rendered for value in private_values)
