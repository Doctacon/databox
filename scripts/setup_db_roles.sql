-- Create roles for schema-layer access control.
-- Run once against the DuckDB database before applying SQLMesh grants.
--
-- staging_reader: internal/raw and CDM build-layer reads
-- domain_reader:  CDM dimensions/facts
-- analyst:        curated CDM and operational analytics reads

CREATE ROLE IF NOT EXISTS staging_reader;
CREATE ROLE IF NOT EXISTS domain_reader;
CREATE ROLE IF NOT EXISTS analyst;
