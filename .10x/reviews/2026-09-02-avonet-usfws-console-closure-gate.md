Status: recorded
Created: 2026-09-02
Updated: 2026-09-02
Target: .10x/tickets/2026-09-02-migrate-avonet-to-polaris-iceberg.md; .10x/tickets/2026-09-02-migrate-usfws-to-polaris-iceberg.md; .10x/tickets/2026-09-02-add-local-polaris-console.md
Verdict: concerns

# AVONET, USFWS, and Console closure gate

## Findings

- AVONET: closure blocked. The previously named source-layout, incremental-loading, and ontology documentation is reconciled, but `docs/rufous-public-release.md` still describes AVONET as loading into local DuckDB and running through dlt/DuckDB. This contradicts its active Polaris-authoritative specification. Update that active release procedure to distinguish Iceberg raw authority from downstream DuckDB transformation.
- USFWS: pass. Current-run identity filters both Iceberg tables; exact completion/count checks and the regression with historical rows prevent aggregate historical success from masking an empty current run.
- Polaris Console: pass. Pinned official source, localhost bindings, scoped CORS, and documented endpoint remain supported by source and evidence.

## Verdict

Concerns. USFWS and Console are closure-ready. AVONET remains open until the active public-release documentation contradiction is repaired.

## Residual risk

The public production deployment is separately paused. That pause prevents execution of its stale release path but does not make contradictory active documentation closure-coherent.
