Status: active
Created: 2026-09-02
Updated: 2026-09-02

# dlt-to-Polaris Iceberg source cutover requirements

dlt 1.30 writes Iceberg through its `filesystem` destination with `table_format="iceberg"`; Polaris is supplied as a PyIceberg REST catalog. The filesystem client separately performs S3 destination operations, so it must receive the configured `DATABOX_AWS_ACCESS_KEY_ID`, `DATABOX_AWS_SECRET_ACCESS_KEY`, and region in addition to the Polaris catalog configuration.

For a source cutover, use a fresh dlt pipeline identity/state and a fresh target table location. A full reset of an abandoned attempt has three parts: archive/reset the source's local dlt pipeline directory; remove the source-specific destination dlt metadata and orphaned warehouse prefix; and drop any stale Polaris table registration before a new load. Reset only the exact source prefix and catalog table after explicit approval.

A successful first dlt Iceberg load creates `_dlt_load_id` and `_dlt_id` in the initial table schema. If dlt attempts to add either as a required schema evolution, stop and inspect for stale local state, destination metadata, or a stale Polaris registration rather than manually adding the fields.

A cutover is incomplete until observability reads the same authority. dlt's filesystem destination does not register `_dlt_loads` as an Iceberg table, so every successful migrated-source run MUST call `publish_dlt_load_status` before downstream refresh. This publishes one explicit `raw_<source>._dlt_load_status` Iceberg row with the dlt load ID, schema, completion time, success status, and rows committed by that load. Set the source's `iceberg_authoritative=True` registry flag; generated `analytics.platform_health` reads this status table. Regenerate and refresh the model alongside direct SQLMesh consumers.
