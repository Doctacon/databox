Status: recorded
Created: 2026-09-03
Updated: 2026-09-03
Ticket: .10x/tickets/2026-09-03-repair-hermetic-ci-and-iceberg-integration-gate.md

# Hermetic CI and protected Iceberg integration gate

## Diagnosis

PR #41 hosted CI failed because Iceberg credentials were checked during Dagster asset-definition import, the structural layout checker required its pre-extraction one-asset list and treated the public-only USFWS provider as a scheduled Databox source, and intentional Rufous contract deletions lacked schema-gate acknowledgements.

## Repair

`iceberg_destination()` now constructs the real dlt filesystem destination without I/O. `require_iceberg_write_credentials()` runs at every retained ingestion asset execution boundary immediately before `dlt.run`, so missing credentials still fail before a publication attempt. No source or destination result is mocked.

Source-layout validation now accepts the retained `dlt_assets`, load-status, and refresh assets structurally, requires the dlt asset exactly once, recognizes USFWS as a documented public-interface-only provider, and has an AVONET atomic-replace publication test.

`.github/workflows/polaris-iceberg-integration.yaml` is manual-dispatch-only, uses the protected `polaris-iceberg-integration` environment, starts a disposable local Polaris catalog, and runs the real `task verify` against configured environment secrets. It is not a PR, push, schedule, or deployment trigger.

PR #41 body now contains these exact acknowledgements:

```text
accept-breaking-change: databox/birding_agent/arizona_species_catalog
accept-breaking-change: databox/birding_agent/gbif_iceberg_occurrences
accept-breaking-change: databox/birding_agent/gbif_occurrence_evidence
accept-breaking-change: databox/birding_agent/recent_observation_evidence
accept-breaking-change: databox/birding_agent/species_lookup
accept-breaking-change: databox/birding_agent/xeno_canto_media_evidence
accept-breaking-change: databox/rufous_public/avonet_species_traits
accept-breaking-change: databox/rufous_public/gbif_eod_occurrence
accept-breaking-change: databox/rufous_public/inaturalist_commercial_image
accept-breaking-change: databox/rufous_public/usfws_commercial_image
```

The current PR #41 body was read through `gh pr view 41 --json body`; it includes the list above and no credentials.

## Validation

- Credential-empty definitions subprocess: passed.
- Credential-empty source-layout subprocess: passed, 7 retained sources.
- Focused boundary/layout/workflow tests: 54 passed.
- Schema gate with current PR body: all ten removals acknowledged.
- `task ci`: 388 tests, 85.29% coverage; secret and generated-file checks passed.
- Focused Ruff passed. Full `mypy packages/` was included in the passing `task ci` run; a narrower ad-hoc mypy invocation that omitted the sibling package path is not authoritative.

## Residual risk

The protected GitHub environment and its named secrets must be configured before the manual integration workflow can be dispatched. The manual workflow deliberately performs real smoke publication and requires an operator to initiate and inspect it.

## Hosted coverage follow-up

The first repaired hosted run left the public-only USFWS provider suite outside aggregate coverage, dropping total coverage to 67%. `tests-all` now runs the actual offline `packages/databox-sources/tests/usfws` suite in an isolated appended coverage process before the registry-source loop. It does not register USFWS as a scheduled source. The exact hosted-equivalent sequence passes locally at 85% coverage, and `test_workflow_consumes_registry_matrix_without_source_names` asserts the retained provider path is present.
