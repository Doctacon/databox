Status: open
Created: 2026-07-10
Updated: 2026-07-10
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/done/2026-07-10-build-my-birds-and-profile-controls.md, .10x/tickets/2026-07-10-implement-target-bird-planning.md, .10x/tickets/2026-07-10-implement-proton-bridge-alert-delivery-and-operations.md

# Verify local birding Pokédex

## Scope

Run aggregate adversarial verification across the completed catalog, personal collection, target planning, watched matching/reporting, calendar/outbox, SMTP operations, and preserved Trip Planner. Reconcile active specifications, child evidence, reviews, dependency/status graph, and retrospective learning.

## Acceptance criteria

- Full Python/frontend/SQLMesh/Soda/docs/hooks/typecheck/build suites pass with no recording or unintended warehouse/source mutation.
- Catalog remains 706/624/82 with 600 exact AVONET matches; personal, target, watch, and alert identity all use exact catalog species code without hybrid/parent guesses.
- Privacy and side-effect matrix proves private eBird rows, personal text/origins/centers, recipient/SMTP/Cloudflare/source secrets, and arbitrary model/raw payloads do not leak across API/log/trace/bundle/record boundaries.
- Replay/concurrency/crash tests prove observation transactions, target-plan atomicity, watch novelty, event UID/sequence, outbox claim/retry/unknown reconciliation, and retention behavior.
- Accessibility/direct/history/focus/responsive/empty/error behavior passes across Trip Planner, Arizona Birds, My Birds, target reports, and alert operations.
- Only explicitly authorized live test email/invitation are sent, if still needed; acceptance evidence is redacted and no inbox-rendering guarantee is claimed.
- Independent aggregate architecture, correctness, privacy/security, and UX reviews pass or every residual risk has a durable accepted owner.
- Parent plan, specs, decisions, evidence, reviews, tickets, and retrospective records agree before closure.

## Explicit exclusions

No new product behavior, broad refactor, remote deployment, accounts, social features, or unratified external integration.

## Evidence expectations

Create one aggregate evidence record and independent review records mapping every parent/spec criterion to reproducible artifacts and commands.

## Progress and notes

- 2026-07-10: Verification ticket opened after all remaining focused contracts were ratified.

## Blockers

Depends on implementation children.
