Status: recorded
Created: 2026-09-03
Updated: 2026-09-03
Target: .10x/tickets/done/2026-09-03-transfer-rufous-records-and-docs.md, .10x/tickets/done/2026-09-03-prune-rufous-from-databox.md
Verdict: pass

# Rufous record transfer and Databox prune review

## Findings

The review confirmed Databox retains all twelve artifact relation definitions, their environmental/source inputs, the public `databox_sources.usfws` exports, and public provider tests. The Rufous-target USFWS job, product-specific iNaturalist implementation, application, worker, product models, product workflows, and private runtime were removed. Retained Databox source, platform-health, artifact, Dagster, SQLMesh, and quality gates pass independently.

Initial review found active Rufous records still describing the former shared Quack/database refresh boundary. Rufous corrected the active specifications to use validated `rufous_inputs_v1` input and separate `RUFOUS_DATABASE_PATH` state. Immutable obsolete decisions were moved to superseded history and a standalone boundary decision remains active. Databox's leftover application wording was removed.

## Evidence considered

- `.10x/evidence/2026-09-03-rufous-record-transfer.md`
- `.10x/evidence/2026-09-03-prune-rufous-from-databox.md`
- Databox `task ci`: 385 tests, 85.47% coverage, secret and generated-file checks passed.
- Rufous: 1,073 Python, SQLMesh 11/11, app 537/537 with build/typecheck, worker 71/71, npm audit zero.

## Residual risk

Production remains intentionally disabled. Remote artifact distribution remains excluded. Historical imported records retain former Databox wording but are explicitly historical or superseded, not active authority.

## Verdict

Pass.
