Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: `.10x/tickets/cancelled/2026-07-12-repair-curated-selector-source-integrity.md` final live phase and `.10x/evidence/2026-07-12-curated-selector-live-provider-preflight-blocker.md`
Verdict: concerns

# Curated selector live-provider preflight review

## Findings

No deterministic implementation blocker remains.

- The planner/API/CLI injection repair is test-only at its call sites and leaves production curated transport and iNaturalist throttling defaults intact.
- The focused 136-test and full 786-test runs complete normally without live curated-provider traffic; the explicit forbidden-network assertion exercises the request-time planner path.
- Static, schema-test, hook, documentation, secret, diff, and staging gates pass.
- Read-only preflight covered current curated validation, all non-photo planner evidence, calls, personal/runtime/unrelated tables, and external files without copying personal row values into records.
- The live confirmation failed closed exactly as the active specification requires: Wikimedia transport failure did not activate iNaturalist fallback.
- No re-evaluation command or project database mutation occurred; post-probe fingerprints match preflight.

## Concern

WDQS timed out/unavailable during the required live proof, so the repaired Wikimedia-primary behavior remains unconfirmed against the current provider and the existing 621 catalog plus eight planner iNaturalist results have not been re-evaluated. Closing the ticket or launching migration without a successful Wikimedia-first confirmation would violate the ticket acceptance criteria.

## Verdict

Concerns. The safe stopping behavior and non-live repaired code pass review, but the ticket correctly remains blocked on live WDQS availability and subsequent serialized re-evaluation evidence.

## Residual risk

Public provider availability can recur independently of Rufous. A later attempt must repeat writer/process preflight and protected fingerprints, run only the bounded confirmation first, and must not reuse this attempt as proof of live Wikimedia selection.
