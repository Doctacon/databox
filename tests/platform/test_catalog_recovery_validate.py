import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts/platform/catalog_recovery_validate.py"


def _load_module():
    spec = spec_from_file_location("catalog_recovery_validate", SCRIPT)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = _load_module()


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.expected = None

    def inspect(self, expected):
        self.expected = tuple(expected)
        return self.response


class FakeArrow:
    def __init__(self, rows=1):
        self.num_rows = rows


class FakeScan:
    def __init__(self, *, rows=1, manifest_error=None, data_error=None):
        self.rows = rows
        self.manifest_error = manifest_error
        self.data_error = data_error

    def plan_files(self):
        if self.manifest_error:
            raise self.manifest_error
        return iter(())

    def to_arrow(self):
        if self.data_error:
            raise self.data_error
        return FakeArrow(self.rows)


class FakeTable:
    def __init__(self, *, snapshot_id=42, snapshot_error=None, scan=None):
        self.snapshot_id = snapshot_id
        self.snapshot_error = snapshot_error
        self.fake_scan = scan or FakeScan()

    def current_snapshot(self):
        if self.snapshot_error:
            raise self.snapshot_error
        if self.snapshot_id is None:
            return None
        return SimpleNamespace(snapshot_id=self.snapshot_id)

    def scan(self, *, limit):
        assert limit == 1
        return self.fake_scan


def load_response(secret="temporary-vended-value"):  # secret-scan: allow
    return {
        "metadata-location": "s3://warehouse/raw/table/metadata/v1.metadata.json",
        "metadata": {"current-snapshot-id": 42},
        "config": {"s3.region": "us-west-1"},
        "storage-credentials": [
            {
                "prefix": "s3://warehouse/raw/table",
                "config": {
                    "s3.access-key-id": "temporary-access",  # secret-scan: allow
                    "s3.secret-access-key": secret,
                    "s3.session-token": "temporary-token",  # secret-scan: allow
                },
            }
        ],
    }


def inventory(expected, *, extra=(), missing=(), loads=None):
    actual = (set(expected) - set(missing)) | set(extra)
    namespaces = sorted({item.split(".", 1)[0] for item in actual})
    tables = [
        {"namespace": [item.split(".", 1)[0]], "name": item.split(".", 1)[1]}
        for item in sorted(actual)
    ]
    return {
        "namespaces": [[namespace] for namespace in namespaces],
        "tables": tables,
        "loads": loads or {identifier: {"response": load_response()} for identifier in expected},
    }


def validate(response, table_loader=lambda _location, _properties: FakeTable()):
    return validator.validate_catalog(
        transport=FakeTransport(response),
        container="recovery-polaris",
        catalog="databox_lake",
        recovery_target="2026-09-08T21:40:22Z",
        source_revision="a" * 40,
        table_loader=table_loader,
    )


def test_source_revision_resolves_commit_and_requires_identical_registry(tmp_path):
    registry = tmp_path / "sources.py"
    registry.write_bytes(b"same registry\n")
    commit = "a" * 40
    responses = [
        subprocess.CompletedProcess([], 0, stdout=commit + "\n", stderr=""),
        subprocess.CompletedProcess([], 0, stdout=b"same registry\n", stderr=b""),
    ]
    with (
        patch.object(validator, "REGISTRY_PATH", registry),
        patch.object(validator.subprocess, "run", side_effect=responses) as run,
    ):
        assert validator._source_revision("e95b333") == commit
    assert run.call_args_list[0].args[0][-1] == "e95b333^{commit}"

    responses[1] = subprocess.CompletedProcess([], 0, stdout=b"different\n", stderr=b"")
    with (
        patch.object(validator, "REGISTRY_PATH", registry),
        patch.object(validator.subprocess, "run", side_effect=responses),
        pytest.raises(validator.ValidationError, match="differs"),
    ):
        validator._source_revision("e95b333")


def test_expected_inventory_is_exactly_registry_tables_plus_each_status_table():
    from databox.config.sources import SOURCES

    expected = validator.expected_registry_tables()
    direct = {
        f"{source.raw_catalog}.{table}"
        for source in SOURCES
        for table in (*source.raw_tables, "_dlt_load_status")
    }
    assert set(expected) == direct
    assert len(expected) == len(direct)


def test_malformed_or_overlong_observed_identifiers_fail_without_echoing_them():
    expected = validator.expected_registry_tables()
    response = inventory(expected)
    response["namespaces"].append(["x" * 129])
    response["tables"].append({"namespace": ["raw_gbif"], "name": "bad\nname"})

    report = validate(response)

    assert report["status"] == "fail"
    assert report["malformedObservedIdentifiers"] == 2
    assert "x" * 129 not in json.dumps(report)
    assert "bad\\nname" not in json.dumps(report)


def test_catalog_report_aggregates_missing_unexpected_and_unreadable_tables():
    expected = validator.expected_registry_tables()
    missing = expected[0]
    canonical_namespace = expected[0].split(".", 1)[0]
    extra = f"{canonical_namespace}.unregistered"
    loads = {identifier: {"response": load_response()} for identifier in expected}
    loads[expected[1]] = {"http_status": 404}
    response = inventory(expected, extra=(extra,), missing=(missing,), loads=loads)

    report = validate(response)

    assert report["status"] == "fail"
    assert report["missingTables"] == [missing]
    assert report["unexpectedTables"] == [extra]
    assert report["noncanonicalNamespaces"] == []
    assert report["warningCount"] == 0
    assert report["counts"]["failedTables"] == 1
    failed = {item["identifier"]: item["failures"] for item in report["tables"]}
    assert failed[expected[1]] == ("metadata_unreadable",)
    assert len(report["tables"]) == len(expected)


def test_noncanonical_namespaces_are_prominent_warnings_and_do_not_fail():
    expected = validator.expected_registry_tables()
    extra = ("dlt_polaris_probe.events", "raw_usfws.image_records")

    report = validate(inventory(expected, extra=extra))

    assert report["status"] == "pass"
    assert report["warningCount"] == 4
    assert report["noncanonicalNamespaces"] == ["dlt_polaris_probe", "raw_usfws"]
    assert report["noncanonicalTables"] == list(extra)
    assert report["unexpectedTables"] == []


def test_metadata_and_snapshot_failures_are_bounded_and_safe():
    secret = "must-never-appear"  # secret-scan: allow
    metadata = validator.validate_table(
        "raw_gbif.occurrences",
        load_response(secret),
        table_loader=lambda _location, _properties: (_ for _ in ()).throw(RuntimeError(secret)),
    )
    snapshot = validator.validate_table(
        "raw_gbif.occurrences",
        load_response(secret),
        table_loader=lambda _location, _properties: FakeTable(snapshot_id=None),
    )
    inaccessible_snapshot = validator.validate_table(
        "raw_gbif.occurrences",
        load_response(secret),
        table_loader=lambda _location, _properties: FakeTable(snapshot_error=RuntimeError(secret)),
    )

    rendered = json.dumps([metadata.__dict__, snapshot.__dict__, inaccessible_snapshot.__dict__])
    assert secret not in rendered
    assert metadata.failures == ("metadata_unreadable",)
    assert snapshot.metadata_readable
    assert snapshot.failures == ("current_snapshot_missing",)
    assert inaccessible_snapshot.failures == ("current_snapshot_unreadable",)


def test_matching_rest_and_s3_snapshot_ids_pass():
    outcome = validator.validate_table(
        "raw_gbif.occurrences",
        load_response(),
        table_loader=lambda _location, _properties: FakeTable(snapshot_id=42),
    )

    assert outcome.failures == ()
    assert outcome.current_snapshot_id == "42"


@pytest.mark.parametrize(
    ("metadata", "failure"),
    [
        ({}, "rest_snapshot_missing"),
        ({"current-snapshot-id": "42"}, "rest_snapshot_malformed"),
        ({"current-snapshot-id": 43}, "snapshot_divergent"),
    ],
)
def test_rest_snapshot_missing_malformed_or_divergent_fails_safely(metadata, failure):
    response = load_response("must-never-appear")  # secret-scan: allow
    response["metadata"] = metadata

    outcome = validator.validate_table(
        "raw_gbif.occurrences",
        response,
        table_loader=lambda _location, _properties: FakeTable(snapshot_id=42),
    )

    assert outcome.failures == (failure,)
    assert outcome.metadata_readable
    assert outcome.manifests_readable
    assert outcome.data_readable
    assert "must-never-appear" not in json.dumps(outcome.__dict__)


def test_manifest_and_data_failures_are_aggregated_by_stage_without_exception_text():
    secret = "must-never-appear"  # secret-scan: allow
    manifest = validator.validate_table(
        "raw_gbif.occurrences",
        load_response(),
        table_loader=lambda _location, _properties: FakeTable(
            scan=FakeScan(manifest_error=RuntimeError(secret))
        ),
    )
    data = validator.validate_table(
        "raw_gbif.occurrences",
        load_response(),
        table_loader=lambda _location, _properties: FakeTable(
            scan=FakeScan(data_error=RuntimeError(secret))
        ),
    )

    rendered = json.dumps([manifest.__dict__, data.__dict__])
    assert secret not in rendered
    assert manifest.failures == ("manifest_unreadable",)
    assert not manifest.manifests_readable
    assert data.failures == ("data_unreadable",)
    assert data.manifests_readable
    assert not data.data_readable


def test_empty_table_passes_after_snapshot_manifest_and_limit_one_read():
    outcome = validator.validate_table(
        "raw_gbif.occurrences",
        load_response(),
        table_loader=lambda _location, _properties: FakeTable(scan=FakeScan(rows=0)),
    )

    assert outcome.failures == ()
    assert outcome.metadata_readable
    assert outcome.manifests_readable
    assert outcome.data_readable
    assert outcome.sample_rows == 0


def test_vended_storage_credentials_are_given_to_static_table_only_in_memory():
    captured = {}

    def loader(location, properties):
        captured["location"] = location
        captured["properties"] = properties
        return FakeTable()

    outcome = validator.validate_table("raw_gbif.occurrences", load_response(), table_loader=loader)

    assert outcome.failures == ()
    expected_secret = "temporary-vended-value"  # secret-scan: allow
    assert captured["properties"]["s3.secret-access-key"] == expected_secret
    assert expected_secret not in json.dumps(outcome.__dict__)


def _identity(*, running=True, label="polaris", ports=None):
    return json.dumps(
        {
            "running": running,
            "labels": {validator.RECOVERY_LABEL: label},
            "portBindings": {} if ports is None else ports,
        }
    )


def test_helper_aggregates_all_per_table_request_or_parse_failures():
    helper = validator._CONTAINER_HELPER
    assert "except Exception:" in helper
    assert 'loaded_tables[identifier] = {"request_failed": True}' in helper


def test_docker_transport_requires_labeled_running_unexposed_container():
    for identity in (
        _identity(running=False),
        _identity(label="active"),
        _identity(ports={"8181/tcp": [{"HostPort": "18181"}]}),
        "not-json must-never-appear",
    ):

        def runner(command, identity=identity, **_kwargs):
            return subprocess.CompletedProcess(command, 0, stdout=identity, stderr="secret")

        transport = validator.DockerExecTransport(
            container="recovery-polaris", catalog="databox_lake", runner=runner
        )
        with pytest.raises(validator.ValidationError) as caught:
            transport.inspect(("raw_gbif.occurrences",))
        assert "must-never-appear" not in str(caught.value)
        assert "secret" not in str(caught.value)


def test_docker_transport_preflights_then_sends_only_safe_request_on_stdin():
    calls = []
    response = {"namespaces": [], "tables": [], "loads": {}}

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        stdout = _identity() if command[1] == "inspect" else json.dumps(response)
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    transport = validator.DockerExecTransport(
        container="recovery-polaris", catalog="databox_lake", runner=runner
    )
    assert transport.inspect(("raw_gbif.occurrences",)) == response

    command, kwargs = calls[1]
    assert command[:5] == ["docker", "exec", "-i", "recovery-polaris", "python3"]
    assert json.loads(kwargs["input"]) == {
        "catalog": "databox_lake",
        "expected": ["raw_gbif.occurrences"],
    }
    assert kwargs["capture_output"] is True


def test_main_emits_secret_free_bounded_json_and_nonzero_on_aggregate_failure(capsys):
    secret = "must-never-appear"  # secret-scan: allow
    expected = validator.expected_registry_tables()
    canonical_namespace = expected[0].split(".", 1)[0]
    response = inventory(expected, extra=(f"{canonical_namespace}.unregistered",))
    response["loads"][expected[0]] = {"response": load_response(secret)}

    with (
        patch.object(validator, "DockerExecTransport", return_value=FakeTransport(response)),
        patch.object(validator, "_source_revision", return_value="a" * 40),
        patch.object(validator.time, "monotonic", side_effect=[10.0, 12.5]),
        patch.object(validator.StaticTable, "from_metadata", return_value=FakeTable()),
    ):
        result = validator.main(
            [
                "--polaris-container",
                "recovery-polaris",
                "--catalog",
                "databox_lake",
                "--recovery-target",
                "2026-09-08T21:40:22Z",
                "--source-revision",
                "e95b333",
            ]
        )

    output = capsys.readouterr().out
    report = json.loads(output)
    assert result == 1
    assert report["status"] == "fail"
    assert report["sourceRevision"] == "a" * 40
    assert report["elapsedSeconds"] == 2.5
    assert secret not in output
    assert len(report["tables"]) == len(expected)
