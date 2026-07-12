"""Transactional local storage for the single-user bird collection."""

from __future__ import annotations

import math
import re
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from typing import Any, Literal
from uuid import uuid4

import duckdb

from databox.agent_tools.arizona_boundary import is_in_arizona

SCHEMA = "birding_personal"


class CollectionStorageMigrationError(RuntimeError):
    """Legacy runtime storage cannot be migrated without losing identity."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _timestamp_successor(previous: str) -> str:
    """Return UTC now, or one microsecond after the prior persisted value."""

    candidate = _utc_timestamp(_now())
    prior = _utc_timestamp(previous)
    if candidate <= prior:
        candidate = prior + timedelta(microseconds=1)
    return candidate.isoformat()


def _column_exists(connection: duckdb.DuckDBPyConnection, table: str, column: str) -> bool:
    return bool(
        connection.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = ? AND table_name = ? AND column_name = ?
            """,
            [SCHEMA, table, column],
        ).fetchone()
    )


def _column_nullable(connection: duckdb.DuckDBPyConnection, table: str, column: str) -> bool:
    row = connection.execute(
        """
        SELECT is_nullable FROM information_schema.columns
        WHERE table_schema = ? AND table_name = ? AND column_name = ?
        """,
        [SCHEMA, table, column],
    ).fetchone()
    return row is not None and row[0] == "YES"


def _add_opaque_column(connection: duckdb.DuckDBPyConnection, table: str, column: str) -> None:
    if not _column_exists(connection, table, column):
        connection.execute(f"ALTER TABLE {SCHEMA}.{table} ADD COLUMN {column} VARCHAR")


def _cancellation_request_id(watch_id: str, activation_generation: str, reason: str) -> str:
    return sha256(
        f"watch-cancellation|{watch_id}|{activation_generation}|{reason}".encode()
    ).hexdigest()


def _legacy_identity(kind: str, immutable_request_id: str) -> str:
    return sha256(
        f"watch-cancellation-migration|{kind}|{immutable_request_id}".encode()
    ).hexdigest()


def _apply_legacy_request_mapping(
    connection: duckdb.DuckDBPyConnection,
    *,
    temporary_id: str,
    target_id: str,
    species_code: str,
    watch_id: str,
    activation_generation: str,
    reason: str,
) -> None:
    """Move one temporary legacy row to its final semantic identity."""

    existing = connection.execute(
        f"""SELECT species_code, watch_id, activation_generation, reason
            FROM {SCHEMA}.watch_cancellation_requests
            WHERE cancellation_request_id = ?""",
        [target_id],
    ).fetchone()
    expected = (species_code, watch_id, activation_generation, reason)
    if existing is not None:
        if tuple(str(value) for value in existing) != expected:
            raise CollectionStorageMigrationError(
                "Legacy cancellation identity conflicts with another request"
            )
        connection.execute(
            f"""DELETE FROM {SCHEMA}.watch_cancellation_requests
                WHERE cancellation_request_id = ?""",
            [temporary_id],
        )
        return
    connection.execute(
        f"""UPDATE {SCHEMA}.watch_cancellation_requests
            SET cancellation_request_id = ?, watch_id = ?, activation_generation = ?
            WHERE cancellation_request_id = ?""",
        [target_id, watch_id, activation_generation, temporary_id],
    )


def backfill_runtime_identities(connection: duckdb.DuckDBPyConnection) -> None:
    """Backfill legacy identities without collapsing historical activations."""

    watch_rows = connection.execute(
        f"""SELECT species_code, activated_at, created_at, watch_id, activation_generation
            FROM {SCHEMA}.watches
            WHERE watch_id IS NULL OR activation_generation IS NULL
            ORDER BY species_code"""
    ).fetchall()
    for species_code, activated_at, created_at, watch_id, generation in watch_rows:
        current_watch_id = (
            str(watch_id)
            if watch_id is not None
            else sha256(f"legacy-watch|{species_code}|{created_at}".encode()).hexdigest()
        )
        current_generation = (
            str(generation)
            if generation is not None
            else sha256(
                f"legacy-watch-activation|{species_code}|{activated_at}|{created_at}".encode()
            ).hexdigest()
        )
        connection.execute(
            f"""UPDATE {SCHEMA}.watches
                SET watch_id = ?, activation_generation = ?
                WHERE species_code = ?""",
            [current_watch_id, current_generation, species_code],
        )

    legacy_rows = connection.execute(
        f"""SELECT cancellation_request_id, species_code, reason, requested_at
            FROM {SCHEMA}.watch_cancellation_requests
            WHERE watch_id IS NULL OR activation_generation IS NULL
            ORDER BY species_code, requested_at, cancellation_request_id"""
    ).fetchall()
    newest_by_species: dict[str, str] = {}
    for request_id, species_code, _reason, _requested_at in legacy_rows:
        newest_by_species[str(species_code)] = str(request_id)

    mappings: list[tuple[str, str, str, str, str, str]] = []
    for request_id_value, species_code_value, reason_value, _requested_at in legacy_rows:
        immutable_id = str(request_id_value)
        species_code = str(species_code_value)
        reason = str(reason_value)
        current = connection.execute(
            f"""SELECT watch_id, activation_generation FROM {SCHEMA}.watches
                WHERE species_code = ?""",
            [species_code],
        ).fetchone()
        if current is not None and newest_by_species[species_code] == immutable_id:
            watch_id, generation = (str(current[0]), str(current[1]))
        else:
            watch_id = _legacy_identity("watch", immutable_id)
            generation = _legacy_identity("activation", immutable_id)
        target_id = _cancellation_request_id(watch_id, generation, reason)
        temporary_id = _legacy_identity("temporary", immutable_id)
        if (
            temporary_id != immutable_id
            and connection.execute(
                f"""SELECT 1 FROM {SCHEMA}.watch_cancellation_requests
                WHERE cancellation_request_id = ?""",
                [temporary_id],
            ).fetchone()
        ):
            raise CollectionStorageMigrationError(
                "Legacy cancellation temporary identity conflicts"
            )
        connection.execute(
            f"""UPDATE {SCHEMA}.watch_cancellation_requests
                SET cancellation_request_id = ?
                WHERE cancellation_request_id = ?""",
            [temporary_id, immutable_id],
        )
        mappings.append(
            (
                temporary_id,
                target_id,
                species_code,
                watch_id,
                generation,
                reason,
            )
        )

    for temporary_id, target_id, species_code, watch_id, generation, reason in mappings:
        _apply_legacy_request_mapping(
            connection,
            temporary_id=temporary_id,
            target_id=target_id,
            species_code=species_code,
            watch_id=watch_id,
            activation_generation=generation,
            reason=reason,
        )


def enforce_runtime_identity_constraints(connection: duckdb.DuckDBPyConnection) -> None:
    """Finish legacy migration after its backfill transaction commits."""

    for table in ("watches", "watch_cancellation_requests"):
        for column in ("watch_id", "activation_generation"):
            if _column_nullable(connection, table, column):
                connection.execute(
                    f"""ALTER TABLE {SCHEMA}.{table}
                        ALTER COLUMN {column} SET NOT NULL"""
                )


def runtime_identity_migration_required(connection: duckdb.DuckDBPyConnection) -> bool:
    """Return whether legacy watch tables need opaque identity columns."""

    tables = ("watches", "watch_cancellation_requests")
    columns = ("watch_id", "activation_generation")
    for table in tables:
        if not _table_exists(connection, table):
            continue
        for column in columns:
            if not _column_exists(connection, table, column):
                return True
            if _column_nullable(connection, table, column):
                return True
            if connection.execute(
                f"SELECT 1 FROM {SCHEMA}.{table} WHERE {column} IS NULL LIMIT 1"
            ).fetchone():
                return True
    return False


def observation_location_migration_required(
    connection: duckdb.DuckDBPyConnection,
) -> bool:
    """Return whether the private observation table needs additive place columns."""

    if not _table_exists(connection, "observations"):
        return False
    return any(
        not _column_exists(connection, "observations", column)
        for column in (
            "location_source",
            "location_source_id",
            "location_latitude",
            "location_longitude",
            "location_timezone",
            "location_region_code",
        )
    )


def _add_observation_location_columns(connection: duckdb.DuckDBPyConnection) -> None:
    for column, data_type in (
        ("location_source", "VARCHAR"),
        ("location_source_id", "VARCHAR"),
        ("location_latitude", "DOUBLE"),
        ("location_longitude", "DOUBLE"),
        ("location_timezone", "VARCHAR"),
        ("location_region_code", "VARCHAR"),
    ):
        connection.execute(
            f"ALTER TABLE {SCHEMA}.observations ADD COLUMN IF NOT EXISTS {column} {data_type}"
        )


def ensure_tables(connection: duckdb.DuckDBPyConnection) -> None:
    """Create or migrate runtime-owned personal tables in the caller transaction."""

    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.observations (
            observation_id VARCHAR PRIMARY KEY,
            species_code VARCHAR NOT NULL,
            observation_date DATE NOT NULL,
            location_text VARCHAR,
            notes VARCHAR,
            created_at VARCHAR NOT NULL,
            updated_at VARCHAR NOT NULL,
            location_source VARCHAR,
            location_source_id VARCHAR,
            location_latitude DOUBLE,
            location_longitude DOUBLE,
            location_timezone VARCHAR,
            location_region_code VARCHAR,
            CHECK (length(species_code) BETWEEN 1 AND 64),
            CHECK (location_text IS NULL OR length(location_text) BETWEEN 1 AND 300),
            CHECK (notes IS NULL OR length(notes) BETWEEN 1 AND 2000),
            CHECK (location_source IS NULL OR location_source IN ('ebird_hotspot', 'open_meteo')),
            CHECK (location_source_id IS NULL OR length(location_source_id) BETWEEN 1 AND 64),
            CHECK (location_timezone IS NULL OR location_timezone = 'America/Phoenix'),
            CHECK (location_region_code IS NULL OR location_region_code = 'US-AZ'),
            CHECK (
                (location_source IS NULL AND location_source_id IS NULL
                 AND location_latitude IS NULL AND location_longitude IS NULL
                 AND location_timezone IS NULL AND location_region_code IS NULL)
                OR
                (location_text IS NOT NULL AND location_source IS NOT NULL
                 AND location_source_id IS NOT NULL AND location_latitude IS NOT NULL
                 AND location_longitude IS NOT NULL AND location_timezone IS NOT NULL
                 AND location_region_code IS NOT NULL)
            )
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.watches (
            species_code VARCHAR PRIMARY KEY,
            watch_id VARCHAR NOT NULL,
            activation_generation VARCHAR NOT NULL,
            active BOOLEAN NOT NULL,
            center_name VARCHAR NOT NULL,
            center_latitude DOUBLE NOT NULL,
            center_longitude DOUBLE NOT NULL,
            center_timezone VARCHAR NOT NULL,
            radius_miles DOUBLE NOT NULL,
            activated_at VARCHAR NOT NULL,
            created_at VARCHAR NOT NULL,
            updated_at VARCHAR NOT NULL,
            CHECK (length(species_code) BETWEEN 1 AND 64),
            CHECK (length(center_name) BETWEEN 1 AND 300),
            CHECK (center_latitude BETWEEN 31.0 AND 37.1),
            CHECK (center_longitude BETWEEN -115.0 AND -109.0),
            CHECK (radius_miles BETWEEN 1 AND 300)
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.watch_cancellation_requests (
            cancellation_request_id VARCHAR PRIMARY KEY,
            species_code VARCHAR NOT NULL,
            watch_id VARCHAR NOT NULL,
            activation_generation VARCHAR NOT NULL,
            reason VARCHAR NOT NULL,
            requested_at VARCHAR NOT NULL,
            CHECK (length(species_code) BETWEEN 1 AND 64),
            CHECK (reason IN ('pause', 'delete'))
        )
        """
    )
    _add_observation_location_columns(connection)
    connection.execute(
        f"""CREATE INDEX IF NOT EXISTS observations_species_idx
        ON {SCHEMA}.observations(species_code)"""
    )
    connection.execute(
        f"""CREATE INDEX IF NOT EXISTS observations_date_idx
        ON {SCHEMA}.observations(observation_date)"""
    )
    _add_opaque_column(connection, "watches", "watch_id")
    _add_opaque_column(connection, "watches", "activation_generation")
    _add_opaque_column(connection, "watch_cancellation_requests", "watch_id")
    _add_opaque_column(connection, "watch_cancellation_requests", "activation_generation")


def _table_exists(connection: duckdb.DuckDBPyConnection, table: str) -> bool:
    return bool(
        connection.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = ? AND table_name = ?
            """,
            [SCHEMA, table],
        ).fetchone()
    )


def catalog_species(
    connection: duckdb.DuckDBPyConnection, species_code: str
) -> dict[str, Any] | None:
    cursor = connection.execute(
        """
        SELECT species_code, common_name, scientific_name, taxonomic_category
        FROM birding_agent.arizona_species_catalog
        WHERE species_code = ?
        LIMIT 2
        """,
        [species_code],
    )
    rows = cursor.fetchall()
    if len(rows) != 1:
        return None
    return dict(zip([item[0] for item in cursor.description], rows[0], strict=True))


def _identity_columns(alias: str = "c") -> str:
    return (
        f"{alias}.species_code AS catalog_species_code, {alias}.common_name, "
        f"{alias}.scientific_name, {alias}.taxonomic_category"
    )


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    current = row.pop("catalog_species_code", None) is not None
    return {
        "catalog_status": "current" if current else "stale",
        "common_name": row.pop("common_name", None),
        "scientific_name": row.pop("scientific_name", None),
        "taxonomic_category": row.pop("taxonomic_category", None),
    }


def _rows(cursor: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    keys = [item[0] for item in cursor.description]
    return [dict(zip(keys, values, strict=True)) for values in cursor.fetchall()]


def list_observations(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    if not _table_exists(connection, "observations"):
        return []
    rows = _rows(
        connection.execute(
            f"""
            SELECT o.*, {_identity_columns()}
            FROM {SCHEMA}.observations AS o
            LEFT JOIN birding_agent.arizona_species_catalog AS c USING (species_code)
            ORDER BY o.observation_date DESC, o.updated_at DESC, o.observation_id
            """
        )
    )
    for row in rows:
        row["identity"] = _identity(row)
    return rows


def get_observation(
    connection: duckdb.DuckDBPyConnection, observation_id: str
) -> dict[str, Any] | None:
    if not _table_exists(connection, "observations"):
        return None
    rows = _rows(
        connection.execute(
            f"""
            SELECT o.*, {_identity_columns()}
            FROM {SCHEMA}.observations AS o
            LEFT JOIN birding_agent.arizona_species_catalog AS c USING (species_code)
            WHERE o.observation_id = ?
            """,
            [observation_id],
        )
    )
    if len(rows) != 1:
        return None
    rows[0]["identity"] = _identity(rows[0])
    return rows[0]


def _validate_observation_location(
    *,
    location_text: str | None,
    location_source: str | None,
    location_source_id: str | None,
    location_latitude: float | None,
    location_longitude: float | None,
    location_timezone: str | None,
    location_region_code: str | None,
) -> None:
    structured = (
        location_source,
        location_source_id,
        location_latitude,
        location_longitude,
        location_timezone,
        location_region_code,
    )
    if all(value is None for value in structured):
        return
    if any(value is None for value in structured) or location_text is None:
        raise ValueError("structured observation location must be all-or-none")
    if location_source not in ("ebird_hotspot", "open_meteo"):
        raise ValueError("invalid observation location source")
    if (
        not isinstance(location_source_id, str)
        or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", location_source_id) is None
        or (location_source == "open_meteo" and not location_source_id.startswith("open_meteo_"))
    ):
        raise ValueError("invalid observation location identity")
    if (
        isinstance(location_latitude, bool)
        or not isinstance(location_latitude, int | float)
        or not math.isfinite(location_latitude)
        or isinstance(location_longitude, bool)
        or not isinstance(location_longitude, int | float)
        or not math.isfinite(location_longitude)
        or not is_in_arizona(float(location_latitude), float(location_longitude))
    ):
        raise ValueError("invalid observation location coordinates")
    if location_timezone != "America/Phoenix" or location_region_code != "US-AZ":
        raise ValueError("invalid observation location region")


def create_observation(
    connection: duckdb.DuckDBPyConnection,
    *,
    species_code: str,
    observation_date: date,
    location_text: str | None,
    notes: str | None,
    location_source: str | None = None,
    location_source_id: str | None = None,
    location_latitude: float | None = None,
    location_longitude: float | None = None,
    location_timezone: str | None = None,
    location_region_code: str | None = None,
) -> dict[str, Any]:
    _validate_observation_location(
        location_text=location_text,
        location_source=location_source,
        location_source_id=location_source_id,
        location_latitude=location_latitude,
        location_longitude=location_longitude,
        location_timezone=location_timezone,
        location_region_code=location_region_code,
    )
    if catalog_species(connection, species_code) is None:
        raise LookupError("species")
    timestamp = _now()
    observation_id = str(uuid4())
    connection.execute(
        f"""
        INSERT INTO {SCHEMA}.observations (
            observation_id, species_code, observation_date, location_text, notes,
            created_at, updated_at, location_source, location_source_id,
            location_latitude, location_longitude, location_timezone, location_region_code
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            observation_id,
            species_code,
            observation_date,
            location_text,
            notes,
            timestamp,
            timestamp,
            location_source,
            location_source_id,
            location_latitude,
            location_longitude,
            location_timezone,
            location_region_code,
        ],
    )
    result = get_observation(connection, observation_id)
    assert result is not None
    return result


def update_observation(
    connection: duckdb.DuckDBPyConnection,
    observation_id: str,
    *,
    species_code: str,
    observation_date: date,
    location_text: str | None,
    notes: str | None,
    location_source: str | None = None,
    location_source_id: str | None = None,
    location_latitude: float | None = None,
    location_longitude: float | None = None,
    location_timezone: str | None = None,
    location_region_code: str | None = None,
) -> dict[str, Any]:
    _validate_observation_location(
        location_text=location_text,
        location_source=location_source,
        location_source_id=location_source_id,
        location_latitude=location_latitude,
        location_longitude=location_longitude,
        location_timezone=location_timezone,
        location_region_code=location_region_code,
    )
    if catalog_species(connection, species_code) is None:
        raise LookupError("species")
    existing = get_observation(connection, observation_id)
    if existing is None:
        raise LookupError("observation")
    connection.execute(
        f"""
        UPDATE {SCHEMA}.observations
        SET species_code = ?, observation_date = ?, location_text = ?, notes = ?,
            updated_at = ?, location_source = ?, location_source_id = ?,
            location_latitude = ?, location_longitude = ?, location_timezone = ?,
            location_region_code = ?
        WHERE observation_id = ?
        """,
        [
            species_code,
            observation_date,
            location_text,
            notes,
            _timestamp_successor(str(existing["updated_at"])),
            location_source,
            location_source_id,
            location_latitude,
            location_longitude,
            location_timezone,
            location_region_code,
            observation_id,
        ],
    )
    result = get_observation(connection, observation_id)
    assert result is not None
    return result


def delete_observation(connection: duckdb.DuckDBPyConnection, observation_id: str) -> bool:
    if not _table_exists(connection, "observations"):
        return False
    exists = connection.execute(
        f"SELECT 1 FROM {SCHEMA}.observations WHERE observation_id = ?", [observation_id]
    ).fetchone()
    if not exists:
        return False
    connection.execute(
        f"DELETE FROM {SCHEMA}.observations WHERE observation_id = ?", [observation_id]
    )
    return True


def list_life_list(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    if not _table_exists(connection, "observations"):
        return []
    rows = _rows(
        connection.execute(
            f"""
            SELECT o.species_code, MIN(o.observation_date) AS first_observed_date,
                   MAX(o.observation_date) AS latest_observed_date,
                   COUNT(*)::BIGINT AS observation_count, {_identity_columns()}
            FROM {SCHEMA}.observations AS o
            LEFT JOIN birding_agent.arizona_species_catalog AS c USING (species_code)
            GROUP BY o.species_code, c.species_code, c.common_name,
                     c.scientific_name, c.taxonomic_category
            ORDER BY first_observed_date, o.species_code
            """
        )
    )
    for row in rows:
        row["identity"] = _identity(row)
    return rows


def list_watches(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    if not _table_exists(connection, "watches"):
        return []
    rows = _rows(
        connection.execute(
            f"""
            SELECT w.species_code, w.active, w.center_name, w.center_latitude,
                   w.center_longitude, w.center_timezone, w.radius_miles,
                   w.activated_at, w.created_at, w.updated_at, {_identity_columns()}
            FROM {SCHEMA}.watches AS w
            LEFT JOIN birding_agent.arizona_species_catalog AS c USING (species_code)
            ORDER BY w.created_at, w.species_code
            """
        )
    )
    for row in rows:
        row["identity"] = _identity(row)
    return rows


def put_watch(
    connection: duckdb.DuckDBPyConnection,
    *,
    species_code: str,
    center_name: str,
    center_latitude: float,
    center_longitude: float,
    center_timezone: str,
    radius_miles: float,
) -> dict[str, Any]:
    if catalog_species(connection, species_code) is None:
        raise LookupError("species")
    existing = None
    if _table_exists(connection, "watches"):
        existing = connection.execute(
            f"""SELECT watch_id, activation_generation, active, center_name,
                       center_latitude, center_longitude, center_timezone,
                       radius_miles, activated_at, created_at, updated_at
                FROM {SCHEMA}.watches WHERE species_code = ?""",
            [species_code],
        ).fetchone()
    active = bool(existing[2]) if existing else True
    unchanged = bool(
        existing
        and str(existing[3]) == center_name
        and float(existing[4]) == center_latitude
        and float(existing[5]) == center_longitude
        and str(existing[6]) == center_timezone
        and float(existing[7]) == radius_miles
    )
    if unchanged:
        return next(row for row in list_watches(connection) if row["species_code"] == species_code)
    if existing:
        timestamp = _timestamp_successor(str(existing[10]))
        watch_id = str(existing[0])
        activation_generation = str(existing[1]) if not active else str(uuid4())
        activated_at = timestamp if active else str(existing[8])
        created_at = str(existing[9])
    else:
        timestamp = _utc_timestamp(_now()).isoformat()
        watch_id = str(uuid4())
        activation_generation = str(uuid4())
        activated_at = timestamp
        created_at = timestamp
    connection.execute(
        f"""
        INSERT OR REPLACE INTO {SCHEMA}.watches (
            species_code, watch_id, activation_generation, active, center_name,
            center_latitude, center_longitude, center_timezone, radius_miles,
            activated_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            species_code,
            watch_id,
            activation_generation,
            active,
            center_name,
            center_latitude,
            center_longitude,
            center_timezone,
            radius_miles,
            activated_at,
            created_at,
            timestamp,
        ],
    )
    return next(row for row in list_watches(connection) if row["species_code"] == species_code)


def watch_runtime_identity(
    connection: duckdb.DuckDBPyConnection, species_code: str
) -> tuple[str, str] | None:
    """Return opaque internal watch and activation identities."""

    if not _table_exists(connection, "watches"):
        return None
    row = connection.execute(
        f"""SELECT watch_id, activation_generation FROM {SCHEMA}.watches
            WHERE species_code = ?""",
        [species_code],
    ).fetchone()
    return (str(row[0]), str(row[1])) if row is not None else None


def set_watch_active(
    connection: duckdb.DuckDBPyConnection, species_code: str, *, active: bool
) -> dict[str, Any]:
    if not _table_exists(connection, "watches"):
        raise LookupError("watch")
    existing = connection.execute(
        f"""SELECT active, updated_at FROM {SCHEMA}.watches
            WHERE species_code = ?""",
        [species_code],
    ).fetchone()
    if existing is None:
        raise LookupError("watch")
    if active and catalog_species(connection, species_code) is None:
        raise LookupError("species")
    if bool(existing[0]) != active:
        timestamp = _timestamp_successor(str(existing[1]))
        if active:
            connection.execute(
                f"""UPDATE {SCHEMA}.watches
                SET active = TRUE, activation_generation = ?, activated_at = ?, updated_at = ?
                WHERE species_code = ?""",
                [str(uuid4()), timestamp, timestamp, species_code],
            )
        else:
            connection.execute(
                f"""UPDATE {SCHEMA}.watches
                SET active = FALSE, updated_at = ? WHERE species_code = ?""",
                [timestamp, species_code],
            )
    return next(row for row in list_watches(connection) if row["species_code"] == species_code)


def request_watch_cancellation(
    connection: duckdb.DuckDBPyConnection,
    species_code: str,
    *,
    reason: Literal["pause", "delete"],
    watch_id: str,
    activation_generation: str,
) -> None:
    """Persist a side-effect-free cancellation handoff for downstream evaluation."""

    request_id = _cancellation_request_id(watch_id, activation_generation, reason)
    connection.execute(
        f"""INSERT OR IGNORE INTO {SCHEMA}.watch_cancellation_requests (
            cancellation_request_id, species_code, watch_id,
            activation_generation, reason, requested_at
        ) VALUES (?, ?, ?, ?, ?, ?)""",
        [request_id, species_code, watch_id, activation_generation, reason, _now()],
    )


def list_watch_cancellation_requests(
    connection: duckdb.DuckDBPyConnection,
) -> list[dict[str, Any]]:
    """Return bounded non-private handoffs for the evaluator/calendar child."""

    if not _table_exists(connection, "watch_cancellation_requests"):
        return []
    return _rows(
        connection.execute(
            f"""SELECT cancellation_request_id, species_code, reason, requested_at
                FROM {SCHEMA}.watch_cancellation_requests
                ORDER BY requested_at, cancellation_request_id"""
        )
    )


def consume_watch_cancellation_request(
    connection: duckdb.DuckDBPyConnection, cancellation_request_id: str
) -> bool:
    """Remove one handoff after downstream conditionally resolves it."""

    if not _table_exists(connection, "watch_cancellation_requests"):
        return False
    exists = connection.execute(
        f"""SELECT 1 FROM {SCHEMA}.watch_cancellation_requests
            WHERE cancellation_request_id = ?""",
        [cancellation_request_id],
    ).fetchone()
    if not exists:
        return False
    connection.execute(
        f"""DELETE FROM {SCHEMA}.watch_cancellation_requests
            WHERE cancellation_request_id = ?""",
        [cancellation_request_id],
    )
    return True


def delete_watch(connection: duckdb.DuckDBPyConnection, species_code: str) -> bool:
    if not _table_exists(connection, "watches"):
        return False
    existing = connection.execute(
        f"SELECT 1 FROM {SCHEMA}.watches WHERE species_code = ?", [species_code]
    ).fetchone()
    if existing is None:
        return False
    connection.execute(f"DELETE FROM {SCHEMA}.watches WHERE species_code = ?", [species_code])
    return True


def collection_state(connection: duckdb.DuckDBPyConnection, species_code: str) -> dict[str, Any]:
    current = catalog_species(connection, species_code) is not None
    observed_count = 0
    if _table_exists(connection, "observations"):
        count_row = connection.execute(
            f"SELECT COUNT(*) FROM {SCHEMA}.observations WHERE species_code = ?",
            [species_code],
        ).fetchone()
        assert count_row is not None
        observed_count = int(count_row[0])
    watched = False
    watch_active = False
    if _table_exists(connection, "watches"):
        watch = connection.execute(
            f"SELECT active FROM {SCHEMA}.watches WHERE species_code = ?", [species_code]
        ).fetchone()
        watched = watch is not None
        watch_active = bool(watch[0]) if watch is not None else False
    return {
        "species_code": species_code,
        "catalog_status": "current" if current else "stale",
        "observed": observed_count > 0,
        "observation_count": observed_count,
        "watched": watched,
        "watch_active": watch_active,
    }
