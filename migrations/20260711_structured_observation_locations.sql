-- Additive, idempotent private observation location migration.
-- Existing location_text and observation rows remain unchanged; no values are inferred.
ALTER TABLE birding_personal.observations
  ADD COLUMN IF NOT EXISTS location_source VARCHAR;
ALTER TABLE birding_personal.observations
  ADD COLUMN IF NOT EXISTS location_source_id VARCHAR;
ALTER TABLE birding_personal.observations
  ADD COLUMN IF NOT EXISTS location_latitude DOUBLE;
ALTER TABLE birding_personal.observations
  ADD COLUMN IF NOT EXISTS location_longitude DOUBLE;
ALTER TABLE birding_personal.observations
  ADD COLUMN IF NOT EXISTS location_timezone VARCHAR;
ALTER TABLE birding_personal.observations
  ADD COLUMN IF NOT EXISTS location_region_code VARCHAR;
