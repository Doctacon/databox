#!/usr/bin/env python3
"""Read-only, registry-derived validation of an isolated restored Polaris catalog."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from databox.config.sources import SOURCES
from pyiceberg.table import StaticTable

STATUS_TABLE = "_dlt_load_status"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_MAX_IDENTIFIERS = 100

# Runs wholly inside the explicitly named no-port Polaris container. OAuth never
# leaves it; vended credentials cross only its captured pipe into PyIceberg process
# memory and are excluded from diagnostics and the operator-visible report.
_CONTAINER_HELPER = r"""
import json, os, sys, urllib.error, urllib.parse, urllib.request
cfg = json.load(sys.stdin)
base = "http://127.0.0.1:8181/api/catalog"
data = urllib.parse.urlencode({
    "grant_type": "client_credentials",
    "client_id": os.environ["DATABOX_POLARIS_CLIENT_ID"],
    "client_secret": os.environ["DATABOX_POLARIS_CLIENT_SECRET"],
    "scope": "PRINCIPAL_ROLE:ALL",
}).encode()
with urllib.request.urlopen(urllib.request.Request(base + "/v1/oauth/tokens", data=data)) as r:
    token = json.load(r)["access_token"]
headers = {"Authorization": "Bearer " + token, "Polaris-Realm": "POLARIS"}
def get(path, extra=None):
    request_headers = dict(headers)
    request_headers.update(extra or {})
    with urllib.request.urlopen(urllib.request.Request(base + path, headers=request_headers)) as r:
        return json.load(r)
def pages(path, key):
    found = []
    cursor = None
    while True:
        separator = "&" if "?" in path else "?"
        suffix = (
            separator + urllib.parse.urlencode({"pageToken": cursor}) if cursor else ""
        )
        response = get(path + suffix)
        found.extend(response.get(key, []))
        cursor = response.get("next-page-token")
        if not cursor:
            return found
catalog = urllib.parse.quote(cfg["catalog"], safe="")
namespaces = pages("/v1/" + catalog + "/namespaces", "namespaces")
tables = []
for parts in namespaces:
    encoded = urllib.parse.quote("\x1f".join(parts), safe="")
    tables.extend(pages("/v1/" + catalog + "/namespaces/" + encoded + "/tables", "identifiers"))
loaded_tables = {}
for identifier in cfg["expected"]:
    namespace, name = identifier.split(".", 1)
    encoded_namespace = urllib.parse.quote(namespace, safe="")
    encoded_name = urllib.parse.quote(name, safe="")
    try:
        loaded_tables[identifier] = {"response": get(
            "/v1/" + catalog + "/namespaces/" + encoded_namespace + "/tables/" + encoded_name,
            {"X-Iceberg-Access-Delegation": "vended-credentials"},
        )}
    except urllib.error.HTTPError as error:
        loaded_tables[identifier] = {"http_status": error.code}
print(json.dumps({"namespaces": namespaces, "tables": tables, "loads": loaded_tables}))
"""


class ValidationError(RuntimeError):
    """A bounded error safe to include in operator output."""


class RecoveryCatalogTransport(Protocol):
    def inspect(self, expected: Sequence[str]) -> Mapping[str, Any]: ...


class ReadableTable(Protocol):
    def current_snapshot(self) -> Any: ...

    def scan(self, *, limit: int) -> Any: ...


TableLoader = Callable[[str, Mapping[str, str]], ReadableTable]
Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class TableOutcome:
    identifier: str
    metadata_readable: bool = False
    current_snapshot_id: str | None = None
    manifests_readable: bool = False
    data_readable: bool = False
    sample_rows: int | None = None
    failures: tuple[str, ...] = ()


class DockerExecTransport:
    """Query only the named restored Polaris container through stdin/stdout pipes."""

    def __init__(
        self,
        *,
        container: str,
        catalog: str,
        runner: Runner = subprocess.run,
    ) -> None:
        if not _NAME.fullmatch(container):
            raise ValidationError("invalid restored Polaris container name")
        if not _NAME.fullmatch(catalog):
            raise ValidationError("invalid Polaris catalog name")
        self.container = container
        self.catalog = catalog
        self.runner = runner

    def inspect(self, expected: Sequence[str]) -> Mapping[str, Any]:
        request = json.dumps({"catalog": self.catalog, "expected": list(expected)})
        try:
            completed = self.runner(
                ["docker", "exec", "-i", self.container, "python3", "-c", _CONTAINER_HELPER],
                input=request,
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as error:
            raise ValidationError(
                "unable to invoke Docker for restored Polaris validation"
            ) from error
        if completed.returncode != 0:
            raise ValidationError("restored Polaris read-only request failed")
        try:
            response = json.loads(completed.stdout)
        except (json.JSONDecodeError, TypeError) as error:
            raise ValidationError(
                "restored Polaris returned an invalid validation response"
            ) from error
        if not isinstance(response, dict):
            raise ValidationError("restored Polaris returned an invalid validation response")
        return response


def expected_registry_tables() -> tuple[str, ...]:
    """Derive the complete validation inventory from the canonical registry."""
    return tuple(
        sorted(
            f"{source.raw_catalog}.{table}"
            for source in SOURCES
            for table in (*source.raw_tables, STATUS_TABLE)
        )
    )


def _static_table(metadata_location: str, properties: Mapping[str, str]) -> ReadableTable:
    return StaticTable.from_metadata(metadata_location, properties=dict(properties))


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items() if isinstance(item, str)}


def _table_access(load_response: object) -> tuple[str, dict[str, str]]:
    if not isinstance(load_response, dict):
        raise ValidationError("invalid table load response")
    location = load_response.get("metadata-location")
    if not isinstance(location, str) or not location.startswith("s3://"):
        raise ValidationError("table metadata location is absent or not S3")
    properties = _string_mapping(load_response.get("config"))
    storage = load_response.get("storage-credentials")
    if isinstance(storage, list):
        for entry in storage:
            if not isinstance(entry, dict):
                continue
            prefix = entry.get("prefix")
            if isinstance(prefix, str) and location.startswith(prefix):
                properties.update(_string_mapping(entry.get("config")))
                break
    return location, properties


def _snapshot_id(snapshot: object) -> str | None:
    value = getattr(snapshot, "snapshot_id", None)
    return str(value) if isinstance(value, int | str) else None


def _sample_row_count(value: object) -> int:
    rows = getattr(value, "num_rows", None)
    if not isinstance(rows, int):
        raise ValidationError("representative read returned an invalid row count")
    return rows


def validate_table(
    identifier: str,
    load: object,
    *,
    table_loader: TableLoader = _static_table,
) -> TableOutcome:
    """Validate one table while reducing all third-party errors to safe stage names."""
    failures: list[str] = []
    try:
        location, properties = _table_access(load)
        table = table_loader(location, properties)
    except Exception:  # Third-party errors can contain credential-bearing properties.
        return TableOutcome(identifier=identifier, failures=("metadata_unreadable",))

    try:
        snapshot = table.current_snapshot()
    except Exception:
        return TableOutcome(
            identifier=identifier,
            metadata_readable=True,
            failures=("current_snapshot_unreadable",),
        )
    snapshot_id = _snapshot_id(snapshot)
    if snapshot_id is None:
        return TableOutcome(
            identifier=identifier,
            metadata_readable=True,
            failures=("current_snapshot_missing",),
        )

    try:
        scan = table.scan(limit=1)
        list(scan.plan_files())
    except Exception:
        failures.append("manifest_unreadable")
        return TableOutcome(
            identifier=identifier,
            metadata_readable=True,
            current_snapshot_id=snapshot_id,
            failures=tuple(failures),
        )

    try:
        sample_rows = _sample_row_count(scan.to_arrow())
    except Exception:
        failures.append("data_unreadable")
        return TableOutcome(
            identifier=identifier,
            metadata_readable=True,
            current_snapshot_id=snapshot_id,
            manifests_readable=True,
            failures=tuple(failures),
        )

    return TableOutcome(
        identifier=identifier,
        metadata_readable=True,
        current_snapshot_id=snapshot_id,
        manifests_readable=True,
        data_readable=True,
        sample_rows=sample_rows,
    )


def _identifiers(response: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    namespaces: set[str] = set()
    for parts in response.get("namespaces", []):
        if isinstance(parts, list) and parts and all(isinstance(part, str) for part in parts):
            namespaces.add(".".join(parts))
    tables: set[str] = set()
    for item in response.get("tables", []):
        if not isinstance(item, dict):
            continue
        namespace = item.get("namespace")
        name = item.get("name")
        if (
            isinstance(namespace, list)
            and all(isinstance(part, str) for part in namespace)
            and isinstance(name, str)
        ):
            tables.add(".".join([*namespace, name]))
    return namespaces, tables


def _bounded(items: set[str]) -> list[str]:
    return sorted(items)[:_MAX_IDENTIFIERS]


def validate_catalog(
    *,
    transport: RecoveryCatalogTransport,
    container: str,
    catalog: str,
    recovery_target: str,
    git_revision: str,
    table_loader: TableLoader = _static_table,
) -> dict[str, Any]:
    expected = expected_registry_tables()
    response = transport.inspect(expected)
    actual_namespaces, actual_tables = _identifiers(response)
    expected_tables = set(expected)
    expected_namespaces = {identifier.split(".", 1)[0] for identifier in expected}
    missing = expected_tables - actual_tables
    unexpected = actual_tables - expected_tables
    missing_namespaces = expected_namespaces - actual_namespaces
    unexpected_namespaces = actual_namespaces - expected_namespaces

    raw_loads = response.get("loads")
    loads = raw_loads if isinstance(raw_loads, dict) else {}
    outcomes = [
        validate_table(
            identifier,
            loads.get(identifier, {}).get("response")
            if isinstance(loads.get(identifier), dict)
            else None,
            table_loader=table_loader,
        )
        for identifier in expected
    ]
    unreadable = sum(bool(outcome.failures) for outcome in outcomes)
    drift = bool(missing or unexpected or missing_namespaces or unexpected_namespaces)
    status = "pass" if not drift and unreadable == 0 else "fail"
    return {
        "status": status,
        "gitRevision": git_revision,
        "recoveryTarget": recovery_target,
        "container": container,
        "catalog": catalog,
        "counts": {
            "expectedTables": len(expected_tables),
            "actualTables": len(actual_tables),
            "validatedTables": len(outcomes) - unreadable,
            "failedTables": unreadable,
        },
        "missingNamespaces": _bounded(missing_namespaces),
        "unexpectedNamespaces": _bounded(unexpected_namespaces),
        "missingTables": _bounded(missing),
        "unexpectedTables": _bounded(unexpected),
        "identifierListsTruncated": any(
            len(items) > _MAX_IDENTIFIERS
            for items in (missing_namespaces, unexpected_namespaces, missing, unexpected)
        ),
        "tables": [asdict(outcome) for outcome in outcomes],
    }


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=False
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise ValidationError("unable to determine Git revision")
    return completed.stdout.strip()


def _failure_report(args: argparse.Namespace, message: str) -> dict[str, Any]:
    return {
        "status": "fail",
        "gitRevision": None,
        "recoveryTarget": args.recovery_target,
        "container": args.polaris_container,
        "catalog": args.catalog,
        "failure": message,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--polaris-container", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--recovery-target", required=True)
    args = parser.parse_args(argv)
    try:
        transport = DockerExecTransport(
            container=args.polaris_container,
            catalog=args.catalog,
        )
        report = validate_catalog(
            transport=transport,
            container=args.polaris_container,
            catalog=args.catalog,
            recovery_target=args.recovery_target,
            git_revision=_git_revision(),
        )
    except ValidationError as error:
        report = _failure_report(args, str(error))
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
