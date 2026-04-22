"""Pydantic schemas at the eBird @dlt.resource boundary.

The models encode the contract between the upstream API response and what dlt
writes to DuckDB. Upstream schema drift (renamed field, flipped type, dropped
required field) surfaces as a `pydantic.ValidationError` at extract time —
before the bad record reaches dlt's writer or a SQLMesh staging view.

`RecentObservation.to_record()` returns a dict keyed by the camelCase API
names (for native fields) and leading-underscore names (for dlt load metadata
fields). This preserves the exact yielded shape that the pre-Pydantic resource
produced, so dlt's normalizer emits the same DuckDB column names as before —
no migration, no schema drift in the warehouse from this change.

Pilot scope: `RecentObservation` covers the `/data/obs/{region}/recent` and
`/data/obs/{region}/recent/notable` endpoints. Extending to the other eBird
resources (species_list, hotspots, taxonomy, region_stats) is tracked by a
follow-up ticket.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class RecentObservation(BaseModel):
    """One eBird recent or notable observation, augmented with dlt load metadata."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    sub_id: str = Field(validation_alias=AliasChoices("subId", "sub_id"))
    species_code: str = Field(validation_alias=AliasChoices("speciesCode", "species_code"))
    com_name: str = Field(validation_alias=AliasChoices("comName", "com_name"))
    sci_name: str = Field(validation_alias=AliasChoices("sciName", "sci_name"))
    loc_id: str = Field(validation_alias=AliasChoices("locId", "loc_id"))
    loc_name: str = Field(validation_alias=AliasChoices("locName", "loc_name"))
    obs_dt: str = Field(validation_alias=AliasChoices("obsDt", "obs_dt"))
    how_many: int | None = Field(default=None, validation_alias=AliasChoices("howMany", "how_many"))
    lat: float
    lng: float
    obs_valid: bool = Field(default=False, validation_alias=AliasChoices("obsValid", "obs_valid"))
    obs_reviewed: bool = Field(
        default=False, validation_alias=AliasChoices("obsReviewed", "obs_reviewed")
    )
    location_private: bool = Field(
        default=False, validation_alias=AliasChoices("locationPrivate", "location_private")
    )
    exotic_category: str | None = Field(
        default=None, validation_alias=AliasChoices("exoticCategory", "exotic_category")
    )

    region_code: str = Field(validation_alias="_region_code")
    loaded_at: str = Field(validation_alias="_loaded_at")
    observation_date: str | None = Field(default=None, validation_alias="_observation_date")
    is_notable: bool = Field(default=False, validation_alias="_is_notable")

    _NATIVE_CAMEL: ClassVar[dict[str, str]] = {
        "sub_id": "subId",
        "species_code": "speciesCode",
        "com_name": "comName",
        "sci_name": "sciName",
        "loc_id": "locId",
        "loc_name": "locName",
        "obs_dt": "obsDt",
        "how_many": "howMany",
        "obs_valid": "obsValid",
        "obs_reviewed": "obsReviewed",
        "location_private": "locationPrivate",
        "exotic_category": "exoticCategory",
    }

    _META_UNDERSCORE: ClassVar[dict[str, str]] = {
        "region_code": "_region_code",
        "loaded_at": "_loaded_at",
        "observation_date": "_observation_date",
        "is_notable": "_is_notable",
    }

    def to_record(self) -> dict[str, Any]:
        """Dump in the exact shape the legacy resource yielded.

        Native API fields come back in camelCase; load-metadata fields keep
        their leading-underscore naming. dlt's normalizer produces the same
        snake_case DuckDB columns as before.
        """
        dumped = self.model_dump()
        out: dict[str, Any] = {}
        for py_name, wire_name in self._NATIVE_CAMEL.items():
            out[wire_name] = dumped[py_name]
        for py_name, wire_name in self._META_UNDERSCORE.items():
            out[wire_name] = dumped[py_name]
        out["lat"] = dumped["lat"]
        out["lng"] = dumped["lng"]
        return out
