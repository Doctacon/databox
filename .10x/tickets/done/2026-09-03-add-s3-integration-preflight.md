Status: done
Created: 2026-09-03
Updated: 2026-09-03
Parent: None
Depends-On: .10x/tickets/done/2026-09-03-forward-oidc-session-token-to-dlt.md

# Add S3 integration preflight

## Scope
Add direct read-only AWS identity and isolated-prefix checks before parallel source launch so integration failures report the exact AWS boundary rather than an interleaved truncated source traceback.

## Acceptance criteria
- Workflow calls STS identity and lists at most one object under the isolated prefix before source jobs.
- No write or production prefix operation is introduced.
- Structural workflow test covers ordering and arguments.

## Progress and notes
- 2026-09-03: dlt credential schema confirms `aws_session_token` is valid and current main forwards it. Run 33798027704 still failed during each source's first S3 listing, but parallel tailing omitted the AWS exception.
- 2026-09-03: Added a read-only STS identity and isolated-prefix S3 listing preflight before source verification, with structural coverage for its exact commands and ordering.

- 2026-09-03: Protected run 33814484913 passed STS identity and isolated-prefix S3 preflight in each matrix job before source publication.

## Blockers
None.
