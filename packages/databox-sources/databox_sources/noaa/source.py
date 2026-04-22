"""NOAA CDO API source pipeline using dlt."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from typing import Any

import dlt
import pendulum
from databox.config.pipeline_config import PipelineConfig
from databox.config.settings import settings
from dlt.sources.helpers import requests as dlt_requests
from dotenv import load_dotenv

from databox_sources._logging import get_logger

load_dotenv()

log = get_logger("databox_sources.noaa")

NOAA_API_BASE = "https://www.ncei.noaa.gov/cdo-web/api/v2"

DEFAULT_DATATYPES = "TMAX,TMIN,PRCP,SNOW,AWND"
DEFAULT_DATASET = "GHCND"
DEFAULT_LOCATION = "FIPS:04"
RATE_LIMIT_SLEEP = 0.25


def get_api_headers() -> dict[str, str]:
    api_token = os.getenv("NOAA_API_TOKEN")
    if not api_token:
        raise ValueError("NOAA_API_TOKEN not found in environment variables")
    return {"token": api_token, "Accept": "application/json"}


def process_weather_record(record: dict[str, Any], location_id: str) -> dict[str, Any]:
    return {
        "date": record.get("date"),
        "datatype": record.get("datatype"),
        "station": record.get("station"),
        "value": record.get("value"),
        "attributes": record.get("attributes", ""),
        "source": record.get("source", ""),
        "_location_id": location_id,
        "_loaded_at": pendulum.now().isoformat(),
    }


def process_station(station: dict[str, Any], location_id: str) -> dict[str, Any]:
    return {
        "id": station.get("id"),
        "name": station.get("name"),
        "latitude": station.get("latitude"),
        "longitude": station.get("longitude"),
        "elevation": station.get("elevation"),
        "elevation_unit": station.get("elevationUnit"),
        "mindate": station.get("mindate"),
        "maxdate": station.get("maxdate"),
        "datacoverage": station.get("datacoverage"),
        "_location_id": location_id,
        "_loaded_at": pendulum.now().isoformat(),
    }


def _paginate(
    url: str, headers: dict, params: dict, sleep: float = RATE_LIMIT_SLEEP
) -> Iterator[dict]:
    """Paginate through NOAA API results, respecting rate limits."""
    params = {**params, "limit": 1000, "offset": 0}

    while True:
        response = dlt_requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        if not results:
            break

        yield from results

        metadata = data.get("metadata", {}).get("resultset", {})
        count = metadata.get("count", 0)
        offset = params["offset"] + len(results)

        if offset >= count:
            break

        params["offset"] = offset
        time.sleep(sleep)


def _chunk_date_range(start: str, end: str, max_days: int = 365) -> list[tuple[str, str]]:
    """Split a date range into chunks that respect NOAA's max range limits.

    GHCND (daily) is limited to 1 year per request.
    """
    start_dt = pendulum.from_format(start, "YYYY-MM-DD")
    end_dt = pendulum.from_format(end, "YYYY-MM-DD")
    chunks = []
    current = start_dt

    while current < end_dt:
        chunk_end = min(current.add(days=max_days), end_dt)
        chunks.append((current.format("YYYY-MM-DD"), chunk_end.format("YYYY-MM-DD")))
        current = chunk_end

    return chunks


@dlt.source
def noaa_source(
    location_id: str = DEFAULT_LOCATION,
    dataset_id: str = DEFAULT_DATASET,
    days_back: int = 30,
    datatypes: str = DEFAULT_DATATYPES,
):
    loaded_at = pendulum.now().isoformat()
    end_date = pendulum.now()
    start_date = end_date.subtract(days=days_back)
    start_str = start_date.format("YYYY-MM-DD")
    end_str = end_date.format("YYYY-MM-DD")

    @dlt.resource(
        primary_key=["date", "datatype", "station"],
        write_disposition="merge",
        columns={
            "date": {"data_type": "text"},
            "datatype": {"data_type": "text"},
            "station": {"data_type": "text"},
            "value": {"data_type": "double"},
            "attributes": {"data_type": "text"},
            "source": {"data_type": "text"},
            "_location_id": {"data_type": "text"},
            "_loaded_at": {"data_type": "timestamp"},
        },
    )
    def daily_weather() -> Iterator[dict[str, Any]]:
        headers = get_api_headers()
        chunks = _chunk_date_range(start_str, end_str, max_days=365)

        for chunk_start, chunk_end in chunks:
            params = {
                "datasetid": dataset_id,
                "datatypeid": datatypes,
                "locationid": location_id,
                "startdate": chunk_start,
                "enddate": chunk_end,
                "units": "standard",
                "includemetadata": "true",
            }

            for record in _paginate(f"{NOAA_API_BASE}/data", headers, params):
                yield process_weather_record(record, location_id)

    @dlt.resource(
        primary_key="id",
        write_disposition="merge",
        columns={
            "id": {"data_type": "text"},
            "name": {"data_type": "text"},
            "latitude": {"data_type": "double"},
            "longitude": {"data_type": "double"},
            "elevation": {"data_type": "double"},
            "elevation_unit": {"data_type": "text"},
            "mindate": {"data_type": "text"},
            "maxdate": {"data_type": "text"},
            "datacoverage": {"data_type": "double"},
            "_location_id": {"data_type": "text"},
            "_loaded_at": {"data_type": "timestamp"},
        },
    )
    def stations() -> Iterator[dict[str, Any]]:
        headers = get_api_headers()
        params = {
            "datasetid": dataset_id,
            "locationid": location_id,
            "limit": 1000,
        }

        for station in _paginate(f"{NOAA_API_BASE}/stations", headers, params):
            yield process_station(station, location_id)

    @dlt.resource(
        primary_key="id",
        write_disposition="replace",
        columns={
            "id": {"data_type": "text"},
            "name": {"data_type": "text"},
            "datacoverage": {"data_type": "double"},
            "mindate": {"data_type": "text"},
            "maxdate": {"data_type": "text"},
            "_loaded_at": {"data_type": "timestamp"},
        },
    )
    def datasets() -> Iterator[dict[str, Any]]:
        headers = get_api_headers()
        url = f"{NOAA_API_BASE}/datasets/{dataset_id}"

        response = dlt_requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        data["_loaded_at"] = loaded_at
        yield data

    return [daily_weather, stations, datasets]


class NoaaPipelineSource:
    """NOAA pipeline source implementing the PipelineSource protocol."""

    def __init__(self, config: PipelineConfig) -> None:
        self.name = config.name
        self.config = config
        self._location = config.params.get("location_id", DEFAULT_LOCATION)
        self._dataset = config.params.get("dataset_id", DEFAULT_DATASET)
        self._days_back = config.params.get("days_back", 30)
        self._datatypes = config.params.get("datatypes", DEFAULT_DATATYPES)

    def resources(self):
        source = noaa_source(
            location_id=self._location,
            dataset_id=self._dataset,
            days_back=self._days_back,
            datatypes=self._datatypes,
        )
        return source.resources.values()

    def load(self, smoke: bool = False):
        schema_name = self.config.resolve_schema_name()
        pipeline = dlt.pipeline(
            pipeline_name=f"{self.name}_api",
            destination=dlt.destinations.duckdb(credentials=settings.raw_catalog_path("noaa")),
            dataset_name="main",
            pipelines_dir=settings.dlt_data_dir,
            progress="log",
        )

        source = noaa_source(
            location_id=self._location,
            dataset_id=self._dataset,
            days_back=self._days_back,
            datatypes=self._datatypes,
        )
        if smoke:
            source.add_limit(max_items=5)

        run_log = log.bind(
            pipeline=pipeline.pipeline_name,
            source="noaa",
            schema=schema_name,
            location=self._location,
            dataset=self._dataset,
            days_back=self._days_back,
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
        return bool(os.getenv("NOAA_API_TOKEN"))


def create_pipeline(config: PipelineConfig) -> NoaaPipelineSource:
    return NoaaPipelineSource(config)
