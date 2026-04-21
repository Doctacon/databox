-- Generated from soda/contracts/usgs_staging/stg_usgs_daily_values.yaml by scripts/generate_staging.py.
-- DO NOT EDIT by hand — run `task staging:generate` to regenerate.
MODEL (
  name usgs_staging.stg_usgs_daily_values,
  kind FULL,
  description 'Staging model for USGS daily streamflow and gage observations',
  grants (select_ = ['staging_reader'])
);

SELECT
    site_no,
    site_name,
    latitude,
    longitude,
    parameter_cd,
    parameter_name,
    unit_cd,
    observation_date::DATE AS observation_date,
    value,
    qualifier,
    _state_cd AS state_cd,
    _loaded_at::TIMESTAMP AS loaded_at
FROM raw_usgs.main.daily_values
