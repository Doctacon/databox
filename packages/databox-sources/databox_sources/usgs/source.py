"""USGS Water Services API source pipeline using dlt.

Data: National Water Information System (NWIS) daily values.
No API key required.

Parameter codes:
  00060 — Discharge (streamflow), ft³/s
  00065 — Gage height, ft
  00010 — Water temperature, °C
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import dlt
import pendulum
from databox_config.pipeline_config import PipelineConfig
from databox_config.settings import settings
from dlt.sources.helpers import requests as dlt_requests

USGS_BASE = "https://waterservices.usgs.gov/nwis"
USGS_SITE_BASE = "https://waterservices.usgs.gov/nwis/site"

DEFAULT_STATE = "AZ"
DEFAULT_PARAMETER_CDS = "00060,00065,00010"
RATE_LIMIT_SLEEP = 0.2


def _daily_values_url(
    state_cd: str,
    parameter_cds: str,
    start_dt: str,
    end_dt: str,
) -> tuple[str, dict]:
    url = f"{USGS_BASE}/dv/"
    params = {
        "format": "json",
        "stateCd": state_cd,
        "parameterCd": parameter_cds,
        "startDT": start_dt,
        "endDT": end_dt,
        "siteStatus": "active",
    }
    return url, params


def _parse_daily_value_records(
    data: dict[str, Any],
    state_cd: str,
    loaded_at: str,
) -> Iterator[dict[str, Any]]:
    """Flatten USGS JSON response into one row per site/parameter/date."""
    time_series_list = data.get("value", {}).get("timeSeries", [])
    for ts in time_series_list:
        site_info = ts.get("sourceInfo", {})
        variable = ts.get("variable", {})
        site_no = site_info.get("siteCode", [{}])[0].get("value")
        site_name = site_info.get("siteName")
        lat = site_info.get("geoLocation", {}).get("geogLocation", {}).get("latitude")
        lon = site_info.get("geoLocation", {}).get("geogLocation", {}).get("longitude")
        param_cd = variable.get("variableCode", [{}])[0].get("value")
        param_name = variable.get("variableName")
        unit = variable.get("unit", {}).get("unitCode")

        for val_obj in ts.get("values", [{}])[0].get("value", []):
            raw_val = val_obj.get("value")
            raw_qualifiers = val_obj.get("qualifiers", [])
            qualifier = ",".join(
                q if isinstance(q, str) else q.get("qualifierCode", "") for q in raw_qualifiers
            )
            yield {
                "site_no": site_no,
                "site_name": site_name,
                "latitude": float(lat) if lat is not None else None,
                "longitude": float(lon) if lon is not None else None,
                "parameter_cd": param_cd,
                "parameter_name": param_name,
                "unit_cd": unit,
                "observation_date": val_obj.get("dateTime", "")[:10],
                "value": float(raw_val) if raw_val is not None and raw_val != "" else None,
                "qualifier": qualifier or None,
                "_state_cd": state_cd,
                "_loaded_at": loaded_at,
            }


def _chunk_date_range(start: str, end: str, max_days: int = 90) -> list[tuple[str, str]]:
    start_dt = pendulum.parse(start)
    end_dt = pendulum.parse(end)
    chunks: list[tuple[str, str]] = []
    current = start_dt
    while current < end_dt:
        chunk_end = min(current.add(days=max_days), end_dt)
        chunks.append((current.format("YYYY-MM-DD"), chunk_end.format("YYYY-MM-DD")))
        current = chunk_end
    return chunks


@dlt.source
def usgs_source(
    state_cd: str = DEFAULT_STATE,
    parameter_cds: str = DEFAULT_PARAMETER_CDS,
    days_back: int = 30,
):
    loaded_at = pendulum.now().isoformat()
    end_date = pendulum.now()
    start_date = end_date.subtract(days=days_back)
    start_str = start_date.format("YYYY-MM-DD")
    end_str = end_date.format("YYYY-MM-DD")

    @dlt.resource(
        primary_key=["site_no", "parameter_cd", "observation_date"],
        write_disposition="merge",
        columns={
            "site_no": {"data_type": "text"},
            "site_name": {"data_type": "text"},
            "latitude": {"data_type": "double"},
            "longitude": {"data_type": "double"},
            "parameter_cd": {"data_type": "text"},
            "parameter_name": {"data_type": "text"},
            "unit_cd": {"data_type": "text"},
            "observation_date": {"data_type": "text"},
            "value": {"data_type": "double"},
            "qualifier": {"data_type": "text"},
            "_state_cd": {"data_type": "text"},
            "_loaded_at": {"data_type": "timestamp"},
        },
    )
    def daily_values() -> Iterator[dict[str, Any]]:
        for chunk_start, chunk_end in _chunk_date_range(start_str, end_str):
            url, params = _daily_values_url(state_cd, parameter_cds, chunk_start, chunk_end)
            response = dlt_requests.get(url, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            yield from _parse_daily_value_records(response.json(), state_cd, loaded_at)
            time.sleep(RATE_LIMIT_SLEEP)

    @dlt.resource(
        primary_key="site_no",
        write_disposition="merge",
        columns={
            "site_no": {"data_type": "text"},
            "site_name": {"data_type": "text"},
            "site_type": {"data_type": "text"},
            "latitude": {"data_type": "double"},
            "longitude": {"data_type": "double"},
            "county_cd": {"data_type": "text"},
            "state_cd": {"data_type": "text"},
            "huc_cd": {"data_type": "text"},
            "drain_area_va": {"data_type": "double"},
            "begin_date": {"data_type": "text"},
            "end_date": {"data_type": "text"},
            "_loaded_at": {"data_type": "timestamp"},
        },
    )
    def sites() -> Iterator[dict[str, Any]]:
        params = {
            "format": "rdb",
            "stateCd": state_cd,
            "parameterCd": parameter_cds,
            "siteStatus": "active",
            "siteType": "ST",
            "outputDataTypeCd": "dv",
        }
        response = dlt_requests.get(USGS_SITE_BASE, params=params)
        response.raise_for_status()
        lines = [ln for ln in response.text.splitlines() if ln and not ln.startswith("#")]
        if len(lines) < 2:
            return
        headers = lines[0].split("\t")
        # skip format-description line (all dashes)
        for row in lines[2:]:
            cols = row.split("\t")
            if len(cols) < len(headers):
                continue
            rec = dict(zip(headers, cols, strict=False))
            yield {
                "site_no": rec.get("site_no"),
                "site_name": rec.get("station_nm"),
                "site_type": rec.get("site_tp_cd"),
                "latitude": _safe_float(rec.get("dec_lat_va")),
                "longitude": _safe_float(rec.get("dec_long_va")),
                "county_cd": rec.get("county_cd"),
                "state_cd": rec.get("state_cd"),
                "huc_cd": rec.get("huc_cd"),
                "drain_area_va": _safe_float(rec.get("drain_area_va")),
                "begin_date": rec.get("begin_date"),
                "end_date": rec.get("end_date"),
                "_loaded_at": loaded_at,
            }

    return [daily_values, sites]


def _safe_float(val: str | None) -> float | None:
    try:
        return float(val) if val else None
    except (ValueError, TypeError):
        return None


class UsgsPipelineSource:
    """USGS pipeline source implementing the PipelineSource protocol."""

    def __init__(self, config: PipelineConfig) -> None:
        self.name = config.name
        self.config = config
        self._state_cd = config.params.get("state_cd", DEFAULT_STATE)
        self._parameter_cds = config.params.get("parameter_cds", DEFAULT_PARAMETER_CDS)
        self._days_back = config.params.get("days_back", 30)

    def resources(self):
        source = usgs_source(
            state_cd=self._state_cd,
            parameter_cds=self._parameter_cds,
            days_back=self._days_back,
        )
        return source.resources.values()

    def load(self, smoke: bool = False):
        schema_name = self.config.resolve_schema_name()
        pipeline = dlt.pipeline(
            pipeline_name=f"{self.name}_api",
            destination=dlt.destinations.postgres(credentials=settings.database_url),
            dataset_name=schema_name,
            pipelines_dir=settings.dlt_data_dir,
            progress="log",
        )
        source = usgs_source(
            state_cd=self._state_cd,
            parameter_cds=self._parameter_cds,
            days_back=self._days_back,
        )
        if smoke:
            source.add_limit(max_items=5)
        print(f"Starting USGS pipeline [{schema_name}]{'  [SMOKE]' if smoke else ''}...")
        info = pipeline.run(source)

        print("\nUSGS data loaded successfully!")
        print(f"  Pipeline: {pipeline.pipeline_name}")
        print(f"  Schema: {schema_name}")
        print(f"  State: {self._state_cd}")
        print(f"  Parameters: {self._parameter_cds}")
        print(f"  Days back: {self._days_back}")
        print(f"\n{info}")
        return pipeline

    def validate_config(self) -> bool:
        return True  # USGS requires no API key


def create_pipeline(config: PipelineConfig) -> UsgsPipelineSource:
    return UsgsPipelineSource(config)
