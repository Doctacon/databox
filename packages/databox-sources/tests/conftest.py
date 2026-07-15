"""Shared pytest fixtures for databox-sources test harness.

Uses pytest-recording (vcrpy) to intercept HTTP calls made through
`dlt.sources.helpers.requests` (which wraps the standard `requests`
library; urllib3 is the actual transport VCR hooks).

Every test module under packages/databox-sources/tests/<source>/ gets:
- auto-scoped cassette storage at tests/<source>/cassettes/
- secret redaction for request headers and query strings
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

TESTS_ROOT = Path(__file__).parent
_GBIF_REFERENCE_PLACEHOLDER = "https://example.invalid/gbif-occurrence"
_EBIRD_PRIVATE_LOCATION_NAME = "Private location (sanitized)"
_EBIRD_PRIVATE_LOCATION_ID_PREFIX = "PRIVATE-LOCATION-"
_EBIRD_PRIVATE_SUBMISSION_ID_PREFIX = "PRIVATE-SUBMISSION-"
_EBIRD_PRIVATE_COORDINATE = 0.0

_NOISY_SCHEMA_KEYS: tuple[str, ...] = (
    "version_hash",
    "previous_hashes",
    "engine_version",
    "imported_version_hash",
    "version",
    "created_at",
    "modified_at",
)


def normalize_schema_yaml(raw: str) -> str:
    """Strip non-deterministic fields from a dlt schema YAML snapshot."""
    doc: dict[str, Any] = yaml.safe_load(raw) or {}
    for key in _NOISY_SCHEMA_KEYS:
        doc.pop(key, None)
    for table in doc.get("tables", {}).values():
        table.pop("x-normalizer", None)
        table.pop("x-stored-schema-hash", None)
        columns = table.get("columns", {}) or {}
        for col in columns.values():
            col.pop("x-normalizer", None)
    dumped = yaml.safe_dump(doc, sort_keys=True, default_flow_style=False)
    # Strip trailing whitespace to survive pre-commit trailing-whitespace hooks
    # that would otherwise mangle the committed snapshot file.
    return "\n".join(line.rstrip() for line in dumped.splitlines())


def _sanitize_ebird_private_locations(payload: list[Any]) -> list[Any]:
    """Replace private eBird location data with non-resolvable synthetic values."""
    location_ids: dict[str, int] = {}
    submission_ids: dict[str, int] = {}
    for row in payload:
        if not isinstance(row, dict) or row.get("locationPrivate") is not True:
            continue
        location_key = str(row.get("locId", ""))
        submission_key = str(row.get("subId", ""))
        location_index = location_ids.setdefault(location_key, len(location_ids) + 1)
        submission_index = submission_ids.setdefault(submission_key, len(submission_ids) + 1)
        row.update(
            {
                "locName": _EBIRD_PRIVATE_LOCATION_NAME,
                "locId": f"{_EBIRD_PRIVATE_LOCATION_ID_PREFIX}{location_index:03d}",
                "subId": f"{_EBIRD_PRIVATE_SUBMISSION_ID_PREFIX}{submission_index:03d}",
                "lat": _EBIRD_PRIVATE_COORDINATE,
                "lng": _EBIRD_PRIVATE_COORDINATE,
            }
        )
    return payload


def _bounded_provider_payload(payload: Any) -> Any:
    """Minimize newly recorded public fixtures to fields required by source tests."""
    if isinstance(payload, list):
        return _sanitize_ebird_private_locations(payload)
    if not isinstance(payload, dict):
        return payload
    results = payload.get("results")
    if (
        isinstance(results, list)
        and results
        and isinstance(results[0], dict)
        and ("key" in results[0] or "gbifID" in results[0])
    ):
        allowed = {
            "key",
            "gbifID",
            "scientificName",
            "acceptedScientificName",
            "class",
            "countryCode",
            "stateProvince",
            "eventDate",
            "basisOfRecord",
            "occurrenceStatus",
            "license",
            "references",
        }
        payload["results"] = [
            {
                key: (_GBIF_REFERENCE_PLACEHOLDER if key == "references" else value)
                for key, value in row.items()
                if key in allowed
            }
            for row in results[:2]
        ]
    elif isinstance(payload.get("recordings"), list):
        allowed = {
            "id",
            "gen",
            "sp",
            "group",
            "en",
            "cnt",
            "type",
            "url",
            "file",
            "lic",
            "q",
            "date",
        }
        payload["recordings"] = [
            {key: value for key, value in row.items() if key in allowed}
            for row in payload["recordings"][:2]
        ]
    elif isinstance(payload.get("features"), list):
        payload["features"] = payload["features"][:2]
    return payload


def _scrub_response_body(response: dict[str, Any]) -> dict[str, Any]:
    """Bound provider fixtures and strip credentials/session cookies."""
    headers = response.get("headers", {})
    if isinstance(headers, dict):
        for key in list(headers):
            if str(key).lower() == "set-cookie":
                del headers[key]

    body = response.get("body", {})
    raw = body.get("string")
    if isinstance(raw, bytes | str):
        try:
            decoded = raw.decode() if isinstance(raw, bytes) else raw
            raw = json.dumps(_bounded_provider_payload(json.loads(decoded))).encode()
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

    tokens = [
        token
        for token in (
            os.getenv("EBIRD_API_TOKEN", ""),
            os.getenv("NOAA_API_TOKEN", ""),
            os.getenv("XENO_CANTO_API_KEY", ""),
        )
        if token
    ]
    if isinstance(raw, bytes):
        for token in tokens:
            raw = raw.replace(token.encode(), b"REDACTED")
        body["string"] = raw
    elif isinstance(raw, str):
        for token in tokens:
            raw = raw.replace(token, "REDACTED")
        body["string"] = raw
    return response


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, Any]:
    return {
        "filter_headers": [
            ("authorization", "REDACTED"),
            ("x-ebirdapitoken", "REDACTED"),
            ("token", "REDACTED"),
            ("x-api-key", "REDACTED"),
            ("cookie", "REDACTED"),
        ],
        "filter_query_parameters": [
            ("token", "REDACTED"),
            ("api_key", "REDACTED"),
            ("key", "REDACTED"),
        ],
        "ignore_hosts": ["telemetry.scalevector.ai"],
        "before_record_response": _scrub_response_body,
        "decode_compressed_response": True,
        "allow_playback_repeats": True,
    }


@pytest.fixture(autouse=True)
def _disable_dlt_telemetry(monkeypatch):
    """Keep dlt's hub telemetry out of VCR cassettes."""
    monkeypatch.setenv("RUNTIME__DLTHUB_TELEMETRY", "false")


@pytest.fixture(autouse=True)
def _isolate_dlt_http_client(request, monkeypatch):
    """Give every VCR test fresh HTTP pools bound only to its cassette.

    dlt's module-level client shares one HTTPAdapter across thread-local sessions.
    urllib3 pools created while vcrpy is active retain cassette-bound connection
    classes, so reusing the adapter can route a later source through an earlier
    source's cassette. A fresh public Client per marked test preserves dlt retry
    behavior without carrying pooled connections across cassette lifetimes.
    """
    if request.node.get_closest_marker("vcr") is None:
        yield
        return

    from dlt.sources.helpers import requests as dlt_requests

    client = dlt_requests.Client()
    monkeypatch.setattr(dlt_requests, "client", client)
    for method in ("get", "post", "put", "patch", "delete", "options", "head", "request"):
        monkeypatch.setattr(dlt_requests, method, getattr(client, method))

    yield

    client.session.close()


@pytest.fixture(autouse=True)
def _fake_api_tokens_when_missing(monkeypatch):
    """Inject dummy API tokens for CI replay runs.

    Sources raise on missing tokens before any HTTP call, so VCR never gets
    a chance to replay. Only set when unset — local re-records still use
    real tokens. Token values leaked into cassettes are filtered via
    filter_headers/filter_query_parameters on recording.
    """
    for var in ("EBIRD_API_TOKEN", "NOAA_API_TOKEN", "XENO_CANTO_API_KEY"):
        if not os.getenv(var):
            monkeypatch.setenv(var, "test-token-for-vcr-replay")


@pytest.fixture
def normalize_schema():
    return normalize_schema_yaml


@pytest.fixture
def memory_duckdb_pipeline_factory(tmp_path):
    """Build a fresh in-memory duckdb dlt pipeline for each test.

    dlt requires an explicit `duckdb.connect(":memory:")` handle (bare `:memory:`
    strings are rejected). `pipelines_dir=tmp_path` isolates dlt state per test.
    """
    import dlt
    import duckdb

    conns: list[Any] = []

    def _factory(pipeline_name: str, dataset_name: str = "main"):
        conn = duckdb.connect(":memory:")
        conns.append(conn)
        return dlt.pipeline(
            pipeline_name=pipeline_name,
            destination=dlt.destinations.duckdb(credentials=conn),
            dataset_name=dataset_name,
            pipelines_dir=str(tmp_path / ".dlt"),
        )

    yield _factory

    for conn in conns:
        conn.close()
