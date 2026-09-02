Status: open
Created: 2026-09-02
Updated: 2026-09-02
Parent: None
Depends-On: None

# Add local Polaris Console

## Scope

Add the official open-source Apache Polaris Console as a localhost-only service in the existing Iceberg Compose stack, configured to connect to the local Polaris REST API. Document its local URL and validate the Compose configuration.

## Acceptance criteria

- The official Apache Polaris Console is available through the existing local Compose stack.
- The console binds only to localhost and connects to the existing Polaris service.
- Polaris API and health ports retain their current behavior.
- Required console/API configuration is explicit and contains no committed credentials.
- Compose configuration validation passes and the console endpoint responds when started.

## Explicit exclusions

- Changing catalog, S3, ingestion, or authorization semantics.
- Exposing the console publicly.
- Adding proprietary services.

## References

- `compose.iceberg.yml`
- `https://polaris.apache.org/tools/polaris-console/`

## Evidence expectations

Record Compose validation and a successful localhost HTTP response.

## Progress and notes

- 2026-09-02: User explicitly authorized implementation with a five-minute execution bound.
- 2026-09-02: Added the localhost-only console service, pinned its source revision, enabled narrowly scoped Polaris CORS, documented the URL, and worked around the host's missing BuildKit support with a minimal local Dockerfile preserving the upstream image procedure.
- 2026-09-02: `docker-compose config --quiet` passed; the stack built and started; `http://127.0.0.1:8080/` returned the console HTML successfully.

## Blockers

None.
