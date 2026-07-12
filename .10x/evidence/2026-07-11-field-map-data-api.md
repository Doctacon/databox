Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-build-field-map-data-api.md, .10x/specs/rufous-field-map.md, .10x/decisions/rufous-catalog-discovery-and-field-map.md

# Field Map data and API evidence

## Census source and usage revalidation

Retrieved 2026-07-11 from the official U.S. Census Bureau TIGERweb `State_County` service:

- Service metadata: `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer?f=pjson`
- State layer 28 metadata: `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/28?f=pjson`
- County layer 29 metadata: `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/29?f=pjson`
- State geometry query: layer 28 `/query?where=STATE%3D%2704%27&outFields=GEOID%2CNAME%2CSTATE&returnGeometry=true&outSR=4326&geometryPrecision=4&maxAllowableOffset=0.005&f=geojson`
- County geometry query: the identical bounded query against layer 29.
- Terms consulted: `https://www.census.gov/data/developers/about/terms-of-service.html` and linked `https://www.census.gov/about/policies.html`.

Layer metadata identifies both as U.S. Census Bureau January 1, 2025-vintage geometry at the 2,500,001–6,000,000 scale range. The terms permit services to search, display, analyze, retrieve, and view Census data, require protection against respondent identification, ask applications to display `This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.`, prohibit implied endorsement, and prohibit representing modified content as unmodified Census content. This artifact contains only administrative geometry/names, is explicitly recorded as derived/generalized, and the active UI specification now requires source, modification, and non-endorsement disclosure.

Only Arizona geometry was fetched: one 4,017-byte state response and one 26,903-byte 15-county response. No national geometry was downloaded or retained. Raw response SHA-256 values were:

```text
state:    7436fe18ddba795f1409fc42056b7ece6080f29d38a9cbd51799fbb17d85304e
counties: 5b3c776f9166f51a5be9aa2579d45ef6ec27358682e45ea4e1e30b182b337194
```

## Deterministic artifact transformation

The executed transformation was:

```text
python3 - <<'PY'
import json
state=json.load(open('/tmp/az_state_source.geojson'))['features']
counties=json.load(open('/tmp/az_counties_source.geojson'))['features']
features=[]
for kind, rows in [('state',state),('county',counties)]:
    for row in sorted(rows,key=lambda item:item['properties']['GEOID']):
        p=row['properties']
        assert p['STATE']=='04' and p['GEOID'].startswith('04')
        features.append({'type':'Feature','properties':{'kind':kind,'geoid':p['GEOID'],'name':p['NAME']},'geometry':row['geometry']})
with open('app/src/assets/arizona-boundaries.geojson','w') as f:
    json.dump({'type':'FeatureCollection','features':features},f,sort_keys=True,separators=(',',':'))
    f.write('\n')
PY
```

Result:

- path: `app/src/assets/arizona-boundaries.geojson`
- retained properties only: `kind`, `geoid`, `name`; geometry retained after source-side WGS84/four-decimal/0.005-degree generalization
- count: 16 features — Arizona state GEOID `04`, then all 15 Arizona counties by GEOID
- size: 30,927 bytes
- SHA-256: `e326985b9f3dd3baa9c98f5cfbd7ea310588af0e43dc00e6c2a0323a0eab163b`

`tests/test_arizona_boundary_artifact.py` pins the exact size/hash/feature inventory/fields and rejects non-Arizona GEOIDs.

## Snapshot contract and adversarial matrix

`GET /api/map-snapshot` opens DuckDB read-only and returns only exact-key safe fields. It inner-joins persisted observations to current catalog identity, requires `region_code='US-AZ'`, `is_valid IS TRUE`, `is_reviewed IS TRUE`, `is_location_private IS FALSE`, and a present positive exact count. Pydantic then requires bounded safe identity/family/location text, strict types, valid timestamps/counts/IDs, and membership in the governed Census-derived Arizona polygon. Output does not expose source flags or raw arbitrary records.

Tests prove:

- null/wrong region, invalid, unreviewed, private/privacy-null, missing count, and unknown current taxonomy are excluded;
- blank/control/malformed identities and locations, impossible count/type, missing freshness, out-of-bounds coordinates, inconsistent warning/latest metadata, extra fields, and duplicate evidence IDs fail closed;
- a public-authority row whose location name contains `(private)` remains eligible and sets `access_warning=true` without overriding privacy authority;
- 10,001 otherwise valid rows return safe 503 and are never truncated to 10,000;
- empty snapshots are coherent;
- backend and browser permit only the two exact safe 503 messages.

## Live read-only reconciliation

With socket connection forbidden, the live local endpoint returned HTTP 200 with:

```text
encounters: 1,575
unique source observation IDs: 1,575
current taxa: 152
public locations: 208
observation range: 2026-06-08T08:31:00 through 2026-07-09T01:59:00
source freshness: 2026-07-09T13:29:12.379064
access warnings: 3
warehouse SHA-256 before/after: 805d6d929988bc7b01d08e89021f39d245074d9532ae42f27e9ca063bda9551b
```

The governed count is lower than the earlier broad 1,676-row research observation because strict delivery additionally excludes seven missing exact counts and evidence without a current catalog identity. No warehouse/source refresh or write occurred.

## Verification

- Focused backend/artifact/profile-contract: 23/23 passed.
- Focused browser map contract: 17/17 passed.
- Full network-blocked Python: 701/701 passed, three snapshots, 86.63% coverage.
- Full frontend: 245/245 passed; TypeScript, production build, and bundle configuration audit passed.
- Ruff, format (153 files), MyPy (94 source files), secret scan, staging/platform generated checks, and strict MkDocs build passed.
- `git diff --check` passed and no files were staged.

## Concurrent live-writer reconciliation

A later whole-session hash check observed `87d45ece558cd248aa6efdd295798276775093a4906eeac40f8c41a9eea245bc` rather than the `805d6d…` baseline proven unchanged by the map GET itself. Read-only investigation under `.10x/tickets/done/2026-07-11-investigate-field-map-verification-warehouse-drift.md` identified one coherent personal observation created through a pre-existing loopback Uvicorn server at 18:12 local, after the unchanged map GET and outside map tests. Catalog, media, source evidence, schemas, Watches, calendar, Wishlist, and SMTP invariants remained unchanged. No restoration is appropriate because the row is legitimate local user data. See `.10x/evidence/2026-07-11-field-map-verification-warehouse-drift.md`.

## Limits

The local geometry is deliberately generalized for statewide thematic rendering, not legal parcel/border adjudication. Browser validation independently enforces strict shape, relationships, and a conservative Arizona envelope; the backend remains authoritative for exact polygon membership. MapLibre rendering and UI behavior belong to the dependent UI ticket. Independent review remains required before closure.
