-- Generated from soda/contracts/usgs_earthquakes_staging/stg_usgs_earthquakes_events.yaml by scripts/generate_staging.py.
-- DO NOT EDIT by hand — run `task staging:generate` to regenerate.
MODEL (
  name usgs_earthquakes_staging.stg_usgs_earthquakes_events,
  kind FULL,
  description 'Staging model for USGS earthquake events (rolling 24h feed)',
  grants (select_ = ['staging_reader'])
);

SELECT
    id,
    magnitude::DOUBLE AS magnitude,
    magnitude_type,
    place,
    title,
    event_time::TIMESTAMP AS event_time,
    event_updated_at::TIMESTAMP AS event_updated_at,
    longitude::DOUBLE AS longitude,
    latitude::DOUBLE AS latitude,
    depth_km::DOUBLE AS depth_km,
    status,
    tsunami_flag::BIGINT AS tsunami_flag,
    significance::BIGINT AS significance,
    event_type,
    alert,
    url,
    _loaded_at::TIMESTAMP AS loaded_at
FROM raw_usgs_earthquakes.main.events
