"""Shared pytest fixtures for databox-sources test harness.

Uses pytest-recording (vcrpy) to intercept HTTP calls made through
`dlt.sources.helpers.requests` (which wraps the standard `requests`
library; urllib3 is the actual transport VCR hooks).

Every test module under packages/databox-sources/tests/<source>/ gets:
- auto-scoped cassette storage at tests/<source>/cassettes/
- secret redaction for request headers and query strings
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

TESTS_ROOT = Path(__file__).parent

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


def _scrub_response_body(response: dict[str, Any]) -> dict[str, Any]:
    """Strip known token echoes from response bodies.

    NOAA and eBird don't echo tokens in bodies today, but this is cheap
    insurance — if the API ever starts leaking them, the filter already exists.
    """
    ebird = os.getenv("EBIRD_API_TOKEN", "")
    noaa = os.getenv("NOAA_API_TOKEN", "")
    motherduck = os.getenv("MOTHERDUCK_TOKEN", "")

    tokens = [t for t in (ebird, noaa, motherduck) if t]
    if not tokens:
        return response

    body = response.get("body", {})
    raw = body.get("string")
    if isinstance(raw, bytes):
        for tok in tokens:
            raw = raw.replace(tok.encode(), b"REDACTED")
        body["string"] = raw
    elif isinstance(raw, str):
        for tok in tokens:
            raw = raw.replace(tok, "REDACTED")
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
        ],
        "filter_query_parameters": [
            ("token", "REDACTED"),
            ("api_key", "REDACTED"),
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
def _fake_api_tokens_when_missing(monkeypatch):
    """Inject dummy API tokens for CI replay runs.

    Sources raise on missing tokens before any HTTP call, so VCR never gets
    a chance to replay. Only set when unset — local re-records still use
    real tokens. Token values leaked into cassettes are filtered via
    filter_headers/filter_query_parameters on recording.
    """
    for var in ("EBIRD_API_TOKEN", "NOAA_API_TOKEN"):
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
