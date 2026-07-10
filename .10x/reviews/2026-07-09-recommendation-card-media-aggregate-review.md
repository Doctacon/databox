Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-add-recommendation-card-photos-and-calls.md
Verdict: pass

# Recommendation card media aggregate review

## Target

Parent plan, verification ticket, three implementation/data children, active decision/specifications, evidence, reviews, implementation, tests, and current DuckDB state for recommendation-card photos and calls.

## Findings

- Request-time enrichment begins after fixed ranking, is bounded/nonfatal/deterministic, leaves model grounding unchanged, validates exact species/geography/licenses/URLs/identifiers, and atomically persists exactly one photo and call result per recommendation.
- Finite Creative Commons rules, HTTPS canonical output, exact GBIF cache key/MD5 paths, Xeno canonical IDs, returned geography validation, bounded transport, suppressed exception context, and total object ordering pass adversarial coverage.
- Recommendation-centric API reload is network-free and read-only.
- React renders exact requested section order, no standalone media section, one lazy photo/native call or independent placeholder per card, runtime object guards, mismatch suppression, attribution retention, accessible workflow disclosure, and responsive containment.
- Backfill reuses the shared selector, limits one-time repair to exact defective v2 rows, proves rollback/duplicate/lock safety, invokes no model, and is idempotent.
- Current warehouse has 2 plans, 16 recommendations, 16 available photos, 16 available calls, zero bad cardinality/binary columns, and Queen Valley 8/8.
- SQLMesh has no production diff; Quack/source-registry checks retain independently runnable sources and one DuckDB.
- Aggregate gates passed 100 focused tests, 50 frontend tests, 2 DeepEval tests, 11 SQLMesh tests, and 258-test CI at 84.09% coverage plus strict docs, pre-commit, bundle, secret, binary, discovery, graph, and diff checks.
- Accepting the exact returned label `United States of America` is within the spec's US jurisdiction requirement because it remains paired with the `country=US` query and independent Arizona validation. No spec change is required.
- All children have pass reviews and retrospectives; no unowned defect remains.

## Verdict

Pass. Verification and parent are closure-ready.

## Residual risk

Remote GBIF cache and Xeno audio availability are temporal. Responsive behavior is DOM/CSS-tested rather than screenshot-regressed. Creative Commons versions and active hosts/paths remain intentionally finite and require reviewed changes when upstream contracts evolve.
