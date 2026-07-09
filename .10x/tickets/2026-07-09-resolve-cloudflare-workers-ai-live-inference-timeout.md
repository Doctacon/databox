Status: open
Created: 2026-07-09
Updated: 2026-07-09
Parent: None
Depends-On: .10x/tickets/done/2026-07-09-integrate-cloudflare-ai-with-adk.md

# Resolve live Cloudflare Workers AI inference timeout

## Scope

Investigate and resolve the external live-inference blocker for the local Birding Trip Copilot. The configured account/token reaches Cloudflare and the local client derives the fixed official HTTPS route, but bounded requests to `@cf/zai-org/glm-4.7-flash` time out before any model response.

Required work:

- revalidate token status and account/model entitlement without recording credentials,
- check Cloudflare service/model availability and applicable account limits,
- retry the existing bounded `task smoke:cloudflare-ai` path,
- capture only safe response status/request identifiers when available,
- distinguish Cloudflare/account availability from any reproducible local client defect.

If investigation identifies a local implementation defect, open a separate bounded repair ticket rather than widening this operational investigation.

## Explicit exclusions

- No fallback or alternate model.
- No credential, response-body, transport-detail, or `.env` value logging.
- No deployed Worker, Wrangler runtime, or browser-side inference.
- No unbounded retries or timeouts.

## Acceptance criteria

- `task smoke:cloudflare-ai` returns one validated bounded response from exactly `@cf/zai-org/glm-4.7-flash`, or a Cloudflare support/account outcome identifies the external cause and an explicitly approved next action.
- Token/account/model checks and any request identifier are recorded without secrets.
- The client still sends credentials only to the fixed HTTPS `api.cloudflare.com` endpoint and does not select a fallback model.
- Any local defect discovered has its own executable repair owner and evidence.

## Evidence expectations

Record the exact bounded commands, date/time, safe status/result, provider status or support references, and explicit limits. Never include configured values or response bodies.

## Progress and notes

- 2026-07-09: Aggregate verification reran `task smoke:cloudflare-ai` once. It reached the configured fixed Cloudflare route but ended in the client's bounded `CloudflareTimeoutError`; no fallback was used and no credential value was printed. Earlier token verification returned HTTP 200, while prior OpenAI-compatible and native model calls also timed out.

## Blockers

External Cloudflare model response availability or account entitlement is not yet established.
