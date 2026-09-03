Status: done
Created: 2026-09-03
Updated: 2026-09-03
Parent: None
Depends-On: .10x/tickets/done/2026-09-03-provision-disposable-polaris-catalog.md

# Forward OIDC session token to dlt

## Scope
Consume `DATABOX_AWS_SESSION_TOKEN` in runtime settings and forward it into dlt filesystem S3 credentials so temporary GitHub OIDC credentials authenticate correctly.

## Acceptance criteria
- Settings accept an optional AWS session token.
- Iceberg destination forwards the session token when present.
- Long-lived local credentials without a session token remain supported.
- Tests prove temporary and long-lived credential construction.
- No workflow trigger, S3 prefix, or production behavior changes.

## Progress and notes
- 2026-09-03: Run 33796711539 reached all source jobs but each failed in s3fs. Workflow exported the OIDC session token, while the dlt destination supplied only access key and secret key. Temporary AWS credentials require the session token.
- 2026-09-03: Added optional session-token settings and conditional dlt credential forwarding, preserving long-lived access-key behavior. Five focused tests and all pre-commit hooks pass. Hosted CI and a protected manual rerun remain required.

- 2026-09-03: Protected run 33814484913 authenticated every source job with GitHub OIDC temporary credentials, including the forwarded AWS session token. All six real publications passed.

## Blockers
None.
