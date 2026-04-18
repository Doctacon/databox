MODEL (
  name usgs_staging.stg_usgs_sites,
  kind VIEW,
  description 'Staging model for USGS monitoring site metadata',
  grants (select_ = ['staging_reader'])
);

SELECT
    site_no,
    site_name,
    site_type,
    latitude,
    longitude,
    county_cd,
    state_cd,
    huc_cd,
    drain_area_va AS drainage_area_sqmi,
    begin_date,
    end_date,
    _loaded_at::TIMESTAMP AS loaded_at
FROM raw_usgs.sites
