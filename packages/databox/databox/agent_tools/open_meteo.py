"""Open-Meteo request-time weather/elevation tool for birding trip plans.

Open-Meteo is intentionally implemented as a request-time tool, not a dlt
pipeline: trip plans use dynamic coordinates and future outing windows. The
used response can be persisted as one trip-plan evidence row so later Dive and
evaluation surfaces can reproduce what the planner saw.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from databox.agent_tools.persistence import (
    DuckDBConnection,
    ensure_birding_agent_persistence_tables,
)

FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
ELEVATION_ENDPOINT = "https://api.open-meteo.com/v1/elevation"

HOURLY_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation_probability",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
    "wind_gusts_10m",
)

JsonGetter = Callable[[str, Mapping[str, object]], dict[str, Any]]


@dataclass(frozen=True)
class OpenMeteoTripContext:
    """Normalized weather/elevation context for one planned outing window."""

    status: str
    latitude: float
    longitude: float
    window_start: str
    window_end: str
    timezone: str
    retrieved_at: str
    units: dict[str, str]
    forecast_summary: dict[str, Any]
    hourly: list[dict[str, Any]]
    elevation_m: float | None
    provenance: list[dict[str, Any]]
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": "open_meteo",
            "status": self.status,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "timezone": self.timezone,
            "retrieved_at": self.retrieved_at,
            "units": self.units,
            "forecast_summary": self.forecast_summary,
            "hourly": self.hourly,
            "elevation_m": self.elevation_m,
            "provenance": self.provenance,
            "caveats": self.caveats,
        }


def fetch_open_meteo_trip_context(
    *,
    latitude: float,
    longitude: float,
    start_at: datetime | str,
    end_at: datetime | str,
    timezone: str = "auto",
    http_get_json: JsonGetter | None = None,
) -> OpenMeteoTripContext:
    """Fetch normalized Open-Meteo context for a trip location/time window.

    Returned forecast units are normalized from Open-Meteo's documented metric
    defaults: temperature C, precipitation mm, wind km/h, probability percent,
    and elevation meters. Open-Meteo forecast times are treated as local
    wall-clock times for the requested timezone; callers should pass the outing
    window in the same intended local time.

    API failures do not raise. The returned context uses ``partial`` or
    ``unavailable`` status with caveats so the planner can surface an explicit
    source-availability caveat instead of crashing.
    """

    _validate_coordinates(latitude, longitude)
    start = _parse_datetime(start_at)
    end = _parse_datetime(end_at)
    if end <= start:
        raise ValueError("end_at must be after start_at")

    getter = http_get_json or _default_get_json
    retrieved_at = datetime.now(UTC).isoformat()
    caveats: list[str] = []
    provenance: list[dict[str, Any]] = []
    forecast_summary: dict[str, Any] = {}
    hourly_rows: list[dict[str, Any]] = []
    elevation_m: float | None = None
    units: dict[str, str] = {
        "temperature": "celsius",
        "relative_humidity": "percent",
        "precipitation_probability": "percent",
        "precipitation": "millimeter",
        "wind_speed": "km/h",
        "wind_gusts": "km/h",
        "elevation": "meter",
    }

    forecast_params: dict[str, object] = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(HOURLY_FIELDS),
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat(),
        "timezone": timezone,
    }
    try:
        forecast_response = getter(FORECAST_ENDPOINT, forecast_params)
        provenance.append(
            {
                "source": "open_meteo_forecast",
                "endpoint": FORECAST_ENDPOINT,
                "params": forecast_params,
            }
        )
        units.update(_extract_units(forecast_response.get("hourly_units")))
        hourly_rows = _extract_hourly_rows(forecast_response, start, end)
        forecast_summary = _summarize_hourly(hourly_rows)
        if not hourly_rows:
            caveats.append("Open-Meteo forecast returned no hourly rows for the requested window")
    except Exception as exc:  # noqa: BLE001 - source failures become planner caveats.
        caveats.append(f"Open-Meteo forecast unavailable: {exc}")

    elevation_params: dict[str, object] = {"latitude": latitude, "longitude": longitude}
    try:
        elevation_response = getter(ELEVATION_ENDPOINT, elevation_params)
        provenance.append(
            {
                "source": "open_meteo_elevation",
                "endpoint": ELEVATION_ENDPOINT,
                "params": elevation_params,
            }
        )
        elevation_m = _extract_elevation(elevation_response)
        if elevation_m is None:
            caveats.append("Open-Meteo elevation response did not include an elevation value")
    except Exception as exc:  # noqa: BLE001 - source failures become planner caveats.
        caveats.append(f"Open-Meteo elevation unavailable: {exc}")

    has_forecast = bool(hourly_rows)
    has_elevation = elevation_m is not None
    if has_forecast and has_elevation:
        status = "available"
    elif has_forecast or has_elevation:
        status = "partial"
    else:
        status = "unavailable"

    return OpenMeteoTripContext(
        status=status,
        latitude=latitude,
        longitude=longitude,
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        timezone=timezone,
        retrieved_at=retrieved_at,
        units=units,
        forecast_summary=forecast_summary,
        hourly=hourly_rows,
        elevation_m=elevation_m,
        provenance=provenance,
        caveats=caveats,
    )


def persist_open_meteo_evidence(
    connection: DuckDBConnection,
    context: OpenMeteoTripContext,
    *,
    trip_plan_id: str,
    evidence_id: str | None = None,
    schema: str = "birding_agent",
    table: str = "trip_plan_evidence",
) -> str:
    """Persist one Open-Meteo context as a trip-plan evidence artifact.

    The table is intentionally generic evidence storage, not a scheduled raw
    source table. Future planner/Dive work can join on ``trip_plan_id`` and
    inspect ``payload_json`` for the exact Open-Meteo context used by a plan.
    """

    evidence_id = evidence_id or f"open_meteo_{uuid.uuid4().hex}"
    payload = context.to_dict()
    summary = {
        "forecast_summary": context.forecast_summary,
        "elevation_m": context.elevation_m,
        "status": context.status,
    }
    schema_ident = _quote_identifier(schema)
    table_ident = _quote_identifier(table)
    qname = f"{schema_ident}.{table_ident}"

    ensure_birding_agent_persistence_tables(connection, schema=schema)
    connection.execute(f"DELETE FROM {qname} WHERE evidence_id = ?", [evidence_id])
    connection.execute(
        f"""
        INSERT INTO {qname} (
            evidence_id,
            trip_plan_id,
            recommendation_id,
            source,
            source_table,
            source_record_id,
            evidence_type,
            status,
            latitude,
            longitude,
            window_start,
            window_end,
            retrieved_at,
            summary_json,
            payload_json,
            caveats_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            evidence_id,
            trip_plan_id,
            None,
            "open_meteo",
            None,
            evidence_id,
            "weather_elevation_context",
            context.status,
            context.latitude,
            context.longitude,
            context.window_start,
            context.window_end,
            context.retrieved_at,
            json.dumps(summary, sort_keys=True),
            json.dumps(payload, sort_keys=True),
            json.dumps(context.caveats, sort_keys=True),
        ],
    )
    return evidence_id


def _default_get_json(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
    query = urlencode({key: str(value) for key, value in params.items()})
    url = f"{endpoint}?{query}"
    try:
        with urlopen(url, timeout=30) as response:  # noqa: S310 - fixed public Open-Meteo URLs.
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {endpoint}") from exc
    except URLError as exc:
        raise RuntimeError(f"network error from {endpoint}: {exc.reason}") from exc

    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"unexpected JSON response from {endpoint}")
    return cast(dict[str, Any], parsed)


def _validate_coordinates(latitude: float, longitude: float) -> None:
    if not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90")
    if not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")


def _parse_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _local_wall_clock(value: datetime) -> datetime:
    return value.replace(tzinfo=None)


def _extract_units(raw_units: object) -> dict[str, str]:
    if not isinstance(raw_units, dict):
        return {}
    mapping = {
        "temperature_2m": "temperature",
        "relative_humidity_2m": "relative_humidity",
        "precipitation_probability": "precipitation_probability",
        "precipitation": "precipitation",
        "wind_speed_10m": "wind_speed",
        "wind_gusts_10m": "wind_gusts",
    }
    extracted: dict[str, str] = {}
    for source_key, target_key in mapping.items():
        raw_value = raw_units.get(source_key)
        if isinstance(raw_value, str):
            extracted[target_key] = raw_value
    return extracted


def _extract_hourly_rows(
    forecast_response: Mapping[str, Any], start: datetime, end: datetime
) -> list[dict[str, Any]]:
    hourly = forecast_response.get("hourly")
    if not isinstance(hourly, dict):
        raise RuntimeError("forecast response missing hourly data")

    times = hourly.get("time")
    if not isinstance(times, list):
        raise RuntimeError("forecast response missing hourly time values")

    start_local = _local_wall_clock(start)
    end_local = _local_wall_clock(end)
    rows: list[dict[str, Any]] = []
    for idx, raw_time in enumerate(times):
        if not isinstance(raw_time, str):
            continue
        observed_at = datetime.fromisoformat(raw_time)
        if not start_local <= observed_at < end_local:
            continue
        row: dict[str, Any] = {"time": raw_time}
        for field_name in HOURLY_FIELDS:
            values = hourly.get(field_name)
            if isinstance(values, list) and idx < len(values):
                row[field_name] = values[idx]
        rows.append(row)
    return rows


def _summarize_hourly(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return {
        "temperature_2m_min": _min_number(rows, "temperature_2m"),
        "temperature_2m_max": _max_number(rows, "temperature_2m"),
        "temperature_2m_avg": _avg_number(rows, "temperature_2m"),
        "relative_humidity_2m_avg": _avg_number(rows, "relative_humidity_2m"),
        "precipitation_probability_max": _max_number(rows, "precipitation_probability"),
        "precipitation_sum": _sum_number(rows, "precipitation"),
        "wind_speed_10m_max": _max_number(rows, "wind_speed_10m"),
        "wind_gusts_10m_max": _max_number(rows, "wind_gusts_10m"),
        "weather_codes": sorted(
            {value for row in rows if isinstance((value := row.get("weather_code")), int)}
        ),
    }


def _numbers(rows: list[dict[str, Any]], field_name: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        raw_value = row.get(field_name)
        if isinstance(raw_value, int | float):
            values.append(float(raw_value))
    return values


def _min_number(rows: list[dict[str, Any]], field_name: str) -> float | None:
    values = _numbers(rows, field_name)
    return min(values) if values else None


def _max_number(rows: list[dict[str, Any]], field_name: str) -> float | None:
    values = _numbers(rows, field_name)
    return max(values) if values else None


def _sum_number(rows: list[dict[str, Any]], field_name: str) -> float | None:
    values = _numbers(rows, field_name)
    return round(sum(values), 3) if values else None


def _avg_number(rows: list[dict[str, Any]], field_name: str) -> float | None:
    values = _numbers(rows, field_name)
    return round(sum(values) / len(values), 3) if values else None


def _extract_elevation(elevation_response: Mapping[str, Any]) -> float | None:
    raw_elevation = elevation_response.get("elevation")
    if isinstance(raw_elevation, list) and raw_elevation:
        first_value = raw_elevation[0]
        if isinstance(first_value, int | float):
            return float(first_value)
    if isinstance(raw_elevation, int | float):
        return float(raw_elevation)
    return None


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
