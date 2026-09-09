import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
        git_revision="abc123",
        table_loader=table_loader,
    )


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


def test_catalog_report_aggregates_missing_unexpected_and_unreadable_tables():
    expected = validator.expected_registry_tables()
    missing = expected[0]
    extra = "raw_retired.unregistered"
    loads = {identifier: {"response": load_response()} for identifier in expected}
    loads[expected[1]] = {"http_status": 404}
    response = inventory(expected, extra=(extra,), missing=(missing,), loads=loads)

    report = validate(response)

    assert report["status"] == "fail"
    assert report["missingTables"] == [missing]
    assert report["unexpectedTables"] == [extra]
    assert report["unexpectedNamespaces"] == ["raw_retired"]
    assert report["counts"]["failedTables"] == 1
    failed = {item["identifier"]: item["failures"] for item in report["tables"]}
    assert failed[expected[1]] == ("metadata_unreadable",)
    assert len(report["tables"]) == len(expected)


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


def test_docker_transport_sends_only_safe_request_on_stdin_and_sanitizes_failure():
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="must-never-appear")

    transport = validator.DockerExecTransport(
        container="recovery-polaris", catalog="databox_lake", runner=runner
    )
    try:
        transport.inspect(("raw_gbif.occurrences",))
    except validator.ValidationError as error:
        message = str(error)
    else:
        raise AssertionError("expected failure")

    command, kwargs = calls[0]
    assert command[:5] == ["docker", "exec", "-i", "recovery-polaris", "python3"]
    assert json.loads(kwargs["input"]) == {
        "catalog": "databox_lake",
        "expected": ["raw_gbif.occurrences"],
    }
    assert "must-never-appear" not in message
    assert kwargs["capture_output"] is True


def test_main_emits_secret_free_bounded_json_and_nonzero_on_aggregate_failure(capsys):
    secret = "must-never-appear"  # secret-scan: allow
    expected = validator.expected_registry_tables()
    response = inventory(expected, extra=("raw_extra.table",))
    response["loads"][expected[0]] = {"response": load_response(secret)}

    with (
        patch.object(validator, "DockerExecTransport", return_value=FakeTransport(response)),
        patch.object(validator, "_git_revision", return_value="abc123"),
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
            ]
        )

    output = capsys.readouterr().out
    report = json.loads(output)
    assert result == 1
    assert report["status"] == "fail"
    assert secret not in output
    assert len(report["tables"]) == len(expected)
