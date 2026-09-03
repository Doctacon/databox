Status: active
Created: 2026-09-03
Updated: 2026-09-03
Parent: None
Depends-On: .10x/tickets/2026-09-03-isolate-polaris-smoke-s3-prefix.md

# Provision disposable Polaris integration catalog

## Scope
Provision the canonical `databox_lake` catalog in the workflow's fresh disposable Polaris database before verification, backed only by the run-isolated S3 warehouse location.

## Acceptance criteria
- The workflow creates `databox_lake` after Polaris becomes healthy and before `task verify`.
- Storage location is exactly the configured run-isolated S3 prefix.
- Provisioning uses existing ephemeral Polaris credentials and the OIDC role without logging secrets.
- Structural tests cover ordering, catalog name, and isolated location.
- No production prefix or persistent catalog is mutated.

## Progress and notes
- 2026-09-03: Run 33796171237 failed preflight with `Unable to find warehouse databox_lake`; no source or S3 publication occurred. Repository settings, `.env.example`, and active architecture decision confirm underscore-form `databox_lake` is canonical.

- 2026-09-03: Added authenticated management-API provisioning after compose health and before verification. The canonical `databox_lake` catalog is bound to the exact run-isolated S3 location and configured with the OIDC role ARN; OAuth token output is masked.

## Blockers
None.
