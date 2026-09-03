Status: recorded
Created: 2026-09-03
Updated: 2026-09-03
Relates-To: .10x/tickets/done/2026-09-03-split-polaris-integration-source-matrix.md, .10x/tickets/done/2026-09-03-fix-usgs-daily-value-natural-key.md, .10x/decisions/manual-protected-iceberg-integration-gate.md

# Protected Polaris/S3 source-matrix verification

## Verified revision and procedure

GitHub Actions run [33814484913](https://github.com/Doctacon/databox/actions/runs/33814484913) was dispatched manually against `main` merge commit `1b2e86d9eaeb783429d532fa40ada8557c28b619`, the merge commit for [PR #50](https://github.com/Doctacon/databox/pull/50). The run began at `2026-09-03T22:44:49Z` and completed successfully at `2026-09-03T22:50:45Z`.

The protected `polaris-iceberg-integration` environment authorized each matrix job. Each job:

1. exchanged GitHub OIDC identity for the scoped AWS role;
2. generated and masked disposable Postgres and Polaris credentials;
3. started an isolated local Polaris/Postgres stack;
4. provisioned and authorized `databox_lake` against `s3://<bucket>/integration/33814484913/1/<source>/warehouse`;
5. preflighted STS identity and read-only access to its isolated S3 prefix;
6. ran exactly one real provider source through the production Dagster/dlt Iceberg path with SQLMesh skipped; and
7. tore down its disposable local catalog stack.

No static AWS credential secret was used. The bucket, role ARN, and provider tokens came from the protected GitHub environment; credential values and provider payloads are not retained in this record.

## Independent job results

| Source | Job | Result | Completed (UTC) |
| --- | --- | --- | --- |
| eBird | [100843470151](https://github.com/Doctacon/databox/actions/runs/33814484913/job/100843470151) | success | 22:48:34 |
| GBIF | [100843469998](https://github.com/Doctacon/databox/actions/runs/33814484913/job/100843469998) | success | 22:46:58 |
| NOAA | [100843470219](https://github.com/Doctacon/databox/actions/runs/33814484913/job/100843470219) | success | 22:50:44 |
| USGS | [100843470344](https://github.com/Doctacon/databox/actions/runs/33814484913/job/100843470344) | success | 22:47:27 |
| USGS Earthquakes | [100843470191](https://github.com/Doctacon/databox/actions/runs/33814484913/job/100843470191) | success | 22:46:54 |
| Xeno-canto | [100843470192](https://github.com/Doctacon/databox/actions/runs/33814484913/job/100843470192) | success | 22:47:05 |

The preceding run, [33813273328](https://github.com/Doctacon/databox/actions/runs/33813273328), isolated a USGS PyIceberg merge rejection caused by three daily statistics sharing the old `(site_no, parameter_cd, observation_date)` key. PR #50 preserved source `statistic_cd` and extended the natural key. The successful run above is post-repair evidence for that real source path.

## Claims supported

This run proves all six routine refresh providers can independently traverse their real extraction, Dagster/dlt execution, Polaris REST catalog, temporary credential vending, isolated S3 Iceberg publication, and authoritative post-load inspection path at the verified revision. It also proves one source failure no longer suppresses sibling diagnostics and that the USGS source-backed statistic identity is accepted by the real PyIceberg merge path.

Together with ordinary credential-free CI, it closes the protected-gate repair chain implemented by PRs #43–#50.

## Limits and retained operations

- The matrix deliberately skips SQLMesh; ordinary CI and local refresh validation own model behavior.
- AVONET is a pinned explicit snapshot job and is excluded from routine refresh. USFWS requires caller-owned targets and is not a matrix source.
- Each job uses a disposable local Polaris metadata database. This run does not prove availability of a persistent remote catalog service.
- Run-scoped objects remain under `integration/33814484913/1/`; cleanup and retention were outside the integration tickets. The production `warehouse/` prefix was not a workflow target.
- A successful bounded run does not guarantee indefinite provider availability or future schema stability. The protected workflow remains manual-only and requires operator approval.
