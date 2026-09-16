# Stage-1 Seed-A Plan

## Status

Prepared, independently reviewed, approved once, and invoked once. Execution refused before the first successful resource creation because of the diagnosed Docker inventory defect. Its approval is consumed, and the plan is now stale after the local fix. See [failure evidence](seed-a-execution-failure.md).

## Exact private plan

- File: `.recovery/iceberg/adcd0efc4e552f76/seed-a.plan.json`
- SHA-256: `87c9d768fe6d563aad03ef6d67dfa27ebf249d3cab59bc8ad669a0a91afeff9c`
- Plan mode: `0600`
- Containing directory modes: `0700`
- Approval window: exactly six hours from generation

The file is ignored, bounded below 1 MiB, and was published without replacement. Its private contents are not copied into ledger evidence.

## Preparation behavior

The authorized `prepare` invocation performed only local settings, source, Docker runtime, and existing-image inspection. It generated the isolated 16-character run scope and wrote one Seed-A plan. It made no AWS call, did not create/start/remove a container, network, or volume, and performed no S3, Polaris, catalog, table, payload, backup, or cleanup operation.

A preliminary safety wrapper failed before invoking `prepare` because the private root did not yet exist. The root was then created mode `0700`, and the first actual invocation succeeded. A later auxiliary collision-check script used an incorrect dictionary key and stopped only that read-only wrapper; the corrected complete validation passed. Neither wrapper failure changed the plan or performed a live operation.

## Validation and review

- Exact SHA-256, path, regular-file type, modes, size bound, and ignored status: passed.
- Schema-2 Seed-A contract and current six-hour window: passed.
- Current private settings, identity digest, storage role, expected owner, and run-secret HMAC binding: passed.
- Current source/config/script/runtime and all three existing Docker image pins: passed.
- Generated 16-character Stage-1 scope and five absent Docker-resource collisions: passed.
- No raw run secret, credentials, tokens, passwords, or derived execution secrets in the plan: passed.
- Exact operation contract and prohibitions against active/canonical resources, permanent version deletion, delete-marker removal, bucket-control changes, network/volume removal, and automatic cleanup: passed.
- Independent review: approval-ready, no material blocker.

Residual trusted-host assumption: local AWS and Docker executable files are not content-hashed, although their relevant outputs and runtime/image identities are strictly validated.

## Consumed execution gate

The user explicitly approved this exact filename and SHA-256, and it was invoked once. No live resource was created. The plan must not be retried: the corrected source/runtime binding now rejects it as stale. A fresh `prepare`, review, and exact approval cycle is required.
