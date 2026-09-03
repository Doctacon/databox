Status: active
Created: 2026-09-03
Updated: 2026-09-03

# Run real Polaris/Iceberg integration only by protected manual dispatch

## Context

Databox ordinary pull-request CI must validate real source contracts and Dagster graph construction without developer-local configuration or cloud credentials. Actual Polaris/S3 publication is still an essential integration contract, but it requires secrets and can create external side effects. The Rufous extraction PR exposed that the current workflow conflates import-time graph construction with writer initialization.

## Decision

Databox will run the real Polaris/S3 Iceberg integration workflow only through explicit `workflow_dispatch` in a protected GitHub environment. The workflow MUST exchange its GitHub OIDC token for `DATABOX_AWS_ROLE_ARN`; it MUST NOT use static AWS access-key secrets. It MUST generate disposable Polaris/Postgres credentials inside the job and must not store Polaris credentials. Routine pull-request CI MUST remain credential-free, perform no live source/network/S3 publication, and validate the real asset graph structurally. Execution-boundary tests MUST prove missing Iceberg credentials fail closed before publication.

## Alternatives considered

- **Automatic post-merge main run:** rejected because it detects integration failure after merge.
- **Required PR integration check:** rejected because it unnecessarily exposes protected secrets and consumes local-authority integration infrastructure for every PR.
- **Mocked source/destination gate:** rejected because it would not prove the real Polaris/S3 contract.

## Consequences

A human must explicitly launch and inspect the protected integration run before a change needing live destination evidence is treated as proven. Ordinary CI remains reproducible in GitHub-hosted runners. The protected job must use only configured environment secrets and must not print them.
