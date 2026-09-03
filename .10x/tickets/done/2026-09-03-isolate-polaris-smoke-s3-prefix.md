Status: done
Created: 2026-09-03
Updated: 2026-09-03
Parent: None
Depends-On: .10x/tickets/done/2026-09-03-repair-polaris-workflow-runner-and-mask.md

# Isolate Polaris smoke S3 prefix

## Scope
Prevent the protected integration workflow from writing beneath the normal `s3://<bucket>/warehouse/` prefix. Add a configurable Iceberg warehouse prefix whose normal default remains `warehouse`, and set the manual workflow to a GitHub-run-specific integration prefix.

## Acceptance criteria
- Normal runtime retains `warehouse` as the default prefix.
- The manual integration workflow uses a unique prefix containing GitHub run ID and attempt.
- Destination construction uses the configured prefix safely.
- Tests prove default behavior and workflow isolation.
- No production refresh, catalog authority, trigger, or cleanup behavior changes.

## Evidence expectations
Focused tests, diff check, hosted PR CI, and a protected manual rerun after merge.

## Progress and notes
- 2026-09-03: Opened after identifying that the disposable catalog still targeted the normal S3 `warehouse/` prefix. Prior runs failed before publication.
- 2026-09-03: Added the `DATABOX_ICEBERG_WAREHOUSE_PREFIX` setting with the unchanged `warehouse` default, normalized it at destination construction, and isolated manual workflow writes beneath `integration/<run-id>/<attempt>/warehouse`. Focused settings, destination, and workflow tests passed (13 tests); hosted CI and a protected post-merge rerun remain required.

- 2026-09-03: Protected run 33814484913 passed with source-scoped `integration/<run>/<attempt>/<source>/warehouse` prefixes. The workflow retained `warehouse` as the normal runtime default; integration objects were not deleted.

## Blockers
None.
