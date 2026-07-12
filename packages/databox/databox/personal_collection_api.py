"""Typed FastAPI routes for local personal bird collection state."""

from __future__ import annotations

import asyncio
import re
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import duckdb
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from databox.agent_tools.arizona_boundary import is_in_arizona
from databox.agents.birding_trip_planner import NormalizedLocation, resolve_arizona_location
from databox.personal_collection import (
    CollectionStorageMigrationError,
    backfill_runtime_identities,
    collection_state,
    create_observation,
    delete_observation,
    delete_watch,
    enforce_runtime_identity_constraints,
    ensure_tables,
    get_observation,
    list_life_list,
    list_observations,
    list_watches,
    observation_location_migration_required,
    put_watch,
    request_watch_cancellation,
    runtime_identity_migration_required,
    set_watch_active,
    update_observation,
    watch_runtime_identity,
)


class CollectionErrorBody(BaseModel):
    code: str
    message: str


class CollectionErrorResponse(BaseModel):
    error: CollectionErrorBody


class BirdIdentityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_status: Literal["current", "stale"]
    common_name: str | None
    scientific_name: str | None
    taxonomic_category: str | None


class ObservationLocationSelectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    display_name: str = Field(strict=True, min_length=1, max_length=300)
    latitude: float = Field(strict=True)
    longitude: float = Field(strict=True)
    timezone: Literal["America/Phoenix"]
    region_code: Literal["US-AZ"]
    source: Literal["ebird_hotspot", "open_meteo"]
    source_id: str = Field(strict=True, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    place_type: Literal["Birding hotspot", "Arizona place"]

    @field_validator("display_name")
    @classmethod
    def trim_display_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped or re.search(r"[\x00-\x1f\x7f]", stripped) is not None:
            raise ValueError("invalid location display name")
        return stripped

    @model_validator(mode="after")
    def validate_relationships(self) -> ObservationLocationSelectionInput:
        expected_type = "Birding hotspot" if self.source == "ebird_hotspot" else "Arizona place"
        if self.place_type != expected_type:
            raise ValueError("location source and type do not match")
        if self.source == "open_meteo" and not self.source_id.startswith("open_meteo_"):
            raise ValueError("location source and identity do not match")
        if not is_in_arizona(self.latitude, self.longitude):
            raise ValueError("location is outside Arizona")
        return self


class ObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    species_code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9]+$")
    observation_date: date
    location: str | None = Field(default=None, max_length=300)
    location_selection: ObservationLocationSelectionInput | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("location", "notes")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def selection_matches_location(self) -> ObservationInput:
        if (
            self.location_selection is not None
            and self.location != self.location_selection.display_name
        ):
            raise ValueError("location must match the selected display name")
        return self


class ObservationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    species_code: str
    observation_date: date
    location: str | None
    location_source: Literal["ebird_hotspot", "open_meteo"] | None
    location_source_id: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )
    location_latitude: float | None = Field(default=None, allow_inf_nan=False)
    location_longitude: float | None = Field(default=None, allow_inf_nan=False)
    location_timezone: Literal["America/Phoenix"] | None
    location_region_code: Literal["US-AZ"] | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    identity: BirdIdentityResponse

    @model_validator(mode="after")
    def structured_location_is_coherent(self) -> ObservationResponse:
        values = (
            self.location_source,
            self.location_source_id,
            self.location_latitude,
            self.location_longitude,
            self.location_timezone,
            self.location_region_code,
        )
        if all(value is None for value in values):
            return self
        if any(value is None for value in values) or self.location is None:
            raise ValueError("structured location must be all-or-none")
        assert self.location_latitude is not None and self.location_longitude is not None
        if not is_in_arizona(self.location_latitude, self.location_longitude):
            raise ValueError("structured location is outside Arizona")
        if self.location_source == "open_meteo" and not str(self.location_source_id).startswith(
            "open_meteo_"
        ):
            raise ValueError("structured location source is inconsistent")
        return self


class ObservationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[ObservationResponse] = Field(max_length=10000)


class LifeListEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    species_code: str
    first_observed_date: date
    latest_observed_date: date
    observation_count: int = Field(ge=1)
    identity: BirdIdentityResponse


class LifeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    birds: list[LifeListEntryResponse] = Field(max_length=10000)


class WatchCenterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = Field(min_length=1, max_length=64)
    region_code: Literal["US-AZ"]

    @field_validator("display_name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("display_name is required")
        return stripped


class WatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    center: WatchCenterInput
    radius_miles: float = Field(ge=1, le=300, allow_inf_nan=False)


class WatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    species_code: str
    active: bool
    center_name: str
    center_latitude: float
    center_longitude: float
    center_timezone: str
    radius_miles: float
    activated_at: datetime
    created_at: datetime
    updated_at: datetime
    identity: BirdIdentityResponse


class WatchListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    watches: list[WatchResponse] = Field(max_length=10000)


class CollectionStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    species_code: str
    catalog_status: Literal["current", "stale"]
    observed: bool
    observation_count: int = Field(ge=0)
    watched: bool
    watch_active: bool


class RemovedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    removed: bool


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=CollectionErrorResponse(
            error=CollectionErrorBody(code=code, message=message)
        ).model_dump(),
    )


def _busy(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ("lock", "busy", "conflicting", "could not set lock"))


def _begin_collection_transaction(connection: duckdb.DuckDBPyConnection) -> None:
    """Commit legacy DDL migration before the mutation transaction.

    DuckDB cannot alter and then mutate the same table in one transaction.
    Fresh schema creation remains coupled to its first mutation; only an
    already-existing legacy schema takes this separate atomic migration step.
    """

    if runtime_identity_migration_required(connection):
        connection.execute("BEGIN TRANSACTION")
        try:
            ensure_tables(connection)
            connection.execute("COMMIT")
        except Exception:
            try:
                connection.execute("ROLLBACK")
            except duckdb.TransactionException:
                pass
            raise
        connection.execute("BEGIN TRANSACTION")
        try:
            backfill_runtime_identities(connection)
            connection.execute("COMMIT")
        except Exception:
            try:
                connection.execute("ROLLBACK")
            except duckdb.TransactionException:
                pass
            raise
        connection.execute("BEGIN TRANSACTION")
        try:
            enforce_runtime_identity_constraints(connection)
            connection.execute("COMMIT")
        except Exception:
            try:
                connection.execute("ROLLBACK")
            except duckdb.TransactionException:
                pass
            raise
    if observation_location_migration_required(connection):
        connection.execute("BEGIN TRANSACTION")
        try:
            ensure_tables(connection)
            connection.execute("COMMIT")
        except Exception:
            try:
                connection.execute("ROLLBACK")
            except duckdb.TransactionException:
                pass
            raise
    connection.execute("BEGIN TRANSACTION")


def _observation(row: dict[str, object]) -> ObservationResponse:
    row = dict(row)
    row["location"] = row.pop("location_text")
    for field in (
        "location_source",
        "location_source_id",
        "location_latitude",
        "location_longitude",
        "location_timezone",
        "location_region_code",
    ):
        row.setdefault(field, None)
    return ObservationResponse.model_validate(row)


def _valid_identifier(value: str) -> bool:
    return len(value) <= 128 and re.fullmatch(r"[A-Za-z0-9-]+", value) is not None


def register_personal_collection_routes(
    app: FastAPI, *, database_path: str, mutation_lock: asyncio.Lock
) -> None:
    """Register collection endpoints on the local application."""

    def read_connection() -> duckdb.DuckDBPyConnection:
        return duckdb.connect(database_path, read_only=True)

    def write_connection() -> duckdb.DuckDBPyConnection:
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(database_path)

    @app.get("/api/observations", response_model=ObservationListResponse)
    async def observations() -> ObservationListResponse | JSONResponse:
        if not Path(database_path).exists():
            return ObservationListResponse(observations=[])
        connection = None
        try:
            connection = read_connection()
            return ObservationListResponse(
                observations=[_observation(row) for row in list_observations(connection)]
            )
        except duckdb.Error as exc:
            return _error(
                "database_busy" if _busy(exc) else "database_unavailable",
                "The warehouse is refreshing; try again shortly"
                if _busy(exc)
                else "The local collection is unavailable",
                503,
            )
        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/observations/{observation_id}", response_model=ObservationResponse)
    async def observation(observation_id: str) -> ObservationResponse | JSONResponse:
        if not _valid_identifier(observation_id):
            return _error("invalid_request", "Invalid observation identifier", 400)
        if not Path(database_path).exists():
            return _error("not_found", "Observation not found", 404)
        connection = None
        try:
            connection = read_connection()
            row = get_observation(connection, observation_id)
            return _observation(row) if row else _error("not_found", "Observation not found", 404)
        except duckdb.Error as exc:
            return _error(
                "database_busy" if _busy(exc) else "database_unavailable",
                "The local collection is unavailable",
                503,
            )
        finally:
            if connection is not None:
                connection.close()

    async def mutate_observation(
        payload: ObservationInput, observation_id: str | None = None
    ) -> ObservationResponse | JSONResponse:
        if mutation_lock.locked():
            return _error("collection_busy", "Another collection change is in progress", 409)
        async with mutation_lock:
            connection = None
            transaction = False
            try:
                connection = write_connection()
                _begin_collection_transaction(connection)
                transaction = True
                ensure_tables(connection)
                selected = payload.location_selection
                if observation_id is None:
                    row = create_observation(
                        connection,
                        species_code=payload.species_code,
                        observation_date=payload.observation_date,
                        location_text=payload.location,
                        notes=payload.notes,
                        location_source=selected.source if selected else None,
                        location_source_id=selected.source_id if selected else None,
                        location_latitude=selected.latitude if selected else None,
                        location_longitude=selected.longitude if selected else None,
                        location_timezone=selected.timezone if selected else None,
                        location_region_code=selected.region_code if selected else None,
                    )
                else:
                    row = update_observation(
                        connection,
                        observation_id,
                        species_code=payload.species_code,
                        observation_date=payload.observation_date,
                        location_text=payload.location,
                        notes=payload.notes,
                        location_source=selected.source if selected else None,
                        location_source_id=selected.source_id if selected else None,
                        location_latitude=selected.latitude if selected else None,
                        location_longitude=selected.longitude if selected else None,
                        location_timezone=selected.timezone if selected else None,
                        location_region_code=selected.region_code if selected else None,
                    )
                connection.execute("COMMIT")
                transaction = False
                return _observation(row)
            except LookupError as exc:
                if transaction and connection is not None:
                    connection.execute("ROLLBACK")
                return _error(
                    "species_not_found" if exc.args == ("species",) else "not_found",
                    "Bird not found in the current Arizona catalog"
                    if exc.args == ("species",)
                    else "Observation not found",
                    404,
                )
            except ValueError:
                if transaction and connection is not None:
                    connection.execute("ROLLBACK")
                return _error("invalid_request", "Check the collection inputs and try again", 422)
            except CollectionStorageMigrationError:
                if transaction and connection is not None:
                    connection.execute("ROLLBACK")
                return _error("database_unavailable", "The local collection is unavailable", 503)
            except duckdb.Error as exc:
                if transaction and connection is not None:
                    connection.execute("ROLLBACK")
                return _error(
                    "database_busy" if _busy(exc) else "database_unavailable",
                    "The local collection is unavailable",
                    503,
                )
            finally:
                if connection is not None:
                    connection.close()

    @app.post("/api/observations", status_code=201, response_model=ObservationResponse)
    async def add_observation(payload: ObservationInput) -> ObservationResponse | JSONResponse:
        return await mutate_observation(payload)

    @app.put("/api/observations/{observation_id}", response_model=ObservationResponse)
    async def edit_observation(
        observation_id: str, payload: ObservationInput
    ) -> ObservationResponse | JSONResponse:
        if not _valid_identifier(observation_id):
            return _error("invalid_request", "Invalid observation identifier", 400)
        return await mutate_observation(payload, observation_id)

    @app.delete("/api/observations/{observation_id}", response_model=RemovedResponse)
    async def remove_observation(
        observation_id: str, confirm: bool = Query(default=False)
    ) -> RemovedResponse | JSONResponse:
        if not confirm:
            return _error("confirmation_required", "Confirm permanent observation deletion", 409)
        if not _valid_identifier(observation_id):
            return _error("invalid_request", "Invalid observation identifier", 400)
        if mutation_lock.locked():
            return _error("collection_busy", "Another collection change is in progress", 409)
        async with mutation_lock:
            connection = None
            transaction = False
            try:
                connection = write_connection()
                _begin_collection_transaction(connection)
                transaction = True
                ensure_tables(connection)
                if not delete_observation(connection, observation_id):
                    connection.execute("ROLLBACK")
                    transaction = False
                    return _error("not_found", "Observation not found", 404)
                connection.execute("COMMIT")
                transaction = False
                return RemovedResponse(removed=True)
            except CollectionStorageMigrationError:
                if transaction and connection is not None:
                    connection.execute("ROLLBACK")
                return _error("database_unavailable", "The local collection is unavailable", 503)
            except duckdb.Error as exc:
                if transaction and connection is not None:
                    connection.execute("ROLLBACK")
                return _error(
                    "database_busy" if _busy(exc) else "database_unavailable",
                    "The local collection is unavailable",
                    503,
                )
            finally:
                if connection is not None:
                    connection.close()

    @app.get("/api/life-list", response_model=LifeListResponse)
    async def life_list() -> LifeListResponse | JSONResponse:
        if not Path(database_path).exists():
            return LifeListResponse(birds=[])
        connection = None
        try:
            connection = read_connection()
            return LifeListResponse(birds=list_life_list(connection))
        except duckdb.Error as exc:
            return _error(
                "database_busy" if _busy(exc) else "database_unavailable",
                "The local collection is unavailable",
                503,
            )
        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/watches", response_model=WatchListResponse)
    async def watches() -> WatchListResponse | JSONResponse:
        if not Path(database_path).exists():
            return WatchListResponse(watches=[])
        connection = None
        try:
            connection = read_connection()
            return WatchListResponse(watches=list_watches(connection))
        except duckdb.Error as exc:
            return _error(
                "database_busy" if _busy(exc) else "database_unavailable",
                "The local collection is unavailable",
                503,
            )
        finally:
            if connection is not None:
                connection.close()

    async def change_watch(
        species_code: str,
        *,
        payload: WatchInput | None = None,
        active: bool | None = None,
        delete: bool = False,
    ) -> WatchResponse | RemovedResponse | JSONResponse:
        if not re.fullmatch(r"[A-Za-z0-9]{1,64}", species_code):
            return _error("invalid_request", "Invalid bird species code", 400)
        if mutation_lock.locked():
            return _error("collection_busy", "Another collection change is in progress", 409)
        resolved = None
        if payload is not None:
            center = payload.center
            try:
                resolved = resolve_arizona_location(
                    center.display_name,
                    NormalizedLocation(
                        requested_location=center.display_name,
                        normalized_location_name=center.display_name,
                        latitude=center.latitude,
                        longitude=center.longitude,
                        region_code="US-AZ",
                        timezone=center.timezone,
                    ),
                )
            except ValueError:
                return _error("invalid_location", "Select a location inside Arizona", 400)
        async with mutation_lock:
            connection = None
            transaction = False
            try:
                connection = write_connection()
                _begin_collection_transaction(connection)
                transaction = True
                ensure_tables(connection)
                if delete:
                    existing_watch = next(
                        (
                            row
                            for row in list_watches(connection)
                            if row["species_code"] == species_code
                        ),
                        None,
                    )
                    if existing_watch is not None:
                        runtime_identity = watch_runtime_identity(connection, species_code)
                        assert runtime_identity is not None
                        request_watch_cancellation(
                            connection,
                            species_code,
                            reason="delete",
                            watch_id=runtime_identity[0],
                            activation_generation=runtime_identity[1],
                        )
                        delete_watch(connection, species_code)
                    result: dict[str, object] | None = None
                elif payload is not None and resolved is not None:
                    result = put_watch(
                        connection,
                        species_code=species_code,
                        center_name=resolved.normalized_location_name,
                        center_latitude=resolved.latitude,
                        center_longitude=resolved.longitude,
                        center_timezone=resolved.timezone,
                        radius_miles=payload.radius_miles,
                    )
                else:
                    assert active is not None
                    existing_watch = next(
                        (
                            row
                            for row in list_watches(connection)
                            if row["species_code"] == species_code
                        ),
                        None,
                    )
                    runtime_identity = watch_runtime_identity(connection, species_code)
                    result = set_watch_active(connection, species_code, active=active)
                    if active is False and existing_watch is not None and existing_watch["active"]:
                        assert runtime_identity is not None
                        request_watch_cancellation(
                            connection,
                            species_code,
                            reason="pause",
                            watch_id=runtime_identity[0],
                            activation_generation=runtime_identity[1],
                        )
                connection.execute("COMMIT")
                transaction = False
                return (
                    RemovedResponse(removed=True)
                    if delete
                    else WatchResponse.model_validate(result)
                )
            except LookupError as exc:
                if transaction and connection is not None:
                    connection.execute("ROLLBACK")
                return _error(
                    "species_not_found" if exc.args == ("species",) else "not_found",
                    "Bird not found in the current Arizona catalog"
                    if exc.args == ("species",)
                    else "Watch not found",
                    404,
                )
            except CollectionStorageMigrationError:
                if transaction and connection is not None:
                    connection.execute("ROLLBACK")
                return _error("database_unavailable", "The local collection is unavailable", 503)
            except duckdb.Error as exc:
                if transaction and connection is not None:
                    connection.execute("ROLLBACK")
                return _error(
                    "database_busy" if _busy(exc) else "database_unavailable",
                    "The local collection is unavailable",
                    503,
                )
            finally:
                if connection is not None:
                    connection.close()

    @app.put("/api/watches/{species_code}", response_model=WatchResponse)
    async def save_watch(
        species_code: str, payload: WatchInput
    ) -> WatchResponse | RemovedResponse | JSONResponse:
        return await change_watch(species_code, payload=payload)

    @app.post("/api/watches/{species_code}/pause", response_model=WatchResponse)
    async def pause_watch(species_code: str) -> WatchResponse | RemovedResponse | JSONResponse:
        return await change_watch(species_code, active=False)

    @app.post("/api/watches/{species_code}/resume", response_model=WatchResponse)
    async def resume_watch(species_code: str) -> WatchResponse | RemovedResponse | JSONResponse:
        return await change_watch(species_code, active=True)

    @app.delete("/api/watches/{species_code}", response_model=RemovedResponse)
    async def remove_watch(species_code: str) -> WatchResponse | RemovedResponse | JSONResponse:
        return await change_watch(species_code, delete=True)

    @app.get("/api/birds/{species_code}/collection-state", response_model=CollectionStateResponse)
    async def state(species_code: str) -> CollectionStateResponse | JSONResponse:
        if not re.fullmatch(r"[A-Za-z0-9]{1,64}", species_code):
            return _error("invalid_request", "Invalid bird species code", 400)
        if not Path(database_path).exists():
            return _error("not_found", "Bird not found in the current Arizona catalog", 404)
        connection = None
        try:
            connection = read_connection()
            result = collection_state(connection, species_code)
            if (
                result["catalog_status"] == "stale"
                and result["observation_count"] == 0
                and not result["watched"]
            ):
                return _error("not_found", "Bird not found in the current Arizona catalog", 404)
            return CollectionStateResponse.model_validate(result)
        except duckdb.Error as exc:
            return _error(
                "database_busy" if _busy(exc) else "database_unavailable",
                "The local collection is unavailable",
                503,
            )
        finally:
            if connection is not None:
                connection.close()
