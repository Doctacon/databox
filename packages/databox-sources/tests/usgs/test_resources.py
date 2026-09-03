"""Unit tests for USGS NWIS dlt resources."""

from __future__ import annotations

import pytest
from databox_sources.usgs.source import _parse_daily_value_records, usgs_source

FROZEN_NOW = "2026-02-15T00:00:00Z"


@pytest.mark.vcr
@pytest.mark.time_machine(FROZEN_NOW)
def test_daily_values_returns_rows():
    source = usgs_source(state_cd="RI", parameter_cds="00060", days_back=3)
    rows = list(source.resources["daily_values"])

    assert len(rows) > 0, "expected at least one USGS daily streamflow reading"

    sample = rows[0]
    for key in (
        "site_no",
        "parameter_cd",
        "statistic_cd",
        "observation_date",
        "value",
        "_state_cd",
        "_loaded_at",
    ):
        assert key in sample, f"missing expected key '{key}' in row {sample!r}"

    assert sample["_state_cd"] == "RI"
    assert sample["parameter_cd"] == "00060"
    assert sample["statistic_cd"] == "00003"
    if sample.get("value") is not None:
        assert isinstance(sample["value"], float)
    if sample.get("latitude") is not None:
        assert isinstance(sample["latitude"], float)


def test_daily_value_statistics_are_distinct_natural_keys() -> None:
    statistic_series = []
    for statistic_cd, statistic_name, value in (
        ("00001", "Maximum", "21.8"),
        ("00002", "Minimum", "20.5"),
        ("00003", "Mean", "21.2"),
    ):
        statistic_series.append(
            {
                "sourceInfo": {
                    "siteCode": [{"value": "09380000"}],
                    "siteName": "Colorado River at Lees Ferry",
                },
                "variable": {
                    "variableCode": [{"value": "00010"}],
                    "variableName": "Temperature, water",
                    "options": {
                        "option": [
                            {
                                "name": "Statistic",
                                "value": statistic_name,
                                "optionCode": statistic_cd,
                            }
                        ]
                    },
                },
                "values": [
                    {
                        "value": [
                            {
                                "value": value,
                                "dateTime": "2026-09-01T00:00:00.000",
                            }
                        ]
                    }
                ],
            }
        )

    rows = list(
        _parse_daily_value_records(
            {"value": {"timeSeries": statistic_series}},
            "AZ",
            "2026-09-03T00:00:00Z",
        )
    )
    natural_keys = {
        (
            row["site_no"],
            row["parameter_cd"],
            row["statistic_cd"],
            row["observation_date"],
        )
        for row in rows
    }

    assert len(rows) == 3
    assert len(natural_keys) == 3
    assert {row["statistic_cd"] for row in rows} == {"00001", "00002", "00003"}
