Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: `.10x/tickets/done/2026-07-13-reconcile-inaturalist-photo-migration-evidence.md`, campaign-resume implementation, bounded live repair, and durable artifacts
Verdict: pass

# iNaturalist photo migration reconciliation review

## Assumptions tested

- Global validity was not being mislabeled as current-campaign ownership.
- The 82 missing checkpoints could be adopted without provider requests or requerying 624 completed identities.
- Legacy request-count reconstruction was bounded by outcomes that prove two completed request stages.
- The repair did not widen into planner apply, broad catalog enrichment, calls, model/email/refresh, or manual SQL intervention.
- Protected-state and migration claims were independently reproducible from durable sanitized artifacts.
- Full tests did not silently mutate shared operational rate state.

## Findings

No blocker or significant finding remains.

- **Campaign ownership:** Completion and dry-run inspection use strict terminal rows filtered by the authoritative run ID. The migration test proves mixed prior/current ownership resumes only the missing terminal checkpoint.
- **Bounded repair:** The exact supported `--refresh-photos` CLI path selected 82 identities and its injected transport guard observed zero provider requests. The final authoritative run owns all 706 photo rows; the 624 prior current-campaign rows retained their provider metadata.
- **Observability:** Final status is complete with target/processed=706, lookup=624, request=1248, and outcomes totaling 706: 82 identity unavailable, 622 available, two no eligible. Historical request reconstruction applies only because every recorded lookup has a terminal two-stage outcome.
- **No-op and API:** Read-only dry-run reports zero remaining work. Catalog, placeholder profile, map, plan, and browser GETs return 200 with discovery forbidden and unchanged database hash.
- **Protected state:** Durable raw artifacts include the calculation procedure, schemas, counts, commutative row digests, external hashes, run output, API validation, and an artifact checksum manifest. They contain no personal row values or secrets. All 86 protected database fingerprints and 20 non-rate-ledger external hashes match.
- **Rate ledger:** Immediate pre/post repair hashes match, proving the authorized repair did not use the limiter. The later difference was traced to two deterministic catalog API calls whose fake getter omitted no-op limiter injection. Both calls now inject it; the culprit test passes with the ledger digest unchanged. Before/after ledger digests and bounded sanitized counter metadata are recorded rather than hidden.
- **Validation:** Focused 145 and full 776 Python tests, three snapshots, 86.43% coverage, Ruff/format/MyPy, security/generated/docs/SQLMesh/source-layout, all hooks, diff, and empty staging passed.

## Verdict

Pass. The correctness campaign-ownership blocker and privacy evidence-reproducibility gap are resolved without provider traffic, broad re-enrichment, planner mutation, or unrelated state changes.

## Residual risk

Remote provider media remains outside Rufous control. Historical 1,248 request reconstruction is valid for this exact terminal outcome set and must not be generalized to provider-failure campaigns. Physical-browser, live remote-image, and assistive-technology behavior remain outside this backend/evidence repair.
