Status: recorded
Created: 2026-07-08
Updated: 2026-07-08
Relates-To: .10x/tickets/done/2026-07-08-add-open-meteo-trip-context-tool.md

# Evidence: Open-Meteo trip context tool

## What was observed

Implemented a request-time Open-Meteo tool for Birding Trip Copilot weather/elevation context. The tool is not a dlt source and does not add scheduled ingestion. It normalizes forecast/elevation responses for a latitude/longitude and outing window, handles source errors as planner caveats, and persists the used context as a trip-plan evidence artifact.

## Procedure and results

### Focused tests

```bash
.venv/bin/python -m pytest --no-cov tests/test_open_meteo_tool.py -q
```

Result:

```text
4 passed
```

Covered behavior:

- success path with mocked forecast and elevation responses,
- local outing-window filtering and unit normalization,
- unavailable-source behavior when both Open-Meteo calls fail,
- partial-source behavior when forecast returns no rows for the requested window,
- DuckDB persistence of one trip-plan evidence artifact.

### Lint, formatting, and type checks

```bash
.venv/bin/ruff check packages/databox/databox/agent_tools tests/test_open_meteo_tool.py
.venv/bin/ruff format --check packages/databox/databox/agent_tools tests/test_open_meteo_tool.py
.venv/bin/mypy packages/databox/databox/agent_tools tests/test_open_meteo_tool.py
```

Results:

```text
All checks passed!
3 files already formatted
Success: no issues found in 3 source files
```

## Example normalized output

The mocked success test produced an `OpenMeteoTripContext` equivalent to this shape:

```json
{
  "source": "open_meteo",
  "status": "available",
  "latitude": 34.54,
  "longitude": -112.47,
  "window_start": "2026-07-09T06:00:00",
  "window_end": "2026-07-09T09:00:00",
  "timezone": "America/Phoenix",
  "units": {
    "temperature": "°C",
    "relative_humidity": "%",
    "precipitation_probability": "%",
    "precipitation": "mm",
    "wind_speed": "km/h",
    "wind_gusts": "km/h",
    "elevation": "meter"
  },
  "forecast_summary": {
    "temperature_2m_min": 20.0,
    "temperature_2m_max": 23.0,
    "temperature_2m_avg": 21.5,
    "relative_humidity_2m_avg": 55.0,
    "precipitation_probability_max": 20.0,
    "precipitation_sum": 0.3,
    "wind_speed_10m_max": 7.0,
    "wind_gusts_10m_max": 10.0,
    "weather_codes": [0, 1, 2]
  },
  "elevation_m": 1642.0,
  "caveats": []
}
```

## Persistence target/shape

`persist_open_meteo_evidence(...)` writes one row per used Open-Meteo context into:

```text
birding_agent.trip_plan_evidence
```

Columns:

```text
evidence_id TEXT PRIMARY KEY
trip_plan_id TEXT NOT NULL
source TEXT NOT NULL
evidence_type TEXT NOT NULL
status TEXT NOT NULL
latitude DOUBLE
longitude DOUBLE
window_start TEXT
window_end TEXT
retrieved_at TEXT
summary_json TEXT NOT NULL
payload_json TEXT NOT NULL
caveats_json TEXT NOT NULL
```

The Open-Meteo row uses:

```text
source = open_meteo
evidence_type = weather_elevation_context
```

The test verified that the row can be queried from DuckDB and that `payload_json` contains the exact normalized context used by the planner-facing tool.

## API limitations and behavior

- Open-Meteo is called request-time through public endpoints:
  - `https://api.open-meteo.com/v1/forecast`
  - `https://api.open-meteo.com/v1/elevation`
- No API key or secret is read or recorded.
- Forecast times are treated as local wall-clock times for the requested Open-Meteo timezone. Callers should pass the outing window in the intended local time.
- Forecast defaults are metric: temperature Celsius, precipitation millimeters, wind km/h, probability percent, and elevation meters. Upstream `hourly_units` override the display/unit fields when returned.
- API failures do not raise from the public tool function. They return `partial` or `unavailable` context with caveats so the planner can surface source-availability limitations.

## What this supports

- The Open-Meteo ticket acceptance criteria are met without adding a scheduled dlt pipeline, ADK planner, SQLMesh planner model, DeepEval suite, or Dive.

## Limits

- Validation used deterministic mocked responses only; no live Open-Meteo HTTP call was made.
- Persistence creates a generic planner evidence table directly through DuckDB. Later planner/modeling tickets may choose to wrap or migrate this physical artifact into a more complete trip-plan schema.
