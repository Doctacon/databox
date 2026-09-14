Status: recorded
Created: 2026-09-10
Updated: 2026-09-10
Relates-To: .10x/tickets/2026-09-04-run-timed-catalog-recovery-drill.md, .10x/specs/polaris-catalog-continuity.md

# Timed catalog recovery drill passed

## What was observed

The operator ran the reviewed `catalog:recovery-drill` command at source revision `da9e5e5d81cc10f56a13b56330b62062738952a5`. The command returned `status=pass`.

Manual WAL catch-up found six locally retained pending segments, oldest `000000010000000000000015` and newest `00000001000000000000001A`. The oldest had waited 84,386.12848 seconds since `2026-09-09T20:55:29Z`; loss before catch-up was explicitly accepted. The command uploaded those six segments oldest-first plus marker segment `00000001000000000000001B`, then read back and verified eight contiguous remote segments from anchor `000000010000000000000014` through `00000001000000000000001B` before restore.

The marker bracket was:

- before: `2026-09-10T20:22:53.712787Z`;
- target: `2026-09-10T20:22:53.787030Z`;
- after: `2026-09-10T20:22:53.849010Z`.

The marker target-inclusion gap was 0.074243 seconds. This is not represented as continuous off-machine RPO.

End-to-end RTO, measured from before interactive authentication through completed catalog validation, was 226.243827542 seconds (3 minutes 46.244 seconds), meeting the 3,600-second objective.

## Catalog validation

Registry-derived validation completed in 66.321 seconds:

- expected canonical tables: 25;
- validated canonical tables: 25;
- failed canonical tables: 0;
- actual restored tables: 29;
- malformed identifiers: 0;
- missing namespaces/tables: none;
- canonical-namespace unexpected tables: none.

Every canonical table passed metadata, current-snapshot, manifest, and limit-one data-read checks. REST and S3 current snapshot IDs matched. The known noncanonical warnings remained explicit: namespaces `dlt_polaris_probe` and `raw_usfws`; tables `dlt_polaris_probe.events`, `raw_usfws._dlt_load_status`, `raw_usfws.image_records`, and `raw_usfws.image_search_runs`.

## Isolation and cleanup

The command reported marker drop complete and cleanup WAL archive complete. No active drill marker remains. Production PostgreSQL and Polaris remain running and healthy with unchanged start times.

Preserved isolated resources:

- volume `databox_polaris_recovery_drill_esaohqcumduou8to`, cryptographically ownership-labeled;
- network `databox_polaris_recovery_drill_esaohqcumduou8to`;
- running PostgreSQL `databox-polaris-recovery-drill-postgres-esaohqcumduou8to`, no host ports, restart policy `no`, secret-free configuration;
- stopped Polaris `databox-polaris-recovery-drill-polaris-esaohqcumduou8to`, no host ports, restart policy `no`, secret-free configuration.

No cutover or recovery-resource deletion occurred.

## Procedure

Captured the operator-provided bounded JSON result, then independently inspected active/recovery container health, ports, restart policies, configuration environments, labels, volume/network ownership, and active marker count. These follow-up checks were read-only.

## What this supports

This proves one authenticated manual catch-up can close the retained local WAL gap, verify remote continuity, perform microsecond PITR into isolated resources, promote and scrub recovery PostgreSQL credentials, start restored Polaris without bootstrap, and validate all 25 canonical Iceberg tables within the 60-minute RTO.

## Limits

The drill does not prove continuous off-machine RPO; the accepted local model may lose changes made after the last authenticated catch-up if the local machine or disk is lost. Complete Iceberg warehouse loss remains source reconstruction. Preserved recovery artifacts require separately authorized cleanup.
