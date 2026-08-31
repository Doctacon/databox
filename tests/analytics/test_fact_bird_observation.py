from __future__ import annotations

from pathlib import Path

import duckdb

MODEL = (
    Path(__file__).parents[2]
    / "transforms/main/models/environmental_observations/facts/fact_bird_observation.sql"
)


def _model_query() -> str:
    sql = MODEL.read_text()
    return "WITH observations AS" + sql.split("WITH observations AS", maxsplit=1)[1]


def test_checklist_species_identity_uses_freshest_cross_feed_quality_state() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA raw_ebird")
    connection.execute("CREATE SCHEMA environmental_observations")
    connection.execute(
        """
        CREATE TABLE raw_ebird.recent_observations (
          sub_id TEXT, species_code TEXT, com_name TEXT, sci_name TEXT,
          loc_id TEXT, loc_name TEXT, obs_dt TIMESTAMP, how_many BIGINT,
          lat DOUBLE, lng DOUBLE, obs_valid BOOLEAN, obs_reviewed BOOLEAN,
          location_private BOOLEAN, _region_code TEXT, exotic_category TEXT,
          _loaded_at TIMESTAMP, _dlt_load_id TEXT, _dlt_id TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE raw_ebird.notable_observations AS
        SELECT * FROM raw_ebird.recent_observations WHERE FALSE
        """
    )
    connection.execute(
        """
        CREATE TABLE environmental_observations.dim_species (
          species_sk TEXT, species_natural_key TEXT,
          source_pipeline TEXT, source_id TEXT
        )
        """
    )
    connection.execute(
        """
        INSERT INTO environmental_observations.dim_species VALUES
          ('cardinal-sk', 'cardinalis cardinalis', 'ebird_api', 'norcar'),
          ('robin-sk', 'turdus migratorius', 'ebird_api', 'amerob')
        """
    )
    connection.execute(
        """
        CREATE TABLE environmental_observations.dim_bird_hotspot (
          bird_hotspot_sk TEXT, source_pipeline TEXT, source_id TEXT
        )
        """
    )
    connection.execute(
        """
        INSERT INTO environmental_observations.dim_bird_hotspot
        VALUES ('hotspot-sk', 'ebird_api', 'L1')
        """
    )
    connection.execute(
        """
        INSERT INTO raw_ebird.recent_observations VALUES
          ('S1', 'norcar', 'Northern Cardinal', 'Cardinalis cardinalis',
           'L1', 'Public Park', '2026-07-30 07:00:00', 1, 34.54, -112.47,
           TRUE, TRUE, FALSE, 'US-AZ', NULL, '2026-07-30 08:00:00', 'load-1', 'old'),
          ('S1', 'norcar', 'Northern Cardinal', 'Cardinalis cardinalis',
           'L1', 'Public Park', '2026-07-30 07:00:00', 2, 34.54, -112.47,
           TRUE, TRUE, FALSE, 'US-AZ', NULL, '2026-07-30 09:00:00', 'load-2', 'new'),
          ('S1', 'amerob', 'American Robin', 'Turdus migratorius',
           'L1', 'Public Park', '2026-07-30 07:00:00', 3, 34.54, -112.47,
           TRUE, TRUE, FALSE, 'US-AZ', NULL, '2026-07-30 08:00:00', 'load-1', 'robin'),
          ('S1', 'amerob', 'American Robin', 'Turdus migratorius',
           'L1', 'Private location', '2026-07-30 07:00:00', 3, 0.0, 0.0,
           FALSE, TRUE, TRUE, 'US-AZ', NULL, '2026-07-30 11:00:00', 'load-4', 'robin-private')
        """
    )
    connection.execute(
        """
        INSERT INTO raw_ebird.notable_observations VALUES
          ('S1', 'norcar', 'Northern Cardinal', 'Cardinalis cardinalis',
           'L1', 'Public Park', '2026-07-30 07:00:00', 4, 34.54, -112.47,
           TRUE, TRUE, FALSE, 'US-AZ', NULL, '2026-07-30 10:00:00', 'load-3', 'notable'),
          ('S1', 'amerob', 'American Robin', 'Turdus migratorius',
           'L1', 'Public Park', '2026-07-30 07:00:00', 3, 34.54, -112.47,
           TRUE, TRUE, FALSE, 'US-AZ', NULL, '2026-07-30 10:00:00', 'load-3', 'robin-notable')
        """
    )

    cursor = connection.execute(_model_query())
    columns = [column[0] for column in cursor.description]
    rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    connection.close()

    assert {row["source_observation_id"] for row in rows} == {"S1|norcar", "S1|amerob"}
    assert {row["bird_observation_sk"] for row in rows} == {
        "6ab60c8636cd353f22cf2111506f5dbe",
        "f4b4546e4bebd4470dd77a97f2e6d13d",
    }
    cardinal = next(row for row in rows if row["species_code"] == "norcar")
    assert cardinal["observation_count"] == 4
    assert cardinal["dlt_id"] == "notable"
    assert cardinal["source_table"] == "notable_observations"
    assert cardinal["is_notable"] is True
    robin = next(row for row in rows if row["species_code"] == "amerob")
    assert robin["dlt_id"] == "robin-private"
    assert robin["source_table"] == "recent_observations"
    assert robin["is_notable"] is False
    assert robin["is_valid"] is False
    assert robin["is_location_private"] is True
