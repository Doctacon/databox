"""Regression coverage for credential, session, and fixture minimization."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).parents[3]
_TESTS_ROOT = Path(__file__).parent
_MANIFEST = _ROOT / ".10x/evidence/.storage/2026-07-14-source-contract-fixture-sha256.txt"
_GBIF_REFERENCE_PLACEHOLDER = "https://example.invalid/gbif-occurrence"
_EBIRD_PRIVATE_LOCATION_NAME = "Private location (sanitized)"
_EBIRD_PRIVATE_LOCATION_ID = re.compile(r"^PRIVATE-LOCATION-\d{3}$")
_EBIRD_PRIVATE_SUBMISSION_ID = re.compile(r"^PRIVATE-SUBMISSION-\d{3}$")
_PERSONAL_RESPONSE_FIELDS = {
    "catalogNumber",
    "fieldNotes",
    "identifiedBy",
    "identifiedByID",
    "locality",
    "occurrenceRemarks",
    "recordedBy",
    "recordedByID",
    "verbatimLocality",
}


def _response_payloads(cassette: Path) -> list[Any]:
    document = yaml.safe_load(cassette.read_text()) or {}
    payloads: list[Any] = []
    for interaction in document.get("interactions", []):
        raw = interaction.get("response", {}).get("body", {}).get("string")
        if isinstance(raw, bytes):
            raw = raw.decode()
        if not isinstance(raw, str):
            continue
        try:
            payloads.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return payloads


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _all_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _all_keys(child)}
    return set()


def test_vcr_config_filters_request_cookie(vcr_config) -> None:
    assert ("cookie", "REDACTED") in vcr_config["filter_headers"]
    assert ("key", "REDACTED") in vcr_config["filter_query_parameters"]


def test_response_scrub_removes_session_cookie_and_minimizes_gbif_reference(
    monkeypatch, vcr_config
) -> None:
    monkeypatch.setenv("XENO_CANTO_API_KEY", "secret-test-value")
    response = {
        "headers": {
            "Content-Type": ["application/json"],
            "Set-Cookie": ["PHPSESSID=secret-session; path=/; HttpOnly"],
        },
        "body": {
            "string": json.dumps(
                {
                    "results": [
                        {
                            "key": 1,
                            "gbifID": "1",
                            "scientificName": "Corvus corax",
                            "references": "https://provider.example/resolvable/1",
                            "recordedBy": "Public Observer",
                            "remarks": "secret-test-value",
                        }
                    ]
                }
            ).encode()
        },
    }

    scrubbed = vcr_config["before_record_response"](response)
    assert all(key.lower() != "set-cookie" for key in scrubbed["headers"])
    payload = json.loads(scrubbed["body"]["string"])
    assert payload["results"] == [
        {
            "key": 1,
            "gbifID": "1",
            "scientificName": "Corvus corax",
            "references": _GBIF_REFERENCE_PLACEHOLDER,
        }
    ]
    serialized = str(scrubbed["headers"]) + scrubbed["body"]["string"].decode()
    assert "PHPSESSID" not in serialized
    assert "secret-test-value" not in serialized
    assert "Public Observer" not in serialized


def test_response_scrub_sanitizes_top_level_ebird_private_locations(vcr_config) -> None:
    public_row = {
        "locationPrivate": False,
        "locName": "Public park",
        "locId": "PUBLIC-1",
        "subId": "PUBLIC-SUBMISSION-1",
        "lat": 35.0,
        "lng": -111.0,
    }
    response = {
        "headers": {"Content-Type": ["application/json"]},
        "body": {
            "string": json.dumps(
                [
                    public_row,
                    {
                        "speciesCode": "example1",
                        "locationPrivate": True,
                        "locName": "private-original-one",
                        "locId": "private-location-one",
                        "subId": "private-submission-one",
                        "lat": 12.34,
                        "lng": -56.78,
                    },
                    {
                        "speciesCode": "example2",
                        "locationPrivate": True,
                        "locName": "private-original-one",
                        "locId": "private-location-one",
                        "subId": "private-submission-one",
                        "lat": 12.34,
                        "lng": -56.78,
                    },
                    {
                        "speciesCode": "example3",
                        "locationPrivate": True,
                        "locName": "private-original-two",
                        "locId": "private-location-two",
                        "subId": "private-submission-two",
                        "lat": 23.45,
                        "lng": -67.89,
                    },
                ]
            ).encode()
        },
    }

    scrubbed = vcr_config["before_record_response"](response)
    payload = json.loads(scrubbed["body"]["string"])

    assert payload[0] == public_row
    private_rows = payload[1:]
    assert [row["locId"] for row in private_rows] == [
        "PRIVATE-LOCATION-001",
        "PRIVATE-LOCATION-001",
        "PRIVATE-LOCATION-002",
    ]
    assert [row["subId"] for row in private_rows] == [
        "PRIVATE-SUBMISSION-001",
        "PRIVATE-SUBMISSION-001",
        "PRIVATE-SUBMISSION-002",
    ]
    assert all(row["locationPrivate"] is True for row in private_rows)
    assert all(row["locName"] == _EBIRD_PRIVATE_LOCATION_NAME for row in private_rows)
    assert all(row["lat"] == 0.0 and row["lng"] == 0.0 for row in private_rows)
    serialized = scrubbed["body"]["string"].decode()
    assert "private-original" not in serialized
    assert "private-location" not in serialized
    assert "private-submission" not in serialized
    assert "12.34" not in serialized
    assert "-56.78" not in serialized


def test_all_tracked_source_fixtures_are_manifested_and_sanitized() -> None:
    cassettes = sorted(_TESTS_ROOT.glob("*/cassettes/**/*.yaml"))
    snapshots = sorted(_TESTS_ROOT.glob("*/__snapshots__/*.ambr"))
    expected = {path.relative_to(_ROOT).as_posix() for path in [*cassettes, *snapshots]}
    manifested: dict[str, str] = {}
    for line in _MANIFEST.read_text().splitlines():
        digest, path = line.split(maxsplit=1)
        manifested[path] = digest

    assert len(cassettes) == 24
    assert len(snapshots) == 7
    assert set(manifested) == expected
    for path, expected_digest in manifested.items():
        assert hashlib.sha256((_ROOT / path).read_bytes()).hexdigest() == expected_digest

    private_rows = 0
    for cassette in cassettes:
        document = yaml.safe_load(cassette.read_text()) or {}
        for interaction in document.get("interactions", []):
            request_headers = interaction.get("request", {}).get("headers", {})
            response_headers = interaction.get("response", {}).get("headers", {})
            assert "cookie" not in {str(key).lower() for key in request_headers}
            assert "set-cookie" not in {str(key).lower() for key in response_headers}
        assert "PHPSESSID" not in cassette.read_text()
        for payload in _response_payloads(cassette):
            assert not (_all_keys(payload) & _PERSONAL_RESPONSE_FIELDS)
            if "ebird" not in cassette.parts or not isinstance(payload, list):
                continue
            for row in payload:
                if not isinstance(row, dict) or row.get("locationPrivate") is not True:
                    continue
                private_rows += 1
                assert row["locName"] == _EBIRD_PRIVATE_LOCATION_NAME
                assert _EBIRD_PRIVATE_LOCATION_ID.fullmatch(row["locId"])
                assert _EBIRD_PRIVATE_SUBMISSION_ID.fullmatch(row["subId"])
                assert row["lat"] == 0.0
                assert row["lng"] == 0.0

    assert private_rows > 0
