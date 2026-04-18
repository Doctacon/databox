-- Create roles for schema-layer access control.
-- Run once against the DuckDB database before applying SQLMesh grants.
--
-- staging_reader: internal/raw cleansed data
-- domain_reader:  source-specific marts (ebird, noaa, usgs)
-- analyst:        cross-domain analytics only

CREATE ROLE IF NOT EXISTS staging_reader;
CREATE ROLE IF NOT EXISTS domain_reader;
CREATE ROLE IF NOT EXISTS analyst;
