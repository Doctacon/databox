Status: done
Created: 2026-07-13
Updated: 2026-07-13
Parent: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`
Depends-On: `.10x/tickets/done/2026-07-13-harden-inaturalist-photo-operations.md`

# Reconcile iNaturalist photo migration campaign and evidence

## Scope

Repair the final correctness/evidence gap after the exactly-once live migration: make the latest iNaturalist-only catalog campaign own/checkpoint all 706 identities rather than reporting 82 prior-run placeholders as newly processed, and preserve the protected fingerprint inventory/digests/procedure in durable evidence storage. Run only the bounded repair needed after the operational hardening ticket passes.

## Acceptance criteria

- Campaign completion is based on rows fully validated under and owned by the authoritative campaign, not global valid-row cardinality.
- The existing latest campaign resumes exactly the 82 prior-run typed-unavailable identities without provider requests when their non-binomial/terminal status is deterministically known; it MUST NOT requery the 624 completed current-campaign identities.
- The reconciled terminal run owns 706 rows, reports processed/checkpoint=706, selector lookup count=624, actual request count from durable observability, and outcome totals that reconcile all 706 identities (including 82 identity-unavailable, 622 available, and two no-eligible unless validation proves a different exact count).
- A read-only rerun inspection reports zero targets/requests/writes; no second broad catalog apply or planner apply occurs.
- Current state remains 706 valid catalog singletons and eight valid planner singletons with zero legacy representative providers.
- The before/after/post-gate protected fingerprint inventory, exact digests, external hashes, computation procedure, and sanitized raw JSON are copied from temporary artifacts or reproducibly regenerated into `.10x/evidence/.storage/` without personal row values or secrets.
- Protected state remains unchanged except owned photo/run observability metadata.
- API/browser mixed placeholders remain HTTP 200 and GET paths remain network/write-free.
- Focused/full gates and independent correctness/privacy review pass.

## Explicit exclusions

No full provider re-enrichment, manual SQL deletion/reset, planner reapply, source/call refresh, model/email, provider expansion, or binary storage.

## Evidence expectations

Record exact repair command, target/request/outcome counts, run ownership query, zero-target inspection, durable fingerprint artifact paths/digests/procedure, protected-state comparison, gates, and independent review.

## References

- `.10x/specs/curated-inaturalist-representative-bird-photos.md`
- `.10x/evidence/2026-07-13-inaturalist-only-representative-photo-migration.md`
- `.10x/reviews/2026-07-13-inaturalist-only-final-correctness-review.md`
- `.10x/reviews/2026-07-13-inaturalist-only-final-privacy-security-source-review.md`

## Progress and notes

- 2026-07-13: Opened from final aggregate rereview findings. No repair has begun.
- 2026-07-13: Implemented authoritative campaign-owned completion/inspection and a deterministic mixed-owner zero-request regression test. Preflight showed exactly 82 missing campaign checkpoints.
- 2026-07-13: Ran the supported photo-refresh resume exactly once with provider transport forbidden. It adopted exactly 82 terminal non-queryable placeholders with zero requests and preserved 624 current-campaign results. Final run owns 706 rows with processed=706, lookup=624, request=1248, and outcomes 82 identity unavailable + 622 available + two no eligible.
- 2026-07-13: Persisted sanitized fingerprint procedure/raw artifacts/checksum manifest under `.10x/evidence/.storage/`. All 86 protected database fingerprints and 20 non-rate-ledger external hashes match. A full-test shared-ledger mutation was traced to two missing no-op test injections, repaired, and proven isolated by a narrow rerun with unchanged digest.
- 2026-07-13: Focused 145 and full 776 Python tests, three snapshots/86.43% coverage, Ruff/format/MyPy, security/generated/docs/13 SQLMesh/source-layout, all hooks, diff, and empty staging passed. Evidence: `.10x/evidence/2026-07-13-inaturalist-photo-migration-reconciliation.md`. Independent adversarial self-review: `.10x/reviews/2026-07-13-inaturalist-photo-migration-reconciliation-review.md` (pass).
- 2026-07-13 retrospective: Campaign completion must be derived from campaign-owned strict rows, never global valid cardinality. Historical request reconstruction is safe only when bounded terminal outcomes prove request-stage count. Deterministic fake transports must always inject isolated/no-op budget state; external fingerprints correctly caught the missed seam.

## Blockers

None. Acceptance criteria and review gate are satisfied.
