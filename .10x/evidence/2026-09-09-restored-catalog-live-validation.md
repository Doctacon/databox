Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/2026-09-04-build-isolated-catalog-recovery-drill.md

# First live registry-derived restored-catalog validation

## Authorization and boundaries

The user authorized one read-only execution against restored Polaris container `databox-polaris-recovery-validation-20260908-214022`, catalog `databox_lake`, PITR target `2026-09-08T21:40:22Z`, and source revision `e95b333`. The validator ran exactly once. Exit `1` was retained as evidence rather than retried. No bootstrap, refresh, catalog or warehouse write, port publication, cutover, restart, artifact reuse/removal, or cleanup occurred.

## Preconditions

Before the run:

- active PostgreSQL was running/healthy with start time `2026-09-08T21:38:31.476511987Z`;
- active Polaris was running/healthy with start time `2026-09-05T16:26:22.471908317Z`;
- active `polaris` database size was `8309907` bytes;
- recovery PostgreSQL was running with validation label `postgres`, no host port, `pg_is_in_recovery()=false`, and `archive_mode=off`;
- recovery marker `95cfab7c-3526-4068-b560-3570313add54` remained `before=1`, `after=0`, total `1`;
- recovery Polaris was running with exact validation label `polaris`, no host port, readiness `UP`, and zero backup/pgBackRest environment variable names.

No environment values or credential material were printed or recorded.

## Exact sanitized validator result

The command exited `1` after one execution. Its only captured application output was the following secret-free JSON:

```json
{"catalog":"databox_lake","container":"databox-polaris-recovery-validation-20260908-214022","counts":{"actualTables":29,"expectedTables":22,"failedTables":0,"validatedTables":22},"elapsedSeconds":54.956,"identifierListsTruncated":false,"malformedObservedIdentifiers":0,"missingNamespaces":[],"missingTables":[],"recoveryTarget":"2026-09-08T21:40:22Z","sourceRevision":"e95b333092483a7103df9cfcfb39b8124fb7ed82","status":"fail","tables":[{"current_snapshot_id":"9202887823362966287","data_readable":true,"failures":[],"identifier":"raw_avonet._dlt_load_status","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"8694055648763694957","data_readable":true,"failures":[],"identifier":"raw_avonet.species_traits","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"3220611568525741217","data_readable":true,"failures":[],"identifier":"raw_ebird._dlt_load_status","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"8496034848567726653","data_readable":true,"failures":[],"identifier":"raw_ebird.hotspots","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"684332236847636134","data_readable":true,"failures":[],"identifier":"raw_ebird.notable_observations","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"74772981870747702","data_readable":true,"failures":[],"identifier":"raw_ebird.recent_observations","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"2659079092852835766","data_readable":true,"failures":[],"identifier":"raw_ebird.region_stats","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"446789018182763469","data_readable":true,"failures":[],"identifier":"raw_ebird.species_list","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"1658936466699473146","data_readable":true,"failures":[],"identifier":"raw_ebird.taxonomy","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"5482499826201601413","data_readable":true,"failures":[],"identifier":"raw_gbif._dlt_load_status","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"1178466210221253080","data_readable":true,"failures":[],"identifier":"raw_gbif.occurrences","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"2295434671445416220","data_readable":true,"failures":[],"identifier":"raw_noaa._dlt_load_status","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"4607915010058499608","data_readable":true,"failures":[],"identifier":"raw_noaa.daily_weather","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"8393879912199099069","data_readable":true,"failures":[],"identifier":"raw_noaa.datasets","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"4886935635820848172","data_readable":true,"failures":[],"identifier":"raw_noaa.stations","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"395242884961931442","data_readable":true,"failures":[],"identifier":"raw_usgs._dlt_load_status","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"351119792656528959","data_readable":true,"failures":[],"identifier":"raw_usgs.daily_values","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"8545786823220109327","data_readable":true,"failures":[],"identifier":"raw_usgs.sites","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"977510186486814735","data_readable":true,"failures":[],"identifier":"raw_usgs_earthquakes._dlt_load_status","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"2739529565986264506","data_readable":true,"failures":[],"identifier":"raw_usgs_earthquakes.events","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"7888852627616769888","data_readable":true,"failures":[],"identifier":"raw_xeno_canto._dlt_load_status","manifests_readable":true,"metadata_readable":true,"sample_rows":1},{"current_snapshot_id":"1443165738712305454","data_readable":true,"failures":[],"identifier":"raw_xeno_canto.recordings","manifests_readable":true,"metadata_readable":true,"sample_rows":1}],"unexpectedNamespaces":["dlt_polaris_probe","raw_usfws"],"unexpectedTables":["dlt_polaris_probe.events","raw_ebird.taxonomy__banding_codes","raw_ebird.taxonomy__com_name_codes","raw_ebird.taxonomy__sci_name_codes","raw_usfws._dlt_load_status","raw_usfws.image_records","raw_usfws.image_search_runs"]}
```

## Interpretation

The live interface and warehouse checks succeeded for every registry-derived expectation: all 22 expected tables were present, loaded through restored Polaris with vended credentials, had readable metadata and a current snapshot, planned manifests, and completed a read-only limit-one data scan. Every table returned one sample row. There were zero table failure stages, zero missing tables/namespaces, zero malformed identifiers, and no truncated identifier list.

The aggregate verdict correctly failed because 29 tables were observed and seven were unexpected. Three are dlt-generated eBird taxonomy child tables not declared by the canonical registry. Three belong to `raw_usfws`, which the canonical registry specification explicitly excludes from orchestrated Databox ownership. One belongs to `dlt_polaris_probe`, a validation/probe namespace rather than a canonical source. This is registry/catalog drift, not unreadable restored data. It is owned by `.10x/tickets/2026-09-09-reconcile-restored-catalog-registry-drift.md`; this run made no policy or cleanup decision.

## Postconditions

After the run, active PostgreSQL and Polaris remained running/healthy with their exact pre-run start times, and active database size remained `8309907`. Recovery PostgreSQL and Polaris remained running, validation-labeled, and unexposed. Recovery Polaris readiness remained `UP`; recovery PostgreSQL remained promoted with archiving off and exact marker counts `before=1`, `after=0`, total `1`.

## Limits

This is temporal validation evidence, not a backup. The aggregate result is a failure until unexpected catalog state is resolved by an approved decision and a new separately authorized validation passes. No timed recovery drill ran, so neither RPO nor RTO is proven. No production cutover, write-path test, catalog cleanup, IAM least-privilege audit, or complete warehouse-loss reconstruction was tested.
