Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-build-catalog-sort-and-filters.md, .10x/specs/arizona-catalog-discovery-controls.md

# Catalog sort and filter evidence

## What was observed

- The catalog still performs one strict local `GET /api/birds`; all sorting, filtering, option generation, paging, and reset behavior is browser-local.
- Display names use common name, scientific name, then species code. Name comparison uses `Intl.Collator("en", {sensitivity:"base", numeric:true})` and species code as the deterministic total tie-break.
- Name Z–A reverses both display-name and species-code ordering. Taxonomic order is ascending with species code. Observation order is descending count then A–Z. Latest sighting is descending chronological timestamp, null last, then A–Z.
- Category, family, habitat, weight, and search predicates combine with AND. Family display uses common then scientific name. Family/habitat options are deduplicated and alphabetized by visible label after their sentinel, including unavailable labels in alphabetical position.
- Weight boundaries are exact and non-overlapping: Tiny `<20`; Small `>=20,<100`; Medium `>=100,<500`; Large `>=500,<2000`; Very large `>=2000`; unavailable matches only null.
- Every search, sort, or filter change resets page 1 and stops active audio. Page changes, navigation, and unmount retain their existing stop behavior. Reset restores empty search, Name A–Z, and all filter sentinels.
- Controls are native labeled selects/search/button, matching count remains polite live text, empty copy names search and filters, and the responsive grid collapses to one column at the existing narrow breakpoint.

## Adversarial matrix

A six-row isolated family matrix proves:

```text
A–Z: Alpha, Bravo, Charlie, Delta, Echo, Foxtrot
Z–A: Foxtrot, Echo, Delta, Charlie, Bravo, Alpha
Taxonomic: Bravo, Charlie, Alpha, Delta, Echo, Foxtrot
Most observed: Bravo, Charlie, Echo, Alpha, Delta, Foxtrot
Latest sighting: Charlie, Delta, Bravo, Alpha, Echo, Foxtrot
```

The matrix includes equal taxonomic order, equal observation count, equal timestamps, and multiple null timestamps. Masses `19.999`, `20`, `100`, `500`, `2000`, and null each match exactly one governed bucket. Combined search + species + family + habitat + Small returns only Bravo. A no-match search renders the filter-aware empty state.

## Procedure and results

- `cd app && npm test -- --run src/BirdPages.test.tsx && npm run typecheck` — 24/24 focused catalog/profile tests passed; typecheck passed.
- `cd app && npm run typecheck && npm test -- --run && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — 223/223 frontend tests passed; typecheck, build, and bundle audit passed.
- `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q --record-mode=none --block-network -p no:cacheprovider` — 679/679 passed, three snapshots, 86.59% coverage.
- Repository Ruff/format, MyPy for 94 source files, secret scan, and seven source-layout checks passed.
- `git diff --check` and cached-diff inspection passed; no staged files.

## Limits

URL-persisted controls, server-side filtering, weight sorting, migration/media filters, map behavior, and profile layout remain explicitly excluded. Independent review remains required before closure.
