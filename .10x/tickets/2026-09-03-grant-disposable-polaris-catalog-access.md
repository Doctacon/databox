Status: active
Created: 2026-09-03
Updated: 2026-09-03
Parent: None
Depends-On: .10x/tickets/2026-09-03-provision-disposable-polaris-catalog.md

# Grant disposable Polaris catalog access

## Scope
Complete disposable Polaris provisioning by granting the bootstrap principal role catalog content-management access to `databox_lake` before source execution.

## Acceptance criteria
- Provisioning creates a catalog role for `databox_lake`.
- It grants `CATALOG_MANAGE_CONTENT` to that catalog role.
- It grants the catalog role to the authenticated bootstrap principal role.
- Steps occur before source execution and expose no credentials.
- Structural tests cover exact authorization sequence.

## Progress and notes
- 2026-09-03: Run 33799740982 passed AWS/S3 preflight and catalog creation, then Polaris returned 403 for every table-create request. IAM needs no further change.

- 2026-09-03: Verified the exact Polaris 1.7 contracts from tag `apache-polaris-1.7.0`: catalog-role creation, `CATALOG_MANAGE_CONTENT` grant, and assignment to bootstrap role `service_admin`. Implemented the ordered provisioning sequence with structural coverage.

## Blockers
None.
