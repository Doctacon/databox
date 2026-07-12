Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-expand-catalog-summary-for-discovery.md, .10x/specs/arizona-catalog-discovery-controls.md

# Catalog summary discovery fields

## What was observed

- The modeled summary query now selects exact `mass_g` and `habitat` from `birding_agent.arizona_species_catalog`; it performs no join, parent lookup, fallback, or inference.
- FastAPI requires nullable strict finite positive mass and nullable non-empty, control-free habitat bounded to 200 characters. Browser exact-key validation enforces the same boundaries and rejects extra keys.
- API and browser fixtures carry exact values for available species and null for unavailable/hybrid taxa. Profile responses reuse summary mass/habitat while retaining their existing nested morphology/ecology facts.
- Backend attacks reject zero, negative, NaN, infinity, string mass, blank/overlong/control-containing/non-string habitat, and extra fields. Browser attacks reject the same JSON-representable forms plus direct non-finite values.
- Catalog GET remains read-only and network-free. A socket-forbidden live GET returned 706 summaries and left `data/databox.duckdb` SHA-256 unchanged at `805d6d929988bc7b01d08e89021f39d245074d9532ae42f27e9ca063bda9551b`.

## Live reconciliation

```json
{
  "summaries": 706,
  "mass_available": 600,
  "mass_null": 106,
  "habitat_available": 600,
  "habitat_null": 106,
  "hybrid_nonnull": 0,
  "invalid_mass": 0,
  "invalid_habitat": 0
}
```

The 106 null rows are the 82 hybrids plus 24 current species without an exact AVONET match. No parent inference was introduced.

## Procedure and results

- `PYTHONDONTWRITEBYTECODE=1 UV_OFFLINE=1 .venv/bin/pytest -q tests/test_bird_catalog_api.py --no-cov -p no:cacheprovider` — 20/20 passed.
- Network-forbidden live TestClient GET plus before/after hash — 706 rows; 600 exact non-null masses/habitats; zero hybrid non-null; warehouse hash unchanged.
- `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q --record-mode=none --block-network -p no:cacheprovider` — 674/674 passed, three snapshots, 86.58% coverage.
- `cd app && npm run typecheck && npm test -- --run && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — 222/222 tests passed; typecheck, build, and bundle audit passed.
- SQLMesh — 13/13 tests passed, lint passed, and prod diff was clean. Soda production contracts — 25/25 passed.
- Repository Ruff/format, MyPy for 94 source files, secret scan, seven source checks, generated staging/platform-health/docs checks, and complete privacy suites passed.
- `git diff --check` and cached-diff inspection passed; no staged files.

## Independent-review repair

The review found two fail-closed gaps: whitespace-only habitat passed the non-empty check, and summary validation did not bind mass/habitat nullability to trait availability or hybrid identity. Backend and browser now require visible non-whitespace habitat and reject either non-null discovery field when `traits_status='unavailable'` or `taxonomic_category='hybrid'`.

Exact backend attacks set mass or habitat independently on an unavailable species and on a hybrid; all four return the fixed safe 503 response. Browser attacks preserve the governed 624/82 category distribution while moving a trait-bearing row into the hybrid category, proving relationship validation rather than incidental cardinality failure. Whitespace-only habitat is attacked independently in both layers.

- Focused backend — 25/25 passed.
- Frontend — 222/222 passed with typecheck, build, and bundle audit.
- Full network-blocked Python — 679/679 passed, three snapshots, 86.59% coverage.
- Repository Ruff/format, MyPy, secrets, seven source checks, and generated drift/privacy gates passed.

## Limits

This ticket exposes modeled summary facts only. Discovery controls and presentation are separate tickets. Independent review remains required before closure.
