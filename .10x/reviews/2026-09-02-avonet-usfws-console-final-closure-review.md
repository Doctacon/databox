Status: recorded
Created: 2026-09-02
Updated: 2026-09-02
Target: .10x/tickets/2026-09-02-migrate-avonet-to-polaris-iceberg.md; .10x/tickets/2026-09-02-migrate-usfws-to-polaris-iceberg.md; .10x/tickets/2026-09-02-add-local-polaris-console.md
Verdict: concerns

# AVONET, USFWS, and Polaris Console final closure review

## AVONET

Verdict: concerns, non-blocking implementation risk.

The committed source preserves pinned validation and publishes direct dlt Iceberg replacement. Registry/orchestration remains independent and unscheduled; consumers use Polaris. `.10x/evidence/2026-09-02-avonet-polaris-iceberg-migration.md` supports exact row count, both uniqueness checks, lineage, load status, consumer counts, and test gates.

Stale descriptions in `docs/source-layout.md`, `docs/incremental-loading.md`, and `.schema/environmental_observations/ontology.md` still describe Quack staging/manual publication and contradict the active AVONET specification. This documentation debt needs a durable repair before graph-coherent closure.

## USFWS

Verdict: fail.

The explicit-target lifecycle, Iceberg merge tables, lineage, load status, Polaris consumer, licensing rules, and bounded live ingestion are supported by source inspection and `.10x/evidence/2026-09-02-usfws-polaris-iceberg-migration.md`.

Closure blocker: `ingest_public_usfws_media` verifies aggregate historical `image_records` and completed runs after ingestion rather than filtering both checks to the submitted run. Because merge semantics preserve prior run IDs, historical rows can mask a current run that contributes no valid records. The current focused test also uses aggregate counts and does not prove current-run identity. The owning USFWS migration ticket must remain open until verification uses a caller-known run ID and a regression proves historical rows cannot mask an empty current run.

## Polaris Console

Verdict: pass.

Pinned official source, localhost binding, explicit API configuration, CORS, Compose validation, service readiness, and HTML response are supported by committed source and `.10x/evidence/2026-09-02-local-polaris-console.md`. End-to-end login remains untested but was not an acceptance criterion.

## Aggregate verdict

Concerns. The prior evidence and active-specification blockers are resolved. Polaris Console is closure-ready. AVONET needs stale authority documentation reconciled for graph-coherent closure. USFWS has a functional current-run verification blocker and is not closure-ready.

## Residual risk

The deployed Console depends on documented OAuth defaults for blank optional runtime overrides. AVONET implementation is supported but stale docs could mislead operators. USFWS aggregate verification can report success from historical rows after an ineffective current ingestion.
