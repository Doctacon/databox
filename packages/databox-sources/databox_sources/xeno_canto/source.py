"""Xeno-canto recording metadata source pipeline using dlt.

Data: bird sound recording metadata only. Audio files are preserved as external
links and are not downloaded or stored.

API: https://xeno-canto.org/api/3/recordings
Docs: https://xeno-canto.org/explore/api
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

import dlt
import pendulum
from databox.config.pipeline_config import PipelineConfig
from databox.config.settings import settings
from databox.destinations import dlt_destination, dlt_pipeline, prepare_dlt_source
from dlt.sources.helpers import requests as dlt_requests
from dotenv import load_dotenv

from databox_sources._logging import get_logger

load_dotenv()

log = get_logger("databox_sources.xeno_canto")

XENO_CANTO_API_BASE = "https://xeno-canto.org/api/3"
XENO_CANTO_RECORDINGS = f"{XENO_CANTO_API_BASE}/recordings"
XENO_CANTO_DEFAULT_QUERY = 'cnt:"United States" loc:"Arizona" grp:birds'
XENO_CANTO_PAGE_LIMIT = 500

_RECORDING_COLUMNS: Any = {
    "id": {"data_type": "text"},
    "genus": {"data_type": "text"},
    "species": {"data_type": "text"},
    "subspecies": {"data_type": "text"},
    "group_name": {"data_type": "text"},
    "english_name": {"data_type": "text"},
    "recordist": {"data_type": "text"},
    "country": {"data_type": "text"},
    "locality": {"data_type": "text"},
    "latitude": {"data_type": "double"},
    "longitude": {"data_type": "double"},
    "altitude": {"data_type": "text"},
    "recording_type": {"data_type": "text"},
    "sex": {"data_type": "text"},
    "stage": {"data_type": "text"},
    "method": {"data_type": "text"},
    "recording_url": {"data_type": "text"},
    "audio_file_url": {"data_type": "text"},
    "file_name": {"data_type": "text"},
    "sonogram": {"data_type": "text"},
    "oscillogram": {"data_type": "text"},
    "license": {"data_type": "text"},
    "quality": {"data_type": "text"},
    "length": {"data_type": "text"},
    "recording_time": {"data_type": "text"},
    "recording_date": {"data_type": "text"},
    "uploaded_at": {"data_type": "text"},
    "also_species": {"data_type": "text"},
    "remarks": {"data_type": "text"},
    "bird_seen": {"data_type": "text"},
    "animal_seen": {"data_type": "text"},
    "playback_used": {"data_type": "text"},
    "temperature": {"data_type": "text"},
    "registration_number": {"data_type": "text"},
    "automatic_recording": {"data_type": "text"},
    "device": {"data_type": "text"},
    "microphone": {"data_type": "text"},
    "_source_url": {"data_type": "text"},
    "_query": {"data_type": "text"},
    "_query_page": {"data_type": "bigint"},
    "_loaded_at": {"data_type": "timestamp"},
}


def _api_key() -> str:
    api_key = os.getenv("XENO_CANTO_API_KEY")
    if not api_key:
        raise ValueError("XENO_CANTO_API_KEY not found in environment variables")
    return api_key


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if item is not None) or None
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def process_recording(
    record: dict[str, Any], *, query: str, page: int, loaded_at: str
) -> dict[str, Any]:
    """Flatten one Xeno-canto recording into the raw metadata table contract."""
    return {
        "id": _string_or_none(record.get("id")),
        "genus": _string_or_none(record.get("gen")),
        "species": _string_or_none(record.get("sp")),
        "subspecies": _string_or_none(record.get("ssp")),
        "group_name": _string_or_none(record.get("group")),
        "english_name": _string_or_none(record.get("en")),
        "recordist": _string_or_none(record.get("rec")),
        "country": _string_or_none(record.get("cnt")),
        "locality": _string_or_none(record.get("loc")),
        "latitude": _float_or_none(record.get("lat")),
        "longitude": _float_or_none(record.get("lng")),
        "altitude": _string_or_none(record.get("alt")),
        "recording_type": _string_or_none(record.get("type")),
        "sex": _string_or_none(record.get("sex")),
        "stage": _string_or_none(record.get("stage")),
        "method": _string_or_none(record.get("method")),
        "recording_url": _string_or_none(record.get("url")),
        "audio_file_url": _string_or_none(record.get("file")),
        "file_name": _string_or_none(record.get("file-name")),
        "sonogram": _json_or_none(record.get("sono")),
        "oscillogram": _json_or_none(record.get("osci")),
        "license": _string_or_none(record.get("lic")),
        "quality": _string_or_none(record.get("q")),
        "length": _string_or_none(record.get("length")),
        "recording_time": _string_or_none(record.get("time")),
        "recording_date": _string_or_none(record.get("date")),
        "uploaded_at": _string_or_none(record.get("uploaded")),
        "also_species": _string_or_none(record.get("also")),
        "remarks": _string_or_none(record.get("rmk")),
        "bird_seen": _string_or_none(record.get("bird-seen")),
        "animal_seen": _string_or_none(record.get("animal-seen")),
        "playback_used": _string_or_none(record.get("playback-used")),
        "temperature": _string_or_none(record.get("temp")),
        "registration_number": _string_or_none(record.get("regnr")),
        "automatic_recording": _string_or_none(record.get("auto")),
        "device": _string_or_none(record.get("dvc")),
        "microphone": _string_or_none(record.get("mic")),
        "_source_url": XENO_CANTO_RECORDINGS,
        "_query": query,
        "_query_page": page,
        "_loaded_at": loaded_at,
    }


@dlt.source
def xeno_canto_source(
    query: str = XENO_CANTO_DEFAULT_QUERY,
    max_records: int = 1000,
    per_page: int = 100,
) -> Any:
    """Xeno-canto bird recording metadata source."""
    loaded_at = pendulum.now().isoformat()

    @dlt.resource(
        primary_key="id",
        write_disposition="merge",
        columns=_RECORDING_COLUMNS,
    )
    def recordings() -> Iterator[dict[str, Any]]:
        if max_records <= 0:
            return

        yielded = 0
        page = 1
        page_size = max(1, min(per_page, XENO_CANTO_PAGE_LIMIT, max_records))
        api_key = _api_key()

        while yielded < max_records:
            response = dlt_requests.get(
                XENO_CANTO_RECORDINGS,
                headers={"Accept": "application/json"},
                params={"query": query, "per_page": page_size, "page": page, "key": api_key},
            )
            response.raise_for_status()
            payload = response.json()
            if "error" in payload:
                message = payload.get("message", payload["error"])
                raise ValueError(f"Xeno-canto API error: {message}")
            results = payload.get("recordings", [])
            if not results:
                break

            for record in results:
                row = process_recording(record, query=query, page=page, loaded_at=loaded_at)
                if row["id"] is not None:
                    yield row
                    yielded += 1
                    if yielded >= max_records:
                        break

            log.info("recordings_page_fetched", count=len(results), page=page)
            num_pages = int(payload.get("numPages") or page)
            if page >= num_pages or len(results) < page_size:
                break
            page += 1

    return [recordings]


class XenoCantoPipelineSource:
    """Xeno-canto pipeline source implementing the PipelineSource protocol."""

    def __init__(self, config: PipelineConfig) -> None:
        self.name = config.name
        self.config = config
        self._query = str(config.params.get("query", XENO_CANTO_DEFAULT_QUERY))
        self._max_records = int(config.params.get("max_records", 1000))
        self._per_page = int(config.params.get("per_page", 100))

    def _source(self) -> Any:
        return xeno_canto_source(
            query=self._query,
            max_records=self._max_records,
            per_page=self._per_page,
        )

    def resources(self) -> list[Any]:
        source = self._source()
        return list(source.resources.values())

    def load(self, smoke: bool = False) -> Any:
        pipeline = dlt_pipeline(
            pipeline_name=f"{self.name}_api",
            destination=dlt_destination(settings.raw_catalog_path("xeno_canto")),
            dataset_name=settings.raw_dataset_name("xeno_canto"),
            pipelines_dir=settings.dlt_data_dir,
            progress="log",
        )
        source = self._source()
        if smoke:
            source.add_limit(max_items=5)
        source = prepare_dlt_source(source)

        run_log = log.bind(
            pipeline=pipeline.pipeline_name,
            source="xeno_canto",
            schema=self.config.resolve_schema_name(),
            query=self._query,
            smoke=smoke,
        )
        started = pendulum.now()
        run_log.info("pipeline_start")
        info = pipeline.run(source)
        duration_ms = int((pendulum.now() - started).total_seconds() * 1000)
        run_log.info(
            "pipeline_complete",
            load_id=info.loads_ids[-1] if info.loads_ids else None,
            duration_ms=duration_ms,
            has_failed_jobs=info.has_failed_jobs,
        )
        return pipeline

    def validate_config(self) -> bool:
        return True


def create_pipeline(config: PipelineConfig) -> XenoCantoPipelineSource:
    return XenoCantoPipelineSource(config)
