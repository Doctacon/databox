MODEL (
  name sqlmesh_example.stg_ebird_observations,
  kind VIEW,
  description 'Staging model for eBird bird observations'
);

SELECT
    "subId" AS submission_id,
    "speciesCode" AS species_code,
    "comName" AS common_name,
    "sciName" AS scientific_name,
    "locId" AS location_id,
    "locName" AS location_name,
    "obsDt"::timestamp AS observation_datetime,
    DATE("obsDt"::timestamp) AS observation_date,
    EXTRACT(YEAR FROM "obsDt"::timestamp) AS observation_year,
    EXTRACT(MONTH FROM "obsDt"::timestamp) AS observation_month,
    EXTRACT(DAY FROM "obsDt"::timestamp) AS observation_day,
    EXTRACT(HOUR FROM "obsDt"::timestamp) AS observation_hour,
    "howMany" AS count,
    CASE 
        WHEN "howMany" IS NULL THEN 'X' -- Present but not counted
        ELSE CAST("howMany" AS VARCHAR)
    END AS count_display,
    lat::DOUBLE AS latitude,
    lng::DOUBLE AS longitude,
    "obsValid" AS is_valid,
    "obsReviewed" AS is_reviewed,
    "locationPrivate" AS is_location_private,
    "_region_code" AS region_code,
    "_is_notable" AS is_notable,
    "_loaded_at"::timestamp AS loaded_at
FROM raw_ebird_data.recent_observations

UNION ALL

SELECT
    "subId" AS submission_id,
    "speciesCode" AS species_code,
    "comName" AS common_name,
    "sciName" AS scientific_name,
    "locId" AS location_id,
    "locName" AS location_name,
    "obsDt"::timestamp AS observation_datetime,
    DATE("obsDt"::timestamp) AS observation_date,
    EXTRACT(YEAR FROM "obsDt"::timestamp) AS observation_year,
    EXTRACT(MONTH FROM "obsDt"::timestamp) AS observation_month,
    EXTRACT(DAY FROM "obsDt"::timestamp) AS observation_day,
    EXTRACT(HOUR FROM "obsDt"::timestamp) AS observation_hour,
    "howMany" AS count,
    CASE 
        WHEN "howMany" IS NULL THEN 'X' -- Present but not counted
        ELSE CAST("howMany" AS VARCHAR)
    END AS count_display,
    lat::DOUBLE AS latitude,
    lng::DOUBLE AS longitude,
    "obsValid" AS is_valid,
    "obsReviewed" AS is_reviewed,
    "locationPrivate" AS is_location_private,
    "_region_code" AS region_code,
    "_is_notable" AS is_notable,
    "_loaded_at"::timestamp AS loaded_at
FROM raw_ebird_data.notable_observations