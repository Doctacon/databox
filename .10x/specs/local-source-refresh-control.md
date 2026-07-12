Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Local source refresh control

## Purpose and scope

Provide a header action that explicitly launches the existing routine local source refresh while preserving one-Quack ownership, SQLMesh ordering, personal/runtime state, credentials, and safe user feedback.

## Refresh contract

A confirmed refresh MUST execute the same registered routine scope as `task full-refresh`: eBird, GBIF, Xeno-canto, NOAA, USGS, and USGS Earthquakes concurrently through exactly one Quack server owning `data/databox.duckdb`; wait for all required loads; clean clients/dedupe/inspect; and run native SQLMesh only after every required load succeeds. AVONET and catalog-media enrichment MUST NOT run. No alternate sequential fallback is allowed.

The app server MUST launch the established orchestration in an isolated background subprocess rather than duplicate ingestion logic. At most one refresh may run. The command, database path, source scope, environment, and log destination are server-owned constants; browser input cannot supply commands, paths, sources, model/provider settings, credentials, or arguments.

## API and security

Typed same-origin local endpoints MUST provide: read-only status and an explicit confirmed POST launch. Launch MUST reject missing confirmation, disallowed Origin/Host, malformed bodies, and an already-running refresh. Cross-origin/simple-form invocation MUST not start work. Responses and logs MUST be bounded and redact secrets, credentials, private/personal data, arbitrary upstream payloads, and raw exception text.

Durable atomic status outside DuckDB under `.logs/` MUST survive page reload and app restart and include only run ID, state, routine source names/statuses, safe timestamps, phase, safe terminal message, and log reference. States are `idle`, `running_sources`, `running_sqlmesh`, `succeeded`, and `failed`. No automatic retry, scheduled run, cancellation, or launch on startup/GET is permitted.

## UI lifecycle

A keyboard-accessible header button appears beside `Local DuckDB · evidence-backed`. Activation opens an explicit confirmation naming external source calls and local warehouse mutation. Once confirmed, it launches once, disables while active, and polls bounded status. The header shows current phase and source progress.

The shell remains responsive, but warehouse-backed endpoints may return their existing database-busy state during refresh; the UI MUST explain this and preserve already-rendered state where safe. Failure remains visible with a safe log pointer and explicit Retry action requiring a new confirmation. Success uses the universal 3,000-ms success notice; a neutral `Last refreshed` timestamp may remain. No retry is automatic.

## Data and side-effect inventory

- State transition: idle/terminal → confirmed launch → sources → SQLMesh → success/failure.
- Data: routine raw/SQLMesh tables may change; personal observations, Watches, plans, calendar/outbox, runtime media, credentials, and unrelated local files MUST be preserved.
- External effects: six established source clients may call their governed providers; SQLMesh runs only after success.
- Permissions/owner: loopback single user; same-origin and confirmation are still mandatory.
- Failure: source-attributed failure, no SQLMesh after source failure, no implicit retry, persistent safe status/log.
- Operational owner and retry authority: the local user.

## Acceptance scenarios

- GET/status/page load cannot start a refresh.
- One confirmed launch runs the exact routine source set through one Quack owner and then SQLMesh.
- Second launch while active returns safe conflict and starts nothing.
- One source failure prevents SQLMesh and produces persistent attributed failure.
- Browser cannot alter command/scope/path/environment and cross-origin launch fails.
- Personal/runtime checksums and tables survive successful and failed test runs.
- Busy warehouse behavior, reload/restart status recovery, 3-second success, persistent failure, and explicit retry are tested.

## Exclusions

No AVONET, media refresh, model call, email, scheduled refresh, cancellation, arbitrary Dagster job selection, literal materialize-all bypass, fully available staged warehouse, runtime-state merge, or atomic database swap.
