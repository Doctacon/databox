MODEL (
  name birding_agent.gbif_iceberg_occurrences,
  kind FULL,
  description 'Local SQLMesh materialization of the AWS Polaris Iceberg GBIF occurrence table.'
);

SELECT
  key,
  scientific_name,
  decimal_latitude,
  decimal_longitude,
  event_date
FROM polaris_aws.raw_gbif.occurrences;
