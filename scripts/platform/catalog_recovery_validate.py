#!/usr/bin/env python3
"""Read-only, registry-derived validation of an isolated restored Polaris catalog."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, TypeGuard

from databox.config.sources import SOURCES
from pyiceberg.table import StaticTable

STATUS_TABLE = "_dlt_load_status"
REGISTRY_PATH = Path("packages/databox/databox/config/sources.py")
RECOVERY_LABEL = "com.databox.catalog-recovery.validation"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_IDENTIFIER_COMPONENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
_MAX_IDENTIFIER_PARTS = 16
_MAX_IDENTIFIER_LENGTH = 512
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
    except Exception:
        loaded_tables[identifier] = {"request_failed": True}
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
        inspect_format = (
            '{"running":{{json .State.Running}},"labels":{{json .Config.Labels}},'
            '"portBindings":{{json .HostConfig.PortBindings}}}'
        )
        try:
            identity = self.runner(
                ["docker", "inspect", "--format", inspect_format, self.container],
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as error:
            raise ValidationError("unable to inspect restored Polaris container") from error
        if identity.returncode != 0:
            raise ValidationError("restored Polaris container inspection failed")
        try:
            details = json.loads(identity.stdout)
        except (json.JSONDecodeError, TypeError) as error:
            raise ValidationError("restored Polaris container identity is invalid") from error
        labels = details.get("labels") if isinstance(details, dict) else None
        ports = details.get("portBindings") if isinstance(details, dict) else None
        if (
            not isinstance(details, dict)
            or details.get("running") is not True
            or not isinstance(labels, dict)
            or labels.get(RECOVERY_LABEL) != "polaris"
            or (isinstance(ports, dict) and any(ports.values()))
            or not isinstance(ports, dict)
        ):
            raise ValidationError(
                "container is not a running, unexposed restored Polaris validation container"
            )

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


def _rest_snapshot_id(load_response: object) -> tuple[str | None, str | None]:
    if not isinstance(load_response, dict):
        return None, "rest_snapshot_missing"
    metadata = load_response.get("metadata")
    if metadata is None:
        return None, "rest_snapshot_missing"
    if not isinstance(metadata, dict):
        return None, "rest_snapshot_malformed"
    if "current-snapshot-id" not in metadata:
        return None, "rest_snapshot_missing"
    value = metadata["current-snapshot-id"]
    if isinstance(value, bool) or not isinstance(value, int):
        return None, "rest_snapshot_malformed"
    return str(value), None


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

    rest_snapshot_id, rest_failure = _rest_snapshot_id(load)
    if rest_failure is not None:
        failures.append(rest_failure)
    elif rest_snapshot_id != snapshot_id:
        failures.append("snapshot_divergent")

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
        failures=tuple(failures),
    )


def _valid_components(parts: object) -> TypeGuard[list[str]]:
    return (
        isinstance(parts, list)
        and 0 < len(parts) <= _MAX_IDENTIFIER_PARTS
        and all(isinstance(part, str) and _IDENTIFIER_COMPONENT.fullmatch(part) for part in parts)
        and sum(len(part) for part in parts) + len(parts) - 1 <= _MAX_IDENTIFIER_LENGTH
    )


def _identifiers(response: Mapping[str, Any]) -> tuple[set[str], set[str], int]:
    namespaces: set[str] = set()
    malformed = 0
    raw_namespaces = response.get("namespaces", [])
    if not isinstance(raw_namespaces, list):
        raw_namespaces = []
        malformed += 1
    for parts in raw_namespaces:
        if _valid_components(parts):
            namespaces.add(".".join(parts))
        else:
            malformed += 1
    tables: set[str] = set()
    raw_tables = response.get("tables", [])
    if not isinstance(raw_tables, list):
        raw_tables = []
        malformed += 1
    for item in raw_tables:
        namespace = item.get("namespace") if isinstance(item, dict) else None
        name = item.get("name") if isinstance(item, dict) else None
        if (
            _valid_components(namespace)
            and isinstance(name, str)
            and _IDENTIFIER_COMPONENT.fullmatch(name)
        ):
            tables.add(".".join([*namespace, name]))
        else:
            malformed += 1
    return namespaces, tables, malformed


def _bounded(items: set[str]) -> list[str]:
    return sorted(items)[:_MAX_IDENTIFIERS]


def validate_catalog(
    *,
    transport: RecoveryCatalogTransport,
    container: str,
    catalog: str,
    recovery_target: str,
    source_revision: str,
    table_loader: TableLoader = _static_table,
) -> dict[str, Any]:
    expected = expected_registry_tables()
    response = transport.inspect(expected)
    actual_namespaces, actual_tables, malformed = _identifiers(response)
    expected_tables = set(expected)
    expected_namespaces = {identifier.split(".", 1)[0] for identifier in expected}
    missing = expected_tables - actual_tables
    extra_tables = actual_tables - expected_tables
    unexpected = {
        identifier
        for identifier in extra_tables
        if identifier.rsplit(".", 1)[0] in expected_namespaces
    }
    noncanonical_tables = extra_tables - unexpected
    missing_namespaces = expected_namespaces - actual_namespaces
    noncanonical_namespaces = actual_namespaces - expected_namespaces

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
    drift = bool(missing or unexpected or missing_namespaces or malformed)
    status = "pass" if not drift and unreadable == 0 else "fail"
    return {
        "status": status,
        "sourceRevision": source_revision,
        "recoveryTarget": recovery_target,
        "container": container,
        "catalog": catalog,
        "counts": {
            "expectedTables": len(expected_tables),
            "actualTables": len(actual_tables),
            "validatedTables": len(outcomes) - unreadable,
            "failedTables": unreadable,
        },
        "warningCount": len(noncanonical_namespaces) + len(noncanonical_tables),
        "missingNamespaces": _bounded(missing_namespaces),
        "noncanonicalNamespaces": _bounded(noncanonical_namespaces),
        "missingTables": _bounded(missing),
        "unexpectedTables": _bounded(unexpected),
        "noncanonicalTables": _bounded(noncanonical_tables),
        "malformedObservedIdentifiers": malformed,
        "identifierListsTruncated": any(
            len(items) > _MAX_IDENTIFIERS
            for items in (
                missing_namespaces,
                noncanonical_namespaces,
                missing,
                unexpected,
                noncanonical_tables,
            )
        ),
        "tables": [asdict(outcome) for outcome in outcomes],
    }


def resolve_source_revision(requested: str) -> str:
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", f"{requested}^{{commit}}"],
        text=True,
        capture_output=True,
        check=False,
    )
    commit = resolved.stdout.strip()
    if resolved.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValidationError("source revision does not resolve to a commit")
    historical = subprocess.run(
        ["git", "show", f"{commit}:{REGISTRY_PATH.as_posix()}"],
        capture_output=True,
        check=False,
    )
    if historical.returncode != 0:
        raise ValidationError("source revision does not contain the canonical registry")
    try:
        current = REGISTRY_PATH.read_bytes()
    except OSError as error:
        raise ValidationError("unable to read the working-tree canonical registry") from error
    if historical.stdout != current:
        raise ValidationError("source revision registry differs from the imported working tree")
    return commit


def _failure_report(
    args: argparse.Namespace, message: str, source_revision: str | None
) -> dict[str, Any]:
    return {
        "status": "fail",
        "sourceRevision": source_revision,
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
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args(argv)
    started = time.monotonic()
    source_revision = None
    try:
        source_revision = resolve_source_revision(args.source_revision)
        transport = DockerExecTransport(
            container=args.polaris_container,
            catalog=args.catalog,
        )
        report = validate_catalog(
            transport=transport,
            container=args.polaris_container,
            catalog=args.catalog,
            recovery_target=args.recovery_target,
            source_revision=source_revision,
        )
    except ValidationError as error:
        report = _failure_report(args, str(error), source_revision)
    report["elapsedSeconds"] = round(time.monotonic() - started, 3)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
