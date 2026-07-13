Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: `.10x/tickets/done/2026-07-13-implement-inaturalist-only-representative-photos.md`, iNaturalist-only representative-photo implementation and tests
Verdict: pass

# iNaturalist-only representative-photo implementation review

## Assumptions tested

- Superseding Wikimedia removed its active implementation rather than merely bypassing it.
- iNaturalist remains the curated taxon shortlist, not arbitrary observations or GBIF occurrence media.
- Exact v2 identity and v1 shortlist identity cannot drift across versions.
- Available rows bind provider, taxon/photo identity, dimensions, attribution, license, and URLs consistently at persistence, API, and browser boundaries.
- Typed unavailable rows remain strict but cannot invalidate an otherwise coherent catalog.
- GET routes remain local/read-only and deterministic tests make no live provider calls.

## Findings

No blocker or significant finding remains.

- **Source elimination:** Active implementation contains no Wikimedia/Wikidata/Commons discovery endpoints, query/ranking code, host/path validators, provider union, or presentation label. Three frontend adversarial tests intentionally retain `wikimedia_commons` only to prove legacy provider rejection. Creative Commons occurrences are licensing authority strings and are not source logic.
- **Identity and selection:** The selector performs v2 exact active species-rank resolution, then v1 exact identity repetition and ordered `taxon_photos` inspection. It chooses the first eligible row and rejects ambiguity, cross-version mismatch, non-binomial identities, direct occurrence behavior, unsafe metadata, and ineligible dimensions/licenses.
- **Network/source safety:** Only governed iNaturalist v2 and exact-ID v1 endpoints are accepted. Redirects are disabled; response origin, timeout, body size, URL host/path/ID, credentials/port/query/fragment, rate, and daily budget boundaries remain.
- **Persistence/API/browser:** Available provider is exactly `inaturalist`; typed unavailable provider family remains `curated_photo` internally with no active URL. Catalog/planner resume validation now rejects superseded attempted-source provenance, forcing controlled migration rather than silently treating legacy rows as current.
- **Observed app failure:** Browser catalog validation now permits an unavailable row to retain only its exact scientific identity, while all active media fields must be null. A mixed unavailable/available 706-row catalog passes, and malformed unavailable metadata remains rejected. Read-only current-DB GET returned 200/706 rather than `invalid unavailable photo` and did not change the database hash.
- **Regression gates:** 172 focused Python tests, focused TypeScript/frontend tests, 776 full Python tests, 295 full frontend tests, build/bundle audit, Ruff/format, MyPy, secret/generated/docs/source-layout checks, SQLMesh, pre-commit, diff checks, and empty staging all passed.

## Verdict

Pass. The implementation satisfies the active iNaturalist-only specification without live migration or unrelated feature expansion. The separately owned serialized migration is now the correct next dependency.

## Residual risk

Current persisted Wikimedia-first-era rows intentionally display as placeholders until the migration ticket re-evaluates them. Remote image availability, provider schema changes, visual subject quality, physical responsive rendering, and assistive-technology behavior remain outside deterministic implementation evidence. The existing Vite MapLibre chunk advisory is unrelated and unchanged.
