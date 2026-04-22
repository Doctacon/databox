"""Unit tests for the eBird RecentObservation Pydantic contract.

Pilot tests for ticket:pydantic-source-typing. Verifies the model:

- round-trips a known-good API payload to the exact legacy wire shape, so
  dlt's DuckDB schema is unchanged by the migration
- raises on upstream drift (missing required field, wrong type) before the
  record reaches dlt's writer
- tolerates extra fields the API adds (forward-compatible)
"""

from __future__ import annotations

import pendulum
import pytest
from databox_sources.ebird.models import RecentObservation
from pydantic import ValidationError

GOOD_API_PAYLOAD = {
    "subId": "S123456789",
    "speciesCode": "rethaw",
    "comName": "Red-tailed Hawk",
    "sciName": "Buteo jamaicensis",
    "locId": "L9876543",
    "locName": "Tucson Mountain Park",
    "obsDt": "2026-04-21 08:15",
    "howMany": 2,
    "lat": 32.221,
    "lng": -111.017,
    "obsValid": True,
    "obsReviewed": False,
    "locationPrivate": False,
}


def _enriched(payload: dict, region: str = "US-AZ", notable: bool = False) -> dict:
    out = dict(payload)
    out["_region_code"] = region
    out["_loaded_at"] = pendulum.now().isoformat()
    out["_observation_date"] = payload.get("obsDt")
    out["_is_notable"] = notable
    return out


def test_good_payload_validates() -> None:
    obs = RecentObservation.model_validate(_enriched(GOOD_API_PAYLOAD))
    assert obs.species_code == "rethaw"
    assert obs.how_many == 2
    assert obs.region_code == "US-AZ"
    assert obs.is_notable is False


def test_record_preserves_legacy_wire_shape() -> None:
    """to_record() must emit the exact keys the legacy resource yielded."""
    obs = RecentObservation.model_validate(_enriched(GOOD_API_PAYLOAD))
    record = obs.to_record()
    expected_keys = {
        "subId",
        "speciesCode",
        "comName",
        "sciName",
        "locId",
        "locName",
        "obsDt",
        "howMany",
        "lat",
        "lng",
        "obsValid",
        "obsReviewed",
        "locationPrivate",
        "_region_code",
        "_loaded_at",
        "_observation_date",
        "_is_notable",
    }
    assert set(record.keys()) == expected_keys
    assert record["subId"] == "S123456789"
    assert record["_region_code"] == "US-AZ"


def test_missing_required_field_raises() -> None:
    """Drift: upstream drops speciesCode. Must fail at extract."""
    bad = dict(_enriched(GOOD_API_PAYLOAD))
    del bad["speciesCode"]
    with pytest.raises(ValidationError) as exc:
        RecentObservation.model_validate(bad)
    assert "species_code" in str(exc.value) or "speciesCode" in str(exc.value)


def test_type_flip_raises() -> None:
    """Drift: upstream sends howMany as a non-numeric string. Must fail."""
    bad = dict(_enriched(GOOD_API_PAYLOAD))
    bad["howMany"] = "not-a-number"
    with pytest.raises(ValidationError):
        RecentObservation.model_validate(bad)


def test_missing_optional_how_many_ok() -> None:
    """howMany is legitimately absent on 'X' observations — must not raise."""
    ok = dict(_enriched(GOOD_API_PAYLOAD))
    del ok["howMany"]
    obs = RecentObservation.model_validate(ok)
    assert obs.how_many is None
    assert obs.to_record()["howMany"] is None


def test_extra_fields_tolerated() -> None:
    """Upstream adding a new field (e.g. hasRichMedia) must not break extract."""
    extra = dict(_enriched(GOOD_API_PAYLOAD))
    extra["hasRichMedia"] = True
    extra["newFutureField"] = {"nested": "data"}
    obs = RecentObservation.model_validate(extra)
    assert "hasRichMedia" not in obs.to_record()


def test_notable_flag_propagates() -> None:
    obs = RecentObservation.model_validate(_enriched(GOOD_API_PAYLOAD, notable=True))
    assert obs.is_notable is True
    assert obs.to_record()["_is_notable"] is True
