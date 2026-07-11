"""Deterministic watched-bird matching after a successful transformed refresh."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

import duckdb
from pydantic import ValidationError

from databox.agent_tools.open_meteo import JsonGetter, fetch_open_meteo_trip_context
from databox.agents.cloudflare_workers_ai import (
    CLOUDFLARE_WORKERS_AI_MODEL,
    CloudflareConfigurationError,
    CloudflareWorkersAIClient,
    CloudflareWorkersAIError,
    WatchClusterPrompt,
    WatchReportModelClient,
    WatchReportSynthesisRequest,
)
from databox.bird_alert_outbox import enqueue_event_intent, suppress_event_outbox
from databox.config.settings import settings
from databox.target_planning import MILES_TO_KM, normalize_target_weather

ALERT_SCHEMA = "birding_alerts"
PERSONAL_SCHEMA = "birding_personal"
ARIZONA_TZ = ZoneInfo("America/Phoenix")
EARTH_RADIUS_KM = 6371.0088
FRESHNESS = timedelta(hours=48)
EVENT_HORIZON = timedelta(days=5)
RETENTION = timedelta(days=90)


@dataclass(frozen=True)
class WatchCluster:
    location_id: str
    location_name: str | None
    latitude: float
    longitude: float
    independent_submission_count: int
    latest_observation_at: str
    distance_km: float
    distance_miles: float
    evidence_loaded_at: str | None


@dataclass(frozen=True)
class EvaluationResult:
    run_id: str
    refresh_id: str
    status: Literal["completed", "failed"]
    watches_evaluated: int
    matches_created: int
    cancellations_resolved: int
    started_at: str
    completed_at: str | None


class WatchEvaluationError(RuntimeError):
    """Safe evaluator failure."""


def _utc(value: datetime | str) -> datetime:
    parsed = (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _observation_utc(value: datetime | str) -> datetime:
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ARIZONA_TZ)
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _rows(cursor: Any) -> list[dict[str, Any]]:
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = p2 - p1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _safe_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _event_intents_ddl(schema: str, table: str = "event_intents") -> str:
    return f"""
        CREATE TABLE {schema}.{_safe_identifier(table)} (
          species_code VARCHAR PRIMARY KEY, watch_id VARCHAR NOT NULL,
          activation_generation VARCHAR NOT NULL,
          event_uid VARCHAR UNIQUE NOT NULL, sequence BIGINT NOT NULL,
          method VARCHAR NOT NULL, status VARCHAR NOT NULL, report_id VARCHAR,
          source_report_id VARCHAR, morning_start VARCHAR, morning_end VARCHAR,
          event_horizon_end VARCHAR, location_id VARCHAR, location_name VARCHAR,
          latitude DOUBLE, longitude DOUBLE,
          last_accepted_sequence BIGINT, last_accepted_horizon_end VARCHAR,
          last_accepted_at VARCHAR, updated_at VARCHAR NOT NULL,
          CHECK (method IN ('REQUEST','CANCEL')),
          CHECK (status IN (
            'pending_request','pending_cancel','accepted','suppressed','cancelled','expired'
          )),
          CHECK (status <> 'pending_request' OR method = 'REQUEST'),
          CHECK (status <> 'pending_cancel' OR method = 'CANCEL'),
          CHECK (
            status NOT IN ('pending_request','pending_cancel')
            OR (source_report_id IS NOT NULL AND location_id IS NOT NULL)
          )
        )
    """


def _ensure_event_intents_table(
    connection: duckdb.DuckDBPyConnection,
    schema: str,
    *,
    migrate_pre_release: bool,
) -> None:
    columns = {
        str(row[0])
        for row in connection.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema=? AND table_name='event_intents'""",
            [ALERT_SCHEMA],
        ).fetchall()
    }
    if not columns:
        connection.execute(_event_intents_ddl(schema))
        return
    required = {"source_report_id", "location_id"}
    check_row = connection.execute(
        """SELECT count(*) FROM duckdb_constraints()
           WHERE schema_name=? AND table_name='event_intents'
             AND constraint_type='CHECK'""",
        [ALERT_SCHEMA],
    ).fetchone()
    check_count = int(check_row[0]) if check_row is not None else 0
    if required <= columns and check_count >= 5:
        return
    if not migrate_pre_release:
        raise ValueError("pre-release event intent migration requires an explicit transaction")
    migration_table = "event_intents_migration"
    connection.execute(f"DROP TABLE IF EXISTS {schema}.{_safe_identifier(migration_table)}")
    connection.execute(_event_intents_ddl(schema, migration_table))
    source_report = (
        "COALESCE(event.source_report_id, event.report_id)"
        if "source_report_id" in columns
        else "event.report_id"
    )
    location_id = (
        "COALESCE(event.location_id, report.confirmed_location_id)"
        if "location_id" in columns
        else "report.confirmed_location_id"
    )
    connection.execute(
        f"""INSERT INTO {schema}.{_safe_identifier(migration_table)} (
          species_code, watch_id, activation_generation, event_uid, sequence,
          method, status, report_id, source_report_id, morning_start, morning_end,
          event_horizon_end, location_id, location_name, latitude, longitude,
          last_accepted_sequence, last_accepted_horizon_end, last_accepted_at, updated_at
        )
        SELECT event.species_code, event.watch_id, event.activation_generation,
          event.event_uid, event.sequence, event.method, event.status, event.report_id,
          {source_report}, event.morning_start, event.morning_end,
          event.event_horizon_end, {location_id}, event.location_name,
          event.latitude, event.longitude, event.last_accepted_sequence,
          event.last_accepted_horizon_end, event.last_accepted_at, event.updated_at
        FROM {schema}.event_intents AS event
        LEFT JOIN {schema}.match_reports AS report
          ON report.report_id={source_report}"""
    )
    connection.execute(f"DROP TABLE {schema}.event_intents")
    connection.execute(
        f"ALTER TABLE {schema}.{_safe_identifier(migration_table)} RENAME TO event_intents"
    )


def ensure_alert_tables(
    connection: duckdb.DuckDBPyConnection, *, migrate_pre_release: bool = False
) -> None:
    """Ensure alert state; migration opt-in requires a caller-owned transaction."""

    schema = _safe_identifier(ALERT_SCHEMA)
    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.runtime_settings (
          setting_key VARCHAR PRIMARY KEY, setting_value VARCHAR NOT NULL
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.evaluation_runs (
          run_id VARCHAR PRIMARY KEY, refresh_id VARCHAR UNIQUE NOT NULL,
          status VARCHAR NOT NULL, watches_evaluated BIGINT NOT NULL,
          matches_created BIGINT NOT NULL, cancellations_resolved BIGINT NOT NULL,
          started_at VARCHAR NOT NULL, completed_at VARCHAR, safe_error_code VARCHAR,
          CHECK (status IN ('running','completed','failed'))
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.watch_evaluation_results (
          run_id VARCHAR NOT NULL, watch_id VARCHAR NOT NULL,
          activation_generation VARCHAR NOT NULL, species_code VARCHAR NOT NULL,
          decision VARCHAR NOT NULL, eligible_submission_count BIGINT NOT NULL,
          diagnostics_json VARCHAR NOT NULL, report_id VARCHAR, evaluated_at VARCHAR NOT NULL,
          PRIMARY KEY (run_id, watch_id, activation_generation),
          CHECK (decision IN ('matched','no_match','activation_changed'))
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.watch_activation_state (
          watch_id VARCHAR NOT NULL, activation_generation VARCHAR NOT NULL,
          species_code VARCHAR NOT NULL, activated_at VARCHAR NOT NULL,
          last_evaluated_at VARCHAR NOT NULL, last_run_id VARCHAR NOT NULL,
          PRIMARY KEY (watch_id, activation_generation)
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.processed_submissions (
          watch_id VARCHAR NOT NULL, source_observation_id VARCHAR NOT NULL,
          species_code VARCHAR NOT NULL, first_run_id VARCHAR NOT NULL,
          processed_at VARCHAR NOT NULL,
          PRIMARY KEY (watch_id, source_observation_id)
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.match_reports (
          report_id VARCHAR PRIMARY KEY, run_id VARCHAR NOT NULL, watch_id VARCHAR NOT NULL,
          activation_generation VARCHAR NOT NULL, species_code VARCHAR NOT NULL,
          common_name VARCHAR, scientific_name VARCHAR,
          watch_center_name VARCHAR NOT NULL, watch_center_latitude DOUBLE NOT NULL,
          watch_center_longitude DOUBLE NOT NULL, radius_miles DOUBLE NOT NULL,
          confirmed_location_id VARCHAR NOT NULL, confirmed_location_name VARCHAR,
          confirmed_latitude DOUBLE NOT NULL, confirmed_longitude DOUBLE NOT NULL,
          confirmed_distance_miles DOUBLE NOT NULL,
          independent_submission_count BIGINT NOT NULL,
          newest_observation_at VARCHAR NOT NULL, clusters_json VARCHAR NOT NULL,
          morning_start VARCHAR NOT NULL, morning_end VARCHAR NOT NULL,
          event_horizon_end VARCHAR NOT NULL, weather_json VARCHAR NOT NULL,
          caveats_json VARCHAR NOT NULL, emphasis_ids_json VARCHAR NOT NULL,
          report_status VARCHAR NOT NULL, evidence_freshness_at VARCHAR NOT NULL,
          model VARCHAR, fact_hash VARCHAR NOT NULL, created_at VARCHAR NOT NULL,
          resolved_at VARCHAR,
          CHECK (report_status IN ('ready','deterministic_degraded'))
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.model_traces (
          report_id VARCHAR PRIMARY KEY, model_status VARCHAR NOT NULL,
          model VARCHAR, fact_hash VARCHAR NOT NULL, created_at VARCHAR NOT NULL,
          CHECK (model_status IN ('grounded','degraded'))
        )
        """
    )
    _ensure_event_intents_table(
        connection,
        schema,
        migrate_pre_release=migrate_pre_release,
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema}.cancellation_resolutions (
          cancellation_request_id VARCHAR PRIMARY KEY, run_id VARCHAR NOT NULL,
          species_code VARCHAR NOT NULL, outcome VARCHAR NOT NULL, resolved_at VARCHAR NOT NULL,
          CHECK (outcome IN (
            'cancel_intent','request_suppressed','no_accepted_active_event'
          ))
        )
        """
    )


def _installation_id(connection: duckdb.DuckDBPyConnection) -> str:
    row = connection.execute(
        f"""SELECT setting_value FROM {ALERT_SCHEMA}.runtime_settings
            WHERE setting_key = 'installation_id'"""
    ).fetchone()
    if row:
        return str(row[0])
    value = str(uuid.uuid4())
    connection.execute(
        f"INSERT INTO {ALERT_SCHEMA}.runtime_settings VALUES ('installation_id', ?)", [value]
    )
    return value


def _event_uid(installation_id: str, species_code: str) -> str:
    digest = hashlib.sha256(f"{installation_id}|{species_code}".encode()).hexdigest()
    return f"databox-watch-{digest}@local"


def _sunrise_utc(day: date, latitude: float, longitude: float) -> datetime:
    """NOAA sunrise approximation, sufficient for deterministic local scheduling."""

    day_number = day.timetuple().tm_yday
    longitude_hour = longitude / 15
    approximate = day_number + ((6 - longitude_hour) / 24)
    anomaly = (0.9856 * approximate) - 3.289
    true_longitude = (
        anomaly
        + 1.916 * math.sin(math.radians(anomaly))
        + 0.020 * math.sin(math.radians(2 * anomaly))
        + 282.634
    ) % 360
    right_ascension = (
        math.degrees(math.atan(0.91764 * math.tan(math.radians(true_longitude)))) % 360
    )
    right_ascension += (math.floor(true_longitude / 90) * 90) - (
        math.floor(right_ascension / 90) * 90
    )
    right_ascension /= 15
    sin_declination = 0.39782 * math.sin(math.radians(true_longitude))
    cos_declination = math.cos(math.asin(sin_declination))
    cosine_hour = (
        math.cos(math.radians(90.833)) - sin_declination * math.sin(math.radians(latitude))
    ) / (cos_declination * math.cos(math.radians(latitude)))
    if not -1 <= cosine_hour <= 1:
        raise WatchEvaluationError("sunrise_unavailable")
    local_hour = 360 - math.degrees(math.acos(cosine_hour))
    local_hour /= 15
    utc_hour = (
        local_hour + right_ascension - (0.06571 * approximate) - 6.622 - longitude_hour
    ) % 24
    midnight = datetime.combine(day, time(), tzinfo=UTC)
    return midnight + timedelta(hours=utc_hour)


def select_morning_window(
    evaluation_at: datetime, latitude: float, longitude: float
) -> tuple[datetime, datetime, datetime]:
    evaluation_at = evaluation_at.astimezone(UTC)
    horizon = evaluation_at + EVENT_HORIZON
    local_day = evaluation_at.astimezone(ARIZONA_TZ).date()
    for offset in range(6):
        sunrise = _sunrise_utc(local_day + timedelta(days=offset), latitude, longitude)
        start, end = sunrise - timedelta(hours=1), sunrise + timedelta(hours=1)
        if start > evaluation_at and end <= horizon:
            return start, end, horizon
    raise WatchEvaluationError("morning_window_unavailable")


def _active_watches(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    try:
        return _rows(
            connection.execute(
                f"""
                SELECT w.species_code, w.watch_id, w.activation_generation, w.activated_at,
                       w.center_name, w.center_latitude, w.center_longitude,
                       w.center_timezone, w.radius_miles,
                       c.common_name, c.scientific_name
                FROM {PERSONAL_SCHEMA}.watches AS w
                LEFT JOIN birding_agent.arizona_species_catalog AS c USING (species_code)
                WHERE w.active IS TRUE
                ORDER BY w.species_code
                """
            )
        )
    except duckdb.CatalogException:
        return []


def _processed_ids(connection: duckdb.DuckDBPyConnection, watch_id: str) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            f"""SELECT source_observation_id FROM {ALERT_SCHEMA}.processed_submissions
                WHERE watch_id = ?""",
            [watch_id],
        ).fetchall()
    }


def _candidate_rows(
    connection: duckdb.DuckDBPyConnection, species_code: str
) -> list[dict[str, Any]]:
    return _rows(
        connection.execute(
            """
            SELECT source_observation_id, is_valid, is_reviewed, is_location_private,
                   location_id,
                   CASE WHEN is_location_private IS FALSE THEN location_name END AS location_name,
                   CASE WHEN is_location_private IS FALSE THEN latitude END AS latitude,
                   CASE WHEN is_location_private IS FALSE THEN longitude END AS longitude,
                   observation_datetime, loaded_at, bird_observation_sk, dlt_id
            FROM environmental_observations.fact_bird_observation
            WHERE species_code = ? AND region_code = 'US-AZ'
            """,
            [species_code],
        )
    )


def _eligible_submissions(
    connection: duckdb.DuckDBPyConnection,
    watch: Mapping[str, Any],
    evaluation_at: datetime,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    diagnostics: Counter[str] = Counter()
    eligible: dict[str, dict[str, Any]] = {}
    processed = _processed_ids(connection, str(watch["watch_id"]))
    activation = _utc(str(watch["activated_at"]))
    cutoff = evaluation_at - FRESHNESS
    radius_km = float(watch["radius_miles"]) * MILES_TO_KM
    for row in _candidate_rows(connection, str(watch["species_code"])):
        source_id = row["source_observation_id"]
        if source_id is None:
            diagnostics["missing_submission_identity"] += 1
            continue
        source_id = str(source_id)
        if not source_id or len(source_id) > 256:
            diagnostics["invalid_submission_identity"] += 1
            continue
        if row["is_valid"] is not True:
            diagnostics["invalid"] += 1
            continue
        if row["is_reviewed"] is not True:
            diagnostics["unreviewed"] += 1
            continue
        if row["is_location_private"] is not False:
            diagnostics["private"] += 1
            continue
        if row["location_id"] is None or row["latitude"] is None or row["longitude"] is None:
            diagnostics["missing_public_destination"] += 1
            continue
        location_id = str(row["location_id"])
        location_name = row["location_name"]
        if (
            not location_id
            or len(location_id) > 128
            or (location_name is not None and len(str(location_name)) > 300)
        ):
            diagnostics["invalid_public_destination"] += 1
            continue
        observed = _observation_utc(row["observation_datetime"])
        if observed <= activation:
            diagnostics["pre_activation"] += 1
            continue
        if observed < cutoff:
            diagnostics["stale"] += 1
            continue
        if observed > evaluation_at:
            diagnostics["future"] += 1
            continue
        latitude, longitude = float(row["latitude"]), float(row["longitude"])
        if not (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            diagnostics["invalid_coordinates"] += 1
            continue
        distance = _haversine_km(
            float(watch["center_latitude"]),
            float(watch["center_longitude"]),
            latitude,
            longitude,
        )
        if distance > radius_km:
            diagnostics["outside_radius"] += 1
            continue
        if source_id in processed:
            diagnostics["already_processed"] += 1
            continue
        row = dict(row)
        row.update(
            source_observation_id=source_id,
            observed_at_utc=observed,
            distance_km=distance,
        )
        existing = eligible.get(source_id)
        row_key = (
            observed,
            _utc(str(row["loaded_at"]))
            if row["loaded_at"] is not None
            else datetime.min.replace(tzinfo=UTC),
            str(row["bird_observation_sk"] or ""),
            str(row["dlt_id"] or ""),
        )
        if existing is None:
            eligible[source_id] = row
        else:
            diagnostics["duplicate_source_row"] += 1
            existing_key = (
                existing["observed_at_utc"],
                _utc(str(existing["loaded_at"]))
                if existing["loaded_at"] is not None
                else datetime.min.replace(tzinfo=UTC),
                str(existing["bird_observation_sk"] or ""),
                str(existing["dlt_id"] or ""),
            )
            if row_key > existing_key:
                eligible[source_id] = row
    return list(eligible.values()), diagnostics


def cluster_submissions(rows: list[dict[str, Any]]) -> list[WatchCluster]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["location_id"])].append(row)
    clusters: list[WatchCluster] = []
    for location_id, items in grouped.items():
        newest = max(
            items,
            key=lambda row: (
                row["observed_at_utc"],
                _utc(str(row["loaded_at"]))
                if row["loaded_at"] is not None
                else datetime.min.replace(tzinfo=UTC),
                str(row["source_observation_id"]),
                str(row["bird_observation_sk"] or ""),
                str(row["dlt_id"] or ""),
            ),
        )
        distance_km = float(newest["distance_km"])
        clusters.append(
            WatchCluster(
                location_id=location_id,
                location_name=str(newest["location_name"])
                if newest["location_name"] is not None
                else None,
                latitude=float(newest["latitude"]),
                longitude=float(newest["longitude"]),
                independent_submission_count=len(items),
                latest_observation_at=_iso(newest["observed_at_utc"]),
                distance_km=round(distance_km, 3),
                distance_miles=round(distance_km / MILES_TO_KM, 3),
                evidence_loaded_at=max(
                    (
                        _iso(_utc(str(item["loaded_at"])))
                        for item in items
                        if item["loaded_at"] is not None
                    ),
                    default=None,
                ),
            )
        )
    clusters.sort(
        key=lambda cluster: (
            -cluster.independent_submission_count,
            -_utc(cluster.latest_observation_at).timestamp(),
            cluster.distance_km,
            cluster.location_name or "",
            cluster.location_id,
        )
    )
    return clusters[:10]


def _caveats(clusters: list[WatchCluster], weather_caveats: list[str]) -> list[str]:
    result = [
        "Recent public observations do not guarantee that the bird remains present.",
        "Verify current site access and posted restrictions before visiting.",
        "The alert uses only valid, reviewed, non-private eBird evidence within 48 hours.",
    ]
    if any("(private)" in (item.location_name or "").lower() for item in clusters):
        result.append(
            "A public observation location name indicates restricted access; verify permission."
        )
    result.extend(weather_caveats[:10])
    return result[:20]


def _report_request(
    watch: Mapping[str, Any],
    clusters: list[WatchCluster],
    morning_start: datetime,
    morning_end: datetime,
    horizon: datetime,
    weather: Any,
    caveats: list[str],
) -> WatchReportSynthesisRequest:
    freshness = max(cluster.latest_observation_at for cluster in clusters)
    return WatchReportSynthesisRequest(
        species_code=str(watch["species_code"]),
        common_name=str(watch["common_name"]) if watch["common_name"] is not None else None,
        scientific_name=str(watch["scientific_name"])
        if watch["scientific_name"] is not None
        else None,
        confirmed_location=WatchClusterPrompt(**asdict(clusters[0])),
        morning_start=_iso(morning_start),
        morning_end=_iso(morning_end),
        event_horizon_end=_iso(horizon),
        evidence_freshness_at=freshness,
        weather=weather,
        caveats=caveats,
    )


def _record_activation_state(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    watch: Mapping[str, Any],
    evaluated_at: str,
) -> None:
    connection.execute(
        f"""INSERT INTO {ALERT_SCHEMA}.watch_activation_state VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (watch_id, activation_generation) DO UPDATE SET
              last_evaluated_at=excluded.last_evaluated_at,
              last_run_id=excluded.last_run_id""",
        [
            watch["watch_id"],
            watch["activation_generation"],
            watch["species_code"],
            watch["activated_at"],
            evaluated_at,
            run_id,
        ],
    )


def _persist_no_match(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    watch: Mapping[str, Any],
    diagnostics: Counter[str],
    evaluated_at: str,
) -> None:
    connection.execute(
        f"""INSERT INTO {ALERT_SCHEMA}.watch_evaluation_results VALUES
        (?, ?, ?, ?, 'no_match', 0, ?, NULL, ?)""",
        [
            run_id,
            watch["watch_id"],
            watch["activation_generation"],
            watch["species_code"],
            json.dumps(dict(sorted(diagnostics.items())), separators=(",", ":")),
            evaluated_at,
        ],
    )


def _persist_match(
    connection: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    watch: Mapping[str, Any],
    submissions: list[dict[str, Any]],
    diagnostics: Counter[str],
    clusters: list[WatchCluster],
    morning_start: datetime,
    morning_end: datetime,
    horizon: datetime,
    weather: Any,
    caveats: list[str],
    emphasis_ids: list[str],
    report_status: str,
    model: str | None,
    fact_hash: str,
    evaluated_at: str,
) -> str:
    current = connection.execute(
        f"""SELECT active, activation_generation FROM {PERSONAL_SCHEMA}.watches
        WHERE species_code = ? AND watch_id = ?""",
        [watch["species_code"], watch["watch_id"]],
    ).fetchone()
    if (
        current is None
        or current[0] is not True
        or str(current[1]) != str(watch["activation_generation"])
    ):
        connection.execute(
            f"""INSERT INTO {ALERT_SCHEMA}.watch_evaluation_results VALUES
            (?, ?, ?, ?, 'activation_changed', 0, ?, NULL, ?)""",
            [
                run_id,
                watch["watch_id"],
                watch["activation_generation"],
                watch["species_code"],
                json.dumps({"activation_changed": 1}),
                evaluated_at,
            ],
        )
        return ""
    report_id = f"watch_report_{uuid.uuid4().hex}"
    confirmed = clusters[0]
    evidence_freshness = max(cluster.latest_observation_at for cluster in clusters)
    report_placeholders = ", ".join("?" for _ in range(30))
    connection.execute(
        f"INSERT INTO {ALERT_SCHEMA}.match_reports VALUES ({report_placeholders}, NULL)",
        [
            report_id,
            run_id,
            watch["watch_id"],
            watch["activation_generation"],
            watch["species_code"],
            watch["common_name"],
            watch["scientific_name"],
            watch["center_name"],
            watch["center_latitude"],
            watch["center_longitude"],
            watch["radius_miles"],
            confirmed.location_id,
            confirmed.location_name,
            confirmed.latitude,
            confirmed.longitude,
            confirmed.distance_miles,
            confirmed.independent_submission_count,
            confirmed.latest_observation_at,
            json.dumps([asdict(item) for item in clusters], separators=(",", ":"), sort_keys=True),
            _iso(morning_start),
            _iso(morning_end),
            _iso(horizon),
            weather.model_dump_json(),
            json.dumps(caveats, separators=(",", ":")),
            json.dumps(emphasis_ids, separators=(",", ":")),
            report_status,
            evidence_freshness,
            model,
            fact_hash,
            evaluated_at,
        ],
    )
    for row in submissions:
        connection.execute(
            f"""INSERT INTO {ALERT_SCHEMA}.processed_submissions VALUES (?, ?, ?, ?, ?)""",
            [
                watch["watch_id"],
                row["source_observation_id"],
                watch["species_code"],
                run_id,
                evaluated_at,
            ],
        )
    connection.execute(
        f"""INSERT INTO {ALERT_SCHEMA}.watch_evaluation_results VALUES
        (?, ?, ?, ?, 'matched', ?, ?, ?, ?)""",
        [
            run_id,
            watch["watch_id"],
            watch["activation_generation"],
            watch["species_code"],
            len(submissions),
            json.dumps(dict(sorted(diagnostics.items())), separators=(",", ":")),
            report_id,
            evaluated_at,
        ],
    )
    connection.execute(
        f"INSERT INTO {ALERT_SCHEMA}.model_traces VALUES (?, ?, ?, ?, ?)",
        [
            report_id,
            "grounded" if report_status == "ready" else "degraded",
            model,
            fact_hash,
            evaluated_at,
        ],
    )
    existing = connection.execute(
        f"""SELECT event_uid, sequence, last_accepted_sequence,
                   last_accepted_horizon_end, last_accepted_at, report_id
            FROM {ALERT_SCHEMA}.event_intents WHERE species_code = ?""",
        [watch["species_code"]],
    ).fetchone()
    if existing:
        uid, sequence, accepted_sequence, accepted_horizon, accepted_at, prior_report_id = existing
        sequence = int(sequence) + 1
        if prior_report_id is not None:
            connection.execute(
                f"""UPDATE {ALERT_SCHEMA}.match_reports
                    SET resolved_at = COALESCE(resolved_at, ?)
                    WHERE report_id = ?""",
                [evaluated_at, prior_report_id],
            )
    else:
        uid = _event_uid(_installation_id(connection), str(watch["species_code"]))
        sequence, accepted_sequence, accepted_horizon, accepted_at = 0, None, None, None
    connection.execute(
        f"DELETE FROM {ALERT_SCHEMA}.event_intents WHERE species_code = ?",
        [watch["species_code"]],
    )
    connection.execute(
        f"""INSERT INTO {ALERT_SCHEMA}.event_intents (
          species_code, watch_id, activation_generation, event_uid, sequence,
          method, status, report_id, source_report_id, morning_start, morning_end,
          event_horizon_end, location_id, location_name, latitude, longitude,
          last_accepted_sequence, last_accepted_horizon_end, last_accepted_at, updated_at
        ) VALUES (
          ?, ?, ?, ?, ?, 'REQUEST', 'pending_request', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )""",
        [
            watch["species_code"],
            watch["watch_id"],
            watch["activation_generation"],
            uid,
            sequence,
            report_id,
            report_id,
            _iso(morning_start),
            _iso(morning_end),
            _iso(horizon),
            confirmed.location_id,
            confirmed.location_name or f"eBird location {confirmed.location_id}",
            confirmed.latitude,
            confirmed.longitude,
            accepted_sequence,
            accepted_horizon,
            accepted_at,
            evaluated_at,
        ],
    )
    enqueue_event_intent(
        connection,
        str(watch["species_code"]),
        now=_utc(evaluated_at),
        in_transaction=True,
    )
    return report_id


def _expire_events(connection: duckdb.DuckDBPyConnection, evaluation_at: datetime) -> int:
    """End elapsed event intents naturally while retaining UID and sequence state."""

    now = _iso(evaluation_at)
    rows = connection.execute(
        f"""SELECT species_code, report_id, event_uid, sequence
            FROM {ALERT_SCHEMA}.event_intents
            WHERE status NOT IN ('cancelled', 'expired')
              AND event_horizon_end IS NOT NULL AND event_horizon_end <= ?""",
        [now],
    ).fetchall()
    if not rows:
        return 0
    connection.execute("BEGIN TRANSACTION")
    try:
        for species_code, report_id, event_uid, sequence in rows:
            suppress_event_outbox(
                connection,
                event_uid=str(event_uid),
                sequence=int(sequence),
                now=evaluation_at,
                reason="natural_expiry",
                in_transaction=True,
            )
            if report_id is not None:
                connection.execute(
                    f"""UPDATE {ALERT_SCHEMA}.match_reports
                        SET resolved_at = COALESCE(resolved_at, ?)
                        WHERE report_id = ?""",
                    [now, report_id],
                )
            connection.execute(
                f"""UPDATE {ALERT_SCHEMA}.event_intents
                    SET status='expired', report_id=NULL, source_report_id=NULL,
                        morning_start=NULL, morning_end=NULL, event_horizon_end=NULL,
                        location_id=NULL, location_name=NULL, latitude=NULL,
                        longitude=NULL, updated_at=?
                    WHERE species_code=?""",
                [now, species_code],
            )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    return len(rows)


def _resolve_cancellations(
    connection: duckdb.DuckDBPyConnection, run_id: str, evaluation_at: datetime
) -> int:
    try:
        requests = _rows(
            connection.execute(
                f"""SELECT cancellation_request_id, species_code, watch_id,
                           activation_generation, reason, requested_at
                    FROM {PERSONAL_SCHEMA}.watch_cancellation_requests
                    ORDER BY requested_at, cancellation_request_id"""
            )
        )
    except duckdb.CatalogException:
        return 0
    resolved = 0
    for request in requests:
        connection.execute("BEGIN TRANSACTION")
        try:
            event = connection.execute(
                f"""SELECT event_uid, sequence, last_accepted_sequence,
                           last_accepted_horizon_end, last_accepted_at, report_id, status
                    FROM {ALERT_SCHEMA}.event_intents
                    WHERE species_code = ? AND watch_id = ?
                      AND activation_generation = ?""",
                [
                    request["species_code"],
                    request["watch_id"],
                    request["activation_generation"],
                ],
            ).fetchone()
            accepted_active = bool(
                event is not None
                and event[4] is not None
                and event[3] is not None
                and str(event[6]) not in {"pending_cancel", "cancelled", "expired"}
                and _utc(str(event[3])) > evaluation_at
            )
            outcome = "no_accepted_active_event"
            if accepted_active and event is not None:
                if event[5] is not None:
                    connection.execute(
                        f"""UPDATE {ALERT_SCHEMA}.match_reports
                            SET resolved_at = COALESCE(resolved_at, ?)
                            WHERE report_id = ?""",
                        [_iso(evaluation_at), event[5]],
                    )
                connection.execute(
                    f"""UPDATE {ALERT_SCHEMA}.event_intents
                        SET sequence = ?, method = 'CANCEL', status = 'pending_cancel',
                            report_id = NULL, updated_at = ? WHERE species_code = ?""",
                    [int(event[1]) + 1, _iso(evaluation_at), request["species_code"]],
                )
                enqueue_event_intent(
                    connection,
                    str(request["species_code"]),
                    now=evaluation_at,
                    in_transaction=True,
                )
                outcome = "cancel_intent"
            elif event is not None and str(event[6]) == "pending_request":
                suppress_event_outbox(
                    connection,
                    event_uid=str(event[0]),
                    sequence=int(event[1]),
                    now=evaluation_at,
                    reason="watch_inactive_before_acceptance",
                    in_transaction=True,
                )
                if event[5] is not None:
                    connection.execute(
                        f"""UPDATE {ALERT_SCHEMA}.match_reports
                            SET resolved_at = COALESCE(resolved_at, ?)
                            WHERE report_id = ?""",
                        [_iso(evaluation_at), event[5]],
                    )
                connection.execute(
                    f"""UPDATE {ALERT_SCHEMA}.event_intents
                        SET status='suppressed', report_id=NULL, source_report_id=NULL,
                            morning_start=NULL, morning_end=NULL, event_horizon_end=NULL,
                            location_id=NULL, location_name=NULL, latitude=NULL,
                            longitude=NULL, last_accepted_sequence=NULL,
                            last_accepted_horizon_end=NULL, last_accepted_at=NULL, updated_at=?
                        WHERE species_code=?""",
                    [_iso(evaluation_at), request["species_code"]],
                )
                outcome = "request_suppressed"
            connection.execute(
                f"""INSERT OR IGNORE INTO {ALERT_SCHEMA}.cancellation_resolutions
                    VALUES (?, ?, ?, ?, ?)""",
                [
                    request["cancellation_request_id"],
                    run_id,
                    request["species_code"],
                    outcome,
                    _iso(evaluation_at),
                ],
            )
            connection.execute(
                f"""DELETE FROM {PERSONAL_SCHEMA}.watch_cancellation_requests
                    WHERE cancellation_request_id = ?""",
                [request["cancellation_request_id"]],
            )
            connection.execute("COMMIT")
            resolved += 1
        except Exception:
            connection.execute("ROLLBACK")
            raise
    return resolved


def evaluate_watched_birds(
    connection: duckdb.DuckDBPyConnection,
    *,
    refresh_id: str,
    evaluation_at: datetime | None = None,
    weather_getter: JsonGetter | None = None,
    model_client: WatchReportModelClient | None = None,
) -> EvaluationResult:
    """Evaluate each active watch once for one successful transformed refresh."""

    if not refresh_id or len(refresh_id) > 128:
        raise ValueError("refresh_id must be between 1 and 128 characters")
    now = (evaluation_at or datetime.now(UTC)).astimezone(UTC)
    run_id = "watch_eval_" + hashlib.sha256(refresh_id.encode()).hexdigest()
    connection.execute("BEGIN TRANSACTION")
    started_at = _iso(now)
    try:
        ensure_alert_tables(connection, migrate_pre_release=True)
        existing = connection.execute(
            f"SELECT * FROM {ALERT_SCHEMA}.evaluation_runs WHERE refresh_id = ?", [refresh_id]
        ).fetchone()
        if existing and str(existing[2]) == "completed":
            connection.execute("COMMIT")
            return EvaluationResult(
                run_id=str(existing[0]),
                refresh_id=str(existing[1]),
                status="completed",
                watches_evaluated=int(existing[3]),
                matches_created=int(existing[4]),
                cancellations_resolved=int(existing[5]),
                started_at=str(existing[6]),
                completed_at=str(existing[7]) if existing[7] is not None else None,
            )
        if existing:
            started_at = str(existing[6])
            connection.execute(
                f"""UPDATE {ALERT_SCHEMA}.evaluation_runs SET status='running',
                    completed_at=NULL, safe_error_code=NULL WHERE run_id=?""",
                [run_id],
            )
        else:
            connection.execute(
                f"""INSERT INTO {ALERT_SCHEMA}.evaluation_runs VALUES
                (?, ?, 'running', 0, 0, 0, ?, NULL, NULL)""",
                [run_id, refresh_id, started_at],
            )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise

    watches_evaluated = 0
    matches_created = 0
    cancellations_resolved = 0
    try:
        _expire_events(connection, now)
        cancellations_resolved = _resolve_cancellations(connection, run_id, now)
        for watch in _active_watches(connection):
            prior = connection.execute(
                f"""SELECT decision FROM {ALERT_SCHEMA}.watch_evaluation_results
                    WHERE run_id=? AND watch_id=? AND activation_generation=?""",
                [run_id, watch["watch_id"], watch["activation_generation"]],
            ).fetchone()
            if prior is not None:
                continue
            submissions, diagnostics = _eligible_submissions(connection, watch, now)
            watches_evaluated += 1
            if not submissions:
                connection.execute("BEGIN TRANSACTION")
                try:
                    _persist_no_match(connection, run_id, watch, diagnostics, _iso(now))
                    _record_activation_state(connection, run_id, watch, _iso(now))
                    connection.execute("COMMIT")
                except Exception:
                    connection.execute("ROLLBACK")
                    raise
                continue
            clusters = cluster_submissions(submissions)
            confirmed = clusters[0]
            morning_start, morning_end, horizon = select_morning_window(
                now, confirmed.latitude, confirmed.longitude
            )
            weather_context = fetch_open_meteo_trip_context(
                latitude=confirmed.latitude,
                longitude=confirmed.longitude,
                start_at=morning_start.astimezone(ARIZONA_TZ).replace(tzinfo=None),
                end_at=morning_end.astimezone(ARIZONA_TZ).replace(tzinfo=None),
                timezone="America/Phoenix",
                http_get_json=weather_getter,
            )
            weather = normalize_target_weather(weather_context)
            caveats = _caveats(clusters, weather.caveats)
            report_request = _report_request(
                watch, clusters, morning_start, morning_end, horizon, weather, caveats
            )
            report_status = "deterministic_degraded"
            model: str | None = None
            emphasis_ids: list[str] = ["freshness", "confirmed_location", "uncertainty"]
            if model_client is not None and model_client.model == CLOUDFLARE_WORKERS_AI_MODEL:
                try:
                    synthesis = model_client.synthesize_watch_report(report_request)
                    if synthesis.grounding.species_code != report_request.species_code:
                        raise ValueError("changed species grounding")
                    if synthesis.grounding.fact_hash != report_request.fact_hash:
                        raise ValueError("changed fact grounding")
                    emphasis_ids = list(synthesis.emphasis_ids)
                    report_status = "ready"
                    model = model_client.model
                except (CloudflareWorkersAIError, ValidationError, ValueError):
                    caveats = [
                        *caveats,
                        "Cloudflare GLM 5.2 enrichment was unavailable; "
                        "deterministic facts are shown.",
                    ][:20]
            else:
                caveats = [
                    *caveats,
                    "Cloudflare GLM 5.2 enrichment was unavailable; deterministic facts are shown.",
                ][:20]
            connection.execute("BEGIN TRANSACTION")
            try:
                report_id = _persist_match(
                    connection,
                    run_id=run_id,
                    watch=watch,
                    submissions=submissions,
                    diagnostics=diagnostics,
                    clusters=clusters,
                    morning_start=morning_start,
                    morning_end=morning_end,
                    horizon=horizon,
                    weather=weather,
                    caveats=caveats,
                    emphasis_ids=emphasis_ids,
                    report_status=report_status,
                    model=model,
                    fact_hash=report_request.fact_hash,
                    evaluated_at=_iso(now),
                )
                if report_id:
                    _record_activation_state(connection, run_id, watch, _iso(now))
                connection.execute("COMMIT")
                if report_id:
                    matches_created += 1
            except Exception:
                connection.execute("ROLLBACK")
                raise
        result_counts = connection.execute(
            f"""SELECT count(*), count(*) FILTER (WHERE decision='matched')
                FROM {ALERT_SCHEMA}.watch_evaluation_results WHERE run_id=?""",
            [run_id],
        ).fetchone()
        cancellation_count = connection.execute(
            f"SELECT count(*) FROM {ALERT_SCHEMA}.cancellation_resolutions WHERE run_id=?",
            [run_id],
        ).fetchone()
        watches_evaluated = int(result_counts[0]) if result_counts else 0
        matches_created = int(result_counts[1]) if result_counts else 0
        cancellations_resolved = int(cancellation_count[0]) if cancellation_count else 0
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.evaluation_runs
                SET status='completed', watches_evaluated=?, matches_created=?,
                    cancellations_resolved=?, completed_at=? WHERE run_id=?""",
            [watches_evaluated, matches_created, cancellations_resolved, _iso(now), run_id],
        )
    except Exception:
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.evaluation_runs
                SET status='failed', watches_evaluated=?, matches_created=?,
                    cancellations_resolved=?, completed_at=?, safe_error_code=? WHERE run_id=?""",
            [
                watches_evaluated,
                matches_created,
                cancellations_resolved,
                _iso(now),
                "evaluation_failed",
                run_id,
            ],
        )
        raise
    return EvaluationResult(
        run_id=run_id,
        refresh_id=refresh_id,
        status="completed",
        watches_evaluated=watches_evaluated,
        matches_created=matches_created,
        cancellations_resolved=cancellations_resolved,
        started_at=started_at,
        completed_at=_iso(now),
    )


def run_watched_bird_evaluator(database_path: str, refresh_id: str) -> EvaluationResult:
    """Production single-writer entrypoint called only by the full-refresh seam."""

    try:
        model_client: WatchReportModelClient | None = cast(
            WatchReportModelClient, CloudflareWorkersAIClient.from_settings(settings)
        )
    except CloudflareConfigurationError:
        model_client = None
    connection = duckdb.connect(database_path)
    try:
        return evaluate_watched_birds(connection, refresh_id=refresh_id, model_client=model_client)
    finally:
        connection.close()


def load_evaluation_runs(
    connection: duckdb.DuckDBPyConnection, *, limit: int = 100
) -> list[dict[str, Any]]:
    try:
        return _rows(
            connection.execute(
                f"""SELECT run_id, refresh_id, status, watches_evaluated,
                           matches_created, cancellations_resolved, started_at, completed_at,
                           safe_error_code
                    FROM {ALERT_SCHEMA}.evaluation_runs
                    ORDER BY started_at DESC, run_id DESC LIMIT ?""",
                [limit],
            )
        )
    except duckdb.CatalogException:
        return []


def load_watch_reports(
    connection: duckdb.DuckDBPyConnection, *, limit: int = 100
) -> list[dict[str, Any]]:
    try:
        rows = _rows(
            connection.execute(
                f"""SELECT r.*, e.event_uid, e.sequence, e.method AS event_method,
                           e.status AS event_status
                    FROM {ALERT_SCHEMA}.match_reports AS r
                    LEFT JOIN {ALERT_SCHEMA}.event_intents AS e
                      ON e.report_id = r.report_id
                    ORDER BY r.created_at DESC, r.report_id DESC LIMIT ?""",
                [limit],
            )
        )
    except duckdb.CatalogException:
        return []
    return [_decode_report(row) for row in rows]


def load_watch_report(
    connection: duckdb.DuckDBPyConnection, report_id: str
) -> dict[str, Any] | None:
    try:
        rows = _rows(
            connection.execute(
                f"""SELECT r.*, e.event_uid, e.sequence, e.method AS event_method,
                           e.status AS event_status
                    FROM {ALERT_SCHEMA}.match_reports AS r
                    LEFT JOIN {ALERT_SCHEMA}.event_intents AS e
                      ON e.report_id = r.report_id
                    WHERE r.report_id = ? LIMIT 2""",
                [report_id],
            )
        )
    except duckdb.CatalogException:
        return None
    if len(rows) != 1:
        return None
    return _decode_report(rows[0])


def _decode_report(row: dict[str, Any]) -> dict[str, Any]:
    for source, target in (
        ("clusters_json", "clusters"),
        ("weather_json", "weather"),
        ("caveats_json", "caveats"),
        ("emphasis_ids_json", "emphasis_ids"),
    ):
        row[target] = json.loads(str(row.pop(source)))
    for private in ("watch_id", "activation_generation", "fact_hash", "model", "resolved_at"):
        row.pop(private, None)
    return row


def cleanup_alert_history(
    connection: duckdb.DuckDBPyConnection, *, now: datetime | None = None
) -> dict[str, int]:
    cutoff = _iso((now or datetime.now(UTC)).astimezone(UTC) - RETENTION)
    report_count_row = connection.execute(
        f"""SELECT count(*) FROM {ALERT_SCHEMA}.match_reports
            WHERE resolved_at IS NOT NULL AND resolved_at < ?
              AND report_id NOT IN (
                SELECT report_id FROM {ALERT_SCHEMA}.event_intents WHERE report_id IS NOT NULL
                UNION
                SELECT source_report_id FROM {ALERT_SCHEMA}.event_intents
                WHERE source_report_id IS NOT NULL
              )""",
        [cutoff],
    ).fetchone()
    report_count = int(report_count_row[0]) if report_count_row else 0
    connection.execute(
        f"""DELETE FROM {ALERT_SCHEMA}.model_traces WHERE report_id IN (
            SELECT report_id FROM {ALERT_SCHEMA}.match_reports
            WHERE resolved_at IS NOT NULL AND resolved_at < ?
              AND report_id NOT IN (
                SELECT report_id FROM {ALERT_SCHEMA}.event_intents WHERE report_id IS NOT NULL
                UNION
                SELECT source_report_id FROM {ALERT_SCHEMA}.event_intents
                WHERE source_report_id IS NOT NULL
              ))""",
        [cutoff],
    )
    connection.execute(
        f"""DELETE FROM {ALERT_SCHEMA}.match_reports
            WHERE resolved_at IS NOT NULL AND resolved_at < ?
              AND report_id NOT IN (
                SELECT report_id FROM {ALERT_SCHEMA}.event_intents WHERE report_id IS NOT NULL
                UNION
                SELECT source_report_id FROM {ALERT_SCHEMA}.event_intents
                WHERE source_report_id IS NOT NULL
              )""",
        [cutoff],
    )
    run_count_row = connection.execute(
        f"""SELECT count(*) FROM {ALERT_SCHEMA}.evaluation_runs
            WHERE status IN ('completed','failed') AND completed_at < ?""",
        [cutoff],
    ).fetchone()
    run_count = int(run_count_row[0]) if run_count_row else 0
    connection.execute(
        f"""DELETE FROM {ALERT_SCHEMA}.watch_evaluation_results
            WHERE run_id IN (SELECT run_id FROM {ALERT_SCHEMA}.evaluation_runs
                             WHERE status IN ('completed','failed') AND completed_at < ?)""",
        [cutoff],
    )
    connection.execute(
        f"""DELETE FROM {ALERT_SCHEMA}.evaluation_runs
            WHERE status IN ('completed','failed') AND completed_at < ?""",
        [cutoff],
    )
    connection.execute(
        f"""DELETE FROM {ALERT_SCHEMA}.cancellation_resolutions
            WHERE resolved_at < ?""",
        [cutoff],
    )
    connection.execute(
        f"""UPDATE {ALERT_SCHEMA}.event_intents
            SET report_id=NULL, source_report_id=NULL, morning_start=NULL,
                morning_end=NULL, event_horizon_end=NULL, location_id=NULL,
                location_name=NULL, latitude=NULL, longitude=NULL
            WHERE status IN ('suppressed','cancelled','expired') AND updated_at < ?""",
        [cutoff],
    )
    return {"reports_deleted": int(report_count), "runs_deleted": int(run_count)}
