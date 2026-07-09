"""Unit tests for Xeno-canto dlt resources."""

from __future__ import annotations

from typing import Any

from databox.config.pipeline_config import load_pipeline_config
from databox_sources.xeno_canto import source as xeno_module
from databox_sources.xeno_canto.source import (
    XENO_CANTO_DEFAULT_QUERY,
    process_recording,
    xeno_canto_source,
)


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def _recording_payload() -> dict[str, Any]:
    return {
        "id": "123456",
        "gen": "Cyanocitta",
        "sp": "stelleri",
        "ssp": "stelleri",
        "group": "birds",
        "en": "Steller's Jay",
        "rec": "Example Recordist",
        "cnt": "United States",
        "loc": "Thumb Butte, Yavapai County, Arizona",
        "lat": "34.541",
        "lng": "-112.515",
        "alt": "1700",
        "type": "song, call",
        "sex": "unknown",
        "stage": "adult",
        "method": "field recording",
        "url": "https://xeno-canto.org/123456",
        "file": "https://xeno-canto.org/123456/download",
        "file-name": "XC123456-stellers-jay.mp3",
        "sono": {"small": "https://xeno-canto.org/sounds/uploaded/example-small.png"},
        "osci": {"small": "https://xeno-canto.org/sounds/uploaded/example-osci.png"},
        "lic": "//creativecommons.org/licenses/by-nc-sa/4.0/",
        "q": "A",
        "length": "0:42",
        "time": "06:15",
        "date": "2026-07-01",
        "uploaded": "2026-07-02",
        "also": ["Aphelocoma wollweberi"],
        "rmk": "Example remarks",
        "bird-seen": "yes",
        "animal-seen": "yes",
        "playback-used": "no",
        "temp": "18 C",
        "regnr": "ABC-123",
        "auto": "no",
        "dvc": "Example recorder",
        "mic": "Example microphone",
    }


def test_process_recording_preserves_media_license_and_provenance_fields() -> None:
    row = process_recording(
        _recording_payload(),
        query=XENO_CANTO_DEFAULT_QUERY,
        page=1,
        loaded_at="2026-07-08T00:00:00Z",
    )

    assert row["id"] == "123456"
    assert row["genus"] == "Cyanocitta"
    assert row["species"] == "stelleri"
    assert row["english_name"] == "Steller's Jay"
    assert row["recordist"] == "Example Recordist"
    assert row["country"] == "United States"
    assert row["locality"] == "Thumb Butte, Yavapai County, Arizona"
    assert row["latitude"] == 34.541
    assert row["longitude"] == -112.515
    assert row["recording_url"] == "https://xeno-canto.org/123456"
    assert row["audio_file_url"] == "https://xeno-canto.org/123456/download"
    assert row["file_name"] == "XC123456-stellers-jay.mp3"
    assert row["license"] == "//creativecommons.org/licenses/by-nc-sa/4.0/"
    assert row["quality"] == "A"
    assert row["also_species"] == "Aphelocoma wollweberi"
    assert row["bird_seen"] == "yes"
    assert row["playback_used"] == "no"
    assert row["_source_url"] == xeno_module.XENO_CANTO_RECORDINGS
    assert row["_query"] == XENO_CANTO_DEFAULT_QUERY
    assert row["_query_page"] == 1
    assert row["_loaded_at"] == "2026-07-08T00:00:00Z"


def test_recordings_resource_fetches_authenticated_metadata_endpoint(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_get(url: str, *, headers: dict[str, Any], params: dict[str, Any]) -> _Response:
        calls.append({"url": url, "headers": headers, "params": params})
        return _Response(
            {
                "numRecordings": "1",
                "numSpecies": "1",
                "page": 1,
                "numPages": 1,
                "recordings": [_recording_payload()],
            }
        )

    monkeypatch.setenv("XENO_CANTO_API_KEY", "test-key")
    monkeypatch.setattr(xeno_module.dlt_requests, "get", fake_get)

    source = xeno_canto_source(query=XENO_CANTO_DEFAULT_QUERY, max_records=1, per_page=50)
    rows = list(source.resources["recordings"])

    assert len(rows) == 1
    assert rows[0]["id"] == "123456"
    assert calls == [
        {
            "url": xeno_module.XENO_CANTO_RECORDINGS,
            "headers": {"Accept": "application/json"},
            "params": {
                "query": XENO_CANTO_DEFAULT_QUERY,
                "per_page": 1,
                "page": 1,
                "key": "test-key",
            },
        }
    ]


def test_recordings_resource_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("XENO_CANTO_API_KEY", raising=False)

    source = xeno_canto_source(query=XENO_CANTO_DEFAULT_QUERY, max_records=1)

    try:
        list(source.resources["recordings"])
    except Exception as exc:  # noqa: BLE001 - dlt wraps extraction errors
        assert "XENO_CANTO_API_KEY" in str(exc)
    else:  # pragma: no cover - defensive assertion path
        raise AssertionError("expected missing XENO_CANTO_API_KEY to fail")


def test_xeno_canto_config_loads_source_params() -> None:
    config = load_pipeline_config("xeno_canto")

    assert config.source_module == "databox_sources.xeno_canto.source"
    assert config.params["query"] == XENO_CANTO_DEFAULT_QUERY
    assert config.params["max_records"] == 1000
    assert config.params["per_page"] == 100
