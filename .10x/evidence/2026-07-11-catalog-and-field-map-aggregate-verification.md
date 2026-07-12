Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-verify-catalog-and-field-map.md, .10x/tickets/done/2026-07-11-improve-catalog-and-add-field-map.md, .10x/decisions/rufous-catalog-discovery-and-field-map.md

# Catalog discovery and Field Map aggregate verification

## Authority and graph inspected

Verification inspected the parent and aggregate tickets; the active catalog-controls, dropdown-ordering, profile-layout, and Field Map specifications; the active catalog/Field Map decision; source research; every implementation, repair, and warehouse-drift investigation child ticket/evidence record; and existing independent child reviews:

- catalog summary discovery fields — pass;
- catalog sorting and filters — pass;
- bird-profile information layout — pass;
- alphabetical dropdown ordering — pass;
- Field Map data/API — pass;
- warehouse-drift investigation — pass;
- profile-layout contract-test repair — pass;
- Rufous Field Map UI — pass.

All eleven planned/discovered direct children are under `.10x/tickets/done/`, and parent sequencing/dependencies agree with current source. Ten non-aggregate child reviews and four aggregate architecture, correctness, privacy/security/source, and UX/accessibility reviews passed.

## Live-state isolation

Before any gate, read-only inspection captured:

```json
{
  "warehouse_sha256": "87d45ece558cd248aa6efdd295798276775093a4906eeac40f8c41a9eea245bc",
  "warehouse_size": 58470400,
  "warehouse_mtime_ns": 1783818811689095812,
  "personal_observation_count": 1,
  "personal_observation_safe_sha256": "4aa0a4bfec2bbf8cea7b85d1e3d58b9b6ec7136e97e3bd6220f24730c87038c3",
  "watch_count": 0,
  "watch_cancellation_count": 0
}
```

The prior Uvicorn process implicated in the resolved concurrent-write investigation was no longer running. The exact same byte hash, size, mtime, safe personal checksum/count, Watch count, and cancellation count were observed after Python, frontend, SQLMesh, Soda, docs, static, hooks, live API, and reconciliation gates. SQLMesh state also remained `c4995254709053ebffabcc16fbfe235e1d47b93208a7a1b1a81bb77b75852a93`.

No data was deleted or normalized. Had explicit loopback use occurred, verification would have compared safe logical state rather than attributing drift to the change; no concurrent change occurred in this run.

## Full gates

### Python and privacy

```text
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' UV_OFFLINE=1 \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q --record-mode=none \
  --block-network -p no:cacheprovider
```

Result: 702/702 passed, three snapshots passed, 86.63% coverage. Socket/provider/model/source access was blocked. No delivery, refresh, apply, remediation, or live mutation command ran.

### Frontend, type, build, and bundle

The first full frontend run passed 248/249 and exposed one nondeterministic test assertion: lazy-loaded Field Map heading DOM was observable before its existing mount effect focused it. Under separately authorized `.10x/tickets/done/2026-07-11-stabilize-field-map-heading-focus-test.md`, only the test changed from an immediate focus assertion to bounded `waitFor`; production code was untouched.

After repair:

- `FieldMap.test.tsx` passed 4/4 in three consecutive runs;
- TypeScript passed;
- full frontend passed 249/249 across 15 files;
- Vite production build passed with separate lazy Field Map JS/CSS chunks;
- expanded bundle audit passed: 12 server-only names, ten configured values, and forbidden Mapbox/OSM/demo-tile/Google-font runtime hosts were absent.

### SQLMesh and Soda

- SQLMesh: 13/13 unit tests passed; lint passed; `sqlmesh diff prod` reported no changes.
- Production Soda: 25/25 contracts, 125 checks, zero failed.
- Warehouse and SQLMesh-state hashes were identical before/after these gates.

### Repository, docs, and hooks

- Ruff passed; all 153 files formatted.
- MyPy passed for 94 source files.
- Secret scan passed.
- Seven source-layout checks passed.
- Generated staging, platform-health, and 20-file dictionary checks passed.
- MkDocs strict build passed with only the existing upstream Material/MkDocs 2.0 warning and existing dictionary-nav notices.
- Pre-commit all-files passed whitespace, EOF, YAML, large-file, JSON, TOML, conflict, debug, line-ending, Ruff, and format hooks.
- `git diff --check` passed; cached diff was empty.

## Live catalog reconciliation

Read-only catalog state:

```text
rows: 706
unique species codes: 706
species: 624
hybrids: 82
mass_g populated/null: 600 / 106
habitat populated/null: 600 / 106
hybrids exposing mass or habitat: 0
```

Backend/browser strict tests reject whitespace/control habitat, malformed/non-finite/non-positive mass, extra fields, unavailable/hybrid trait contradictions, category/cardinality drift, malformed dates, media identity/license/URL drift, and duplicate taxa.

Rendered matrix proves:

- Name A–Z default, Name Z–A, taxonomic, most-observed, and latest-sighting ordering with deterministic species-code/name ties and null-last timestamps;
- exact Tiny `<20`, Small `20–<100`, Medium `100–<500`, Large `500–<2000`, Very large `>=2000`, and unavailable boundaries;
- search, category, family, habitat, and weight AND intersection;
- alphabetical category/family/habitat options, live count, empty copy, reset/page/audio lifecycle.

All 15 current native selects are mechanically inventoried. One English case-insensitive numeric comparator owns unordered visible-label sorting; sentinel-first, numeric, ordinal, chronological, navigation, tab, weight-bucket, sort-action, and recency ordering remain semantic.

## Profile reconciliation

DOM/CSS tests prove all-width one-column profile and media grids, Photo before Call, Ecology before Physical traits, normal long metadata wrapping, retained facts/actions/media/accessibility/history, and 320px protections. The separate static-test repair and its independent review preserve rather than weaken those guarantees.

## Field Map data and privacy reconciliation

With socket connection forbidden, live `GET /api/map-snapshot` returned HTTP 200 and preserved the warehouse hash:

```text
encounters: 1,575
unique source IDs: 1,575
current taxa: 152
public locations: 208
observation range: 2026-06-08T08:31 through 2026-07-09T01:59
source freshness: 2026-07-09T13:29:12.379064
access warnings: 3
all coordinates inside governed Arizona polygon: true
```

Every encounter has exactly the 14 governed fields. The strict SQL/API path inner-joins current catalog identity and requires `US-AZ`, valid, reviewed, non-private, count-present evidence. Tests fail closed on null/blank/missing/duplicate/private/invalid/unreviewed/out-of-bounds/malformed/unknown identity and 10,001-row overflow. Public-authority names containing `(private)` produce access warnings without overriding privacy authority. No personal observation, Watch, plan, media, credential, trace, source flag, or arbitrary payload field appears.

Local geometry remains exactly:

```text
features: 16 (Arizona + 15 counties)
size: 30,927 bytes
SHA-256: e326985b9f3dd3baa9c98f5cfbd7ea310588af0e43dc00e6c2a0323a0eab163b
retained properties: kind, geoid, name
non-Arizona geometry: 0
```

## Field Map UI and network reconciliation

Rendered/static/bundle tests prove:

- `/map` native route/navigation/title/focus/history and direct static fallback;
- inline local Census geometry and inline style with no tile, glyph, font, sprite, telemetry, or HTTP configuration;
- MapLibre 5.24.0 BSD-3-Clause only, lazy-loaded on `/map`; no Mapbox or deck.gl dependency;
- exact-count keyboard cluster markers and expansion zoom;
- point/list/card selection equivalence and exact profile link;
- alphabetized species/family filters and All/48-hour/7-day/30-day current-clock AND recency;
- stale-window/freshness/empty disclosure and Census source/non-endorsement notice;
- semantic complete encounter list, live count/selection, access warning, reduced motion, contrast, long labels, loading/error, and desktop/820px/320px layouts.

The captured runtime style contains local county geometry and no remote resource member. Rendered fetch audit observes only `/api/map-snapshot`; production bundle host audit rejects common remote map resources. No personal/range/route/weather behavior exists in the map component.

## Findings and limits

- No aggregate implementation, source-authority, privacy, architecture, accessibility-contract, data, docs, or static blocker was found.
- The lazy-route focus flake was isolated to test observation timing, repaired under a separate done ticket, independently reviewed, and passed repeated focused/full gates without product changes.
- Automated MapLibre interaction is verified at the typed adapter boundary in jsdom rather than a physical GPU/browser screenshot; the semantic equivalent and exact locality contracts remain fully covered.
- Aggregate independent architecture, correctness, privacy/security/source, and UX/accessibility reviews passed and are recorded under `.10x/reviews/`.
