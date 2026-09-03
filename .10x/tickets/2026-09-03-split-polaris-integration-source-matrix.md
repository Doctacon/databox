Status: active
Created: 2026-09-03
Updated: 2026-09-03
Parent: None
Depends-On: .10x/tickets/2026-09-03-add-s3-integration-preflight.md

# Split Polaris integration into a source matrix

## Scope
Replace the opaque parallel all-source verification step with one protected matrix job per refresh-eligible source. Each job must use its own disposable Polaris/Postgres catalog and source-specific run-isolated S3 prefix, execute exactly one real source, skip unrelated SQLMesh transformation, and retain independent GitHub job attribution.

## Acceptance criteria
- Matrix covers ebird, gbif, xeno_canto, noaa, usgs, and usgs_earthquakes exactly once.
- Each job executes one named real source through the production Dagster/dlt path with `--skip-sqlmesh`.
- Each source uses `integration/<run>/<attempt>/<source>/warehouse` and a disposable catalog.
- One source failure does not suppress other source execution (`fail-fast: false`).
- Existing OIDC, protected environment, masking, catalog provisioning/authorization, S3 preflight, and cleanup protections remain.
- Workflow tests prove matrix membership, command, isolation, and attribution.

## Explicit exclusions
- Durable production refresh behavior.
- SQLMesh verification.
- Provider mocking.
- IAM changes.

## Progress and notes
- 2026-09-03: Run 33803401394 proved Xeno-canto end-to-end publication. CloudTrail showed all six Polaris self-assume calls succeeded; combined parallel logs discarded five source-specific failures, motivating independent jobs.
- 2026-09-03: Split the protected workflow into six independent, non-fail-fast matrix jobs. Each runs one real source without SQLMesh against its own disposable Polaris catalog and source-scoped integration prefix. Focused structural tests, Ruff, pre-commit, secret scan, YAML parse, and diff checks pass; hosted CI and protected matrix execution remain.

## Blockers
None.
