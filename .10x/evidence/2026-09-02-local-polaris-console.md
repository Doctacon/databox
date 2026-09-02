Status: recorded
Created: 2026-09-02
Updated: 2026-09-02
Relates-To: .10x/tickets/2026-09-02-add-local-polaris-console.md

# Local Polaris Console evidence

## What was observed

The official open-source Apache Polaris Console was built from pinned `polaris-tools` revision `36090e045b9281d8ae837e50b36018bb9913be8a`, started in the local Iceberg Compose stack, and served HTML at `http://127.0.0.1:8080/`. Polaris remained healthy on its existing localhost ports.

A browser-style CORS preflight from `http://127.0.0.1:8080` to the Polaris management API returned HTTP 200 with the configured origin, credentials, and allowed methods. The Compose process list showed PostgreSQL healthy, Polaris healthy, and the Console running.

## Procedure

1. Validated `compose.iceberg.yml` with `docker-compose --env-file .env -f compose.iceberg.yml config --quiet`.
2. Built and started `polaris-console` through the Compose stack.
3. Requested `/` and confirmed an HTML document response.
4. Requested `/config.js` and confirmed the localhost Polaris URL, realm, and principal scope without recording credentials.
5. Sent an OPTIONS request with the Console origin to the Polaris management API and inspected CORS response headers.
6. Queried the Polaris readiness endpoint and Compose process state.

## What this supports

This supports localhost-only Console availability, pinned open-source provenance, connection configuration to the existing Polaris API, valid CORS behavior, and preservation of Polaris health and ports.

## Limits

The Console login flow was not verified end-to-end. Runtime configuration rendered blank optional OAuth-token-URL and realm-header overrides, so the application depends on its documented defaults for those values. The Console is deliberately local-only and this evidence does not establish remote availability or production suitability.
