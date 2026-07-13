Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`, `.10x/tickets/done/2026-07-11-upgrade-representative-bird-photos.md`
Verdict: pass

# iNaturalist-only representative-photo parent closure review

## Target and authority

Reviewed the active decision `.10x/decisions/curated-inaturalist-only-representative-photos.md`, endpoint decision `.10x/decisions/inaturalist-curated-photo-api-split.md`, active specification `.10x/specs/curated-inaturalist-representative-bird-photos.md`, parent/aggregate tickets, all done implementation/migration/repair children, aggregate and child evidence, durable fingerprint artifacts, and final multidisciplinary reviews.

The superseded Wikimedia decision/spec and cancelled WDQS repair remain history, not active authority.

## Aggregate acceptance mapping

1. **All active-spec scenarios:** all ten scenarios map to named selector, persistence, API, frontend, interruption/retry, GET-purity, and Field Map tests in `.10x/evidence/2026-07-13-inaturalist-only-representative-photo-aggregate-verification.md`; reconciliation and hardening add final operational proof.
2. **Complete gates:** final evidence records 776 Python tests/three snapshots, 295 frontend tests, strict TypeScript, production build/bundle audit, Ruff/format/MyPy, secret/generated/docs/source-layout checks, 13 SQLMesh tests, all hooks, diff check, and empty staging.
3. **Network limits:** deterministic tests use injected/forbidden transports. Live activity was limited to explicitly authorized metadata-only migration; reconciliation adopted 82 terminal placeholders with zero requests. No binary was requested or stored.
4. **Surface coherence:** catalog/profile/Field Map/new/saved planner activate only strict iNaturalist results or typed placeholders. Current state is 706 catalog singletons (622 available, 84 placeholders) and eight saved-plan singletons, with zero legacy representative providers. Mixed-placeholder GETs return 200 without discovery or writes.
5. **Prohibited side effects:** command paths, counters, run records, and protected fingerprints support zero model, email, routine source/catalog-fact/AVONET/call refresh, recommendation regeneration, or binary persistence. Saved-plan migration inserted zero calls.
6. **Protected state:** 86 protected database fingerprints and 20 non-rate-ledger external hashes match. The sanitized procedure and raw artifacts are durable under `.10x/evidence/.storage/`; the checksum manifest passes. Owned rate-state behavior is bounded and test isolation was repaired.
7. **Independent reviews:** architecture, correctness, privacy/security/source, and UX/accessibility all pass. Earlier fail findings are resolved by done repair tickets and final rerun evidence.
8. **Record graph and retrospective:** active spec/decisions agree with current behavior; all dependencies are done; superseded/cancelled records are terminal; aggregate evidence includes final closure results; reusable operational learning is preserved in `.10x/knowledge/curated-photo-operation-invariants.md`.

## Final observed state

- Authoritative catalog run: complete; target/processed 706; logical lookups 624; actual requests 1,248; all 706 rows owned.
- Outcomes: 82 identity unavailable + 622 available + two no eligible = 706.
- Planner: eight valid available iNaturalist singletons; completion inspection zero targets/requests.
- Legacy representative providers: zero.
- API/browser: catalog, placeholder profile, Field Map, saved plan, and browser routes return 200 with provider discovery forbidden and database hash unchanged.
- Durable artifact manifest: all entries pass after supplemental logs were renamed to repository-visible `.txt` files.

## Findings and verdict

No blocker, significant, minor, or graph-coherence finding remains. **Pass.** The aggregate verification and parent plan are supported for closure.

## Residual limits and no-action rationale

Remote provider content/schema availability, physical responsive rendering, live remote-image quality, and specific screen-reader behavior remain outside deterministic evidence. These are recorded limits, not unresolved defects: metadata-only storage deliberately accepts remote mutability, current acceptance does not require a physical-browser/AT certification pass, and no observed defect remains. Local rate coordination assumes one shared filesystem, matching Rufous's current local-only deployment. No follow-up ticket is warranted absent a new deployment model, explicit manual-verification requirement, or observed defect.
