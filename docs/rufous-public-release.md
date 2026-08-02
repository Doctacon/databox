# Rufous public R2-backed release

Rufous keeps the existing data-engineering architecture. Parallel dlt ingestion
loads a transient DuckDB warehouse, SQLMesh builds the modeled publication
tables, and the release exporter compiles an allowlisted projection. DuckDB is
still the merge and transformation engine; R2 replaces neither SQL execution nor
source-specific deduplication.

The current dlt sources do not use durable cursor incrementals. Rolling sources
re-fetch overlapping windows, snapshot sources replace their complete tables,
and the Quack path append-loads before DuckDB performs latest-wins deduplication.
Raw ingestion must therefore remain on the existing path until each source has a
reviewed cursor, deletion, overlap, and compaction contract. Sending the present
raw appends directly to object storage would retain duplicates and stale snapshot
rows.

For this release, “incremental” applies to publication rather than raw ingestion:
unchanged content reuses the active immutable objects, changed content creates a
new content-addressed release, and only the small pointer changes in place. The
source contracts are deliberately explicit:

| Input | Current refresh contract | R2 behavior |
| --- | --- | --- |
| GBIF eBird EOD bounded sample | Re-fetch the reviewed snapshot and deduplicate/model in DuckDB | Publish only the sanitized modeled result when its semantic hash changes |
| Arizona GNIS | Full pinned snapshot; a changed upstream file requires reviewed URL/hash updates | Publish only the derived prefix shards when their semantic hash changes |
| Browser observations and watches | Device-local, user-controlled records | Never upload |

Moving a raw source to append-only object storage later requires, in code and
tests, a durable source cursor, overlap window, stable deduplication key,
deletion/retraction behavior, late-arrival watermark, compaction policy, replay
procedure, and bounded-retention policy. Until all eight exist, DuckDB remains
the authoritative merge boundary.

The DuckDB file, raw source tables, FastAPI routes, personal collection, watches,
plans, calendar outbox, and email settings are never published. The audited
projection contains only:

- `manifest.json`
- `species/{species-code}.json`
- `cells/{grid-cell}.json`
- `places/{two-character-prefix}.json`
- `attribution.json`

Production publishes that complete projection twice:

1. A dedicated public R2 bucket receives content-addressed, immutable releases.
   The mutable `rufous-public/manifest.json` pointer is conditionally written
   only after every immutable object has been uploaded and verified.
2. Cloudflare Pages receives an independent copy under `/data`. The browser
   prefers the configured R2 release but falls back to this same-origin snapshot
   after any R2, CORS, pointer, hash, schema, or network failure.

Pages still hosts only static application assets. There are no Pages Functions,
Workers, R2 bindings, R2 SQL, Data Catalog, server-side AI calls, analytics, or
email calls. Search, planning, watch evaluation, browser persistence, and `.ics`
generation run on the visitor's device. R2 credentials exist only in the
production GitHub Actions environment; the browser receives only the reviewed
custom-domain URL.

Pull requests build fictional fixtures without production-data access or
deployment credentials (dependency installation still uses the network):

```bash
uv run python scripts/export_rufous_public.py \
  --mode synthetic --output build/rufous-public-data
uv run python scripts/audit_rufous_public.py \
  build/rufous-public-data --workflows .github/workflows --repository-root .
uv run python scripts/publish_rufous_public.py \
  --source build/rufous-public-data \
  --local-root build/rufous-r2-preview \
  --prefix rufous-public
```

The local publisher exercises the same release protocol without credentials or
network access. Production uses `uv run --package databox --extra r2 --locked`
with `--r2` and environment-only credentials. Its layout is:

```text
rufous-public/
  manifest.json                                  mutable, no-cache pointer
  releases/<release-id>/release.json             immutable control manifest
  releases/<release-id>/objects/data/...         immutable audited projection
```

The pointer records both the exporter `data_version` and byte-level release
hash, the exact public-manifest path and hash, the immutable control-manifest
hash, bounded rollback history, the source revision, and the monotonic GitHub
run/attempt that activated it. Publication checks both that sequence and the
object generation: compare-and-swap prevents a concurrent lost update, while
the monotonic guard prevents an older sequential rerun from rolling production
back. Intentional rollback remains a separate verified command.

## Licensed production source boundary

The initial public release uses bird occurrences from Cornell Lab of
Ornithology's [EOD – eBird Observation Dataset on
GBIF](https://www.gbif.org/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e),
published there under CC BY 4.0. It also uses an official USGS GNIS extract for
Arizona place search and the bundled Census-derived Arizona boundary.

This is specifically the GBIF-mediated, licensed dataset path. The production
workflow does not call the direct eBird API, require an eBird token, or publish
direct eBird downloads, checklist identifiers, hotspot records, or taxonomy
responses. Cornell's pending written permission is therefore not a gate for
this GBIF release. It remains a fail-closed gate for any future release that
would add direct eBird data or eBird hotspots under Cornell's separate [data-use
terms](https://support.ebird.org/en/support/solutions/articles/48001078113).

The production warehouse refresh is intentionally source-scoped:

```bash
uv run python scripts/load_dlt_quack.py \
  --source gbif --database data/databox.duckdb --skip-sqlmesh
bash scripts/sqlmesh_plan_rufous_public.sh
```

The release sets `DATABOX_GBIF_MAX_RECORDS=3000`. The dlt source requests only
CC BY 4.0 records marked present, reserves 300 rows for Rufous Hummingbird, and
uses the remaining 2,700-row bounded general Arizona sample for catalog breadth.
Every search stays below GBIF's restricted high-offset range. This is explicitly
a showcase sample, not a complete Arizona bird inventory or a scientific survey.
The workflow also sets `DATABOX_GBIF_PUBLIC_RELEASE=true`; without that explicit
flag, the existing local/Dagster GBIF asset keeps its general Arizona Aves search
and is not narrowed to the public EOD release.

That boundary follows GBIF's guidance that occurrence-search pages are capped at
300, high-offset searches may be restricted, and jobs running longer than about
15 minutes should use the authenticated asynchronous download service. A future
larger snapshot must replace only the transport with a citable GBIF bulk download;
it must continue feeding the same dlt → DuckDB → SQLMesh publication path.

SQLMesh builds only `rufous_public.gbif_eod_occurrence`, a publication model
whose sole warehouse dependency is `raw_gbif.occurrences`; it does not need the
private eBird, Xeno-canto, NOAA, or application models to exist.

Production also requires the official Arizona GNIS text extract and its independently
pinned SHA-256. The workflow's reviewed, committed source metadata points to USGS's
`DomesticNames_AZ_Text.zip`; CI extracts `Text/DomesticNames_AZ.txt` and verifies
both the archive and extracted-text SHA-256 values before publishing anything:

```bash
uv run python scripts/export_rufous_public.py \
  --mode production \
  --database data/databox.duckdb \
  --gnis data/DomesticNames_AZ.txt \
  --gnis-sha256 "$RUF_GNIS_SHA256" \
  --output build/rufous-public-data
```

The GNIS loader accepts official pipe-delimited, tab-delimited, or CSV headers,
including the current `state_name` field, validates the complete extracted-text
hash, and retains only coordinates inside the Arizona polygon. GNIS names are
prefix-sharded for browser-local autocomplete. No browser geocoder is needed.

Updating GNIS is intentionally a code-reviewed release change: replace the committed
official URL plus archive and text hashes together after validating a new USGS snapshot.
The monthly schedule never follows an unreviewed mutable GNIS URL.

## Fail-closed publication rules

- Only the allowlisted GBIF EOD dataset may provide production bird
  observations. GBIF observation licenses must normalize exactly to CC0 or CC
  BY; the EOD dataset is expected to normalize to CC BY 4.0.
- Every published observation requires the real GBIF dataset key, title,
  publisher, source URL, and license. Missing or malformed citation fields reject
  the record rather than substituting an identifier as human-readable credit.
- The credits view renders GBIF's full recommended dataset citation and DOI and
  explicitly identifies Rufous's Arizona filtering, field removal, day-level
  dates, coordinate rounding, generalized labels, and grid-cell grouping.
- The credits view retains GBIF's source-data accuracy notice alongside the
  source credit, license, modification description, citation, and DOI.
- Observer names, raw occurrence/checklist identifiers, local warehouse IDs,
  and direct eBird hotspot IDs are never published. Public occurrence IDs are
  derived only from the already-public generalized fields plus a duplicate
  ordinal; they never encode a raw GBIF key. Non-hotspot coordinates are
  generalized.
- Static locations outside the northeastern Arizona time-boundary ambiguity are
  labeled `America/Phoenix`. Ambiguous locations carry no guessed zone; the
  browser asks the visitor to choose Arizona or Mountain time.
- Direct eBird records and hotspots are excluded even if they happen to exist in
  a developer's local DuckDB file.
- Missing creator/provider credit, source URL, license, attribution, Arizona
  scope, or privacy status rejects an item.

The audit checks every referenced JSON file, source-policy metadata, forbidden
personal/raw fields, Pages file limits, Worker/Functions entrypoints, metered
Cloudflare bindings, known metered browser services, repository-level Wrangler
or Functions discovery paths, and workflow runners. It permits only the standard
`ubuntu-latest` GitHub-hosted runner.

Both synthetic pull-request builds and production builds run the focused
SQLMesh unit test for `rufous_public.gbif_eod_occurrence` before any release
artifact can be built or deployed.

## Deployment controls

The `Rufous public R2-backed release` workflow builds a synthetic, credentialless
preview on pull requests. A relevant push to `main`, a manual dispatch from
`main`, or the monthly schedule may run production. Monthly is deliberate: the
allowlisted EOD dataset is an annual release, so a six-hour occurrence crawl
would add provider load without making this snapshot fresher.

The production sequence is fail-closed:

1. Run dlt into a temporary DuckDB and build the public SQLMesh model.
2. Export the sanitized projection and audit every referenced field and license.
3. Build the full browser application and its independent Pages fallback; audit
   the resulting bundle before any object-store mutation.
4. Require the checked-out commit to remain the current `main` head, then dry-run
   the R2 publisher against the active pointer. This rejects an older workflow
   sequence before Pages can change.
5. Deploy the already-audited Pages directory atomically so the compatible app
   and complete same-release fallback exist first.
6. Recheck the `main` head, conditionally upload and fully read, hash, and verify
   every immutable R2 object plus its actual cache/content metadata, then
   CAS-write and verify the no-cache pointer last.

An unchanged exporter `data_version` re-verifies the active R2 release without
creating another one. Data-schema changes must remain backward compatible with
the immediately previous release because a freshly deployed app can briefly see
the prior R2 pointer. If a future contract cannot be backward compatible, use a
separately reviewed two-release migration before activating the new data pointer.

Production is protected by `RUF_PUBLIC_RELEASE_ENABLED=true`. Repository
variables are:

- `RUF_PUBLIC_URL`
- `CLOUDFLARE_PAGES_PROJECT`

The non-secret public release coordinates are reviewed directly in
`.github/workflows/rufous-public.yaml`:

- `RUFOUS_PUBLIC_DATA_URL` — exactly
  `https://rufous-data.loughondata.com/rufous-public`
- `RUFOUS_R2_BUCKET` — exactly `rufous-public-data`

Changing either coordinate therefore requires the same pull-request review and
checks as changing the publisher instead of an unreviewed settings-page edit.

Production secrets are:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN` — Pages Write only
- `RUF_R2_ACCESS_KEY_ID`
- `RUF_R2_SECRET_ACCESS_KEY` — S3 Object Read & Write for the one public-data
  bucket only

The Pages token and R2 token must be separate. Neither may grant billing, DNS,
Worker, bucket-administration, or access to another bucket. There is no eBird,
Cornell approval, AI, Turnstile, weather, media, or email credential in the
public workflow.

The Pages project remains static-only: no Functions, D1, KV, R2 binding, Queue,
Durable Object, Email, Analytics Engine, Worker entrypoint, or runtime API. R2 is
accessed only through its public custom domain for GET/HEAD and through its S3
endpoint by the production publisher.

## Cloudflare setup

Repository code intentionally does not provision account-wide Cloudflare state.
Before enabling the R2-backed release:

1. Keep `rufous.loughondata.com` attached only to the existing static Pages
   project.
2. Create a dedicated **Standard-class** R2 bucket containing only Rufous public
   releases. Never place raw or private data in this bucket.
3. Attach `rufous-data.loughondata.com` as its production custom domain and keep
   the `r2.dev` development URL disabled. See Cloudflare's [public bucket
   guidance](https://developers.cloudflare.com/r2/buckets/public-buckets/).
4. Apply [`infra/cloudflare/rufous-r2-cors.json`](https://github.com/Doctacon/databox/blob/main/infra/cloudflare/rufous-r2-cors.json).
   Only the iframe origin `https://rufous.loughondata.com` receives GET/HEAD
   access. Pull-request previews continue using same-origin fictional fixtures.
5. Add a hostname-scoped Cache Everything rule for immutable
   `/rufous-public/releases/*` objects and a separate cache-bypass rule for the
   mutable `/rufous-public/manifest.json` pointer. Reject query-string variants
   with WAF. Do not enable Cache Reserve.
6. Use one hostname-scoped WAF rule to allow only GET, HEAD, and OPTIONS and to
   block paths outside the pointer and immutable-release namespaces. Keep the
   default DDoS protection enabled. Do not enable free Bot Fight Mode solely for
   Rufous: it applies to the entire shared zone and cannot be scoped or skipped.
   Free rate limiting cannot match the hostname, so a broader path-scoped rate
   limit is optional rather than a launch gate. Smart Tiered Cache is also a
   zone-wide optional setting.
7. Retain the active release and at least three known-good releases. Cleanup is
   a separate reviewed operation; never use an object-store sync with deletion.
8. Apply an [R2 Bucket Lock](https://developers.cloudflare.com/r2/buckets/bucket-locks/)
   with a 90-day retention period to the
   `rufous-public/releases/` prefix. New release objects may be created, but an
   accidental or compromised overwrite/delete remains blocked during the
   rollback window. The mutable `rufous-public/manifest.json` pointer stays
   outside the lock.
9. Protect Cloudflare and GitHub with passkeys or two-factor authentication and
   set a low account budget alert.

### Cost statement

This architecture is designed for a very low bill, but it is no longer a
hard-zero-cost architecture. R2 Standard currently includes 10 GB-month of
storage, one million Class A operations, ten million Class B operations, and
free egress each month. Successful public reads beyond the allowance are
metered. See [R2 pricing](https://developers.cloudflare.com/r2/pricing/).
Cloudflare [budget alerts](https://developers.cloudflare.com/billing/manage/budget-alerts/)
are informational and do not stop or cap usage.

Caching, immutable URLs, WAF, and rate limiting reduce exposure but cannot
guarantee zero cost against distributed abuse. The emergency cost stop is to
block or disable the R2 custom domain; Rufous then automatically uses the
complete Pages snapshot. Recheck Cloudflare pricing, plan status, token scope,
usage, provider terms, and published attribution at least quarterly.

## Required launch tests

- Build without any Worker, AI, email, Turnstile, eBird, or Cornell credential.
- Confirm pull requests receive no production or R2 credentials and make no R2
  request.
- Reject a staged release containing personal fields, raw identifiers, direct
  eBird material, forbidden licenses, a database signature, an unreferenced
  file, or a path not listed by the application manifest.
- Verify R2 primary loading, pointer and manifest hashes, immutable shard paths,
  catalog/profile/map/planner behavior, local watches and observations, and
  `.ics` download.
- Simulate R2 timeout, CORS failure, 404, malformed pointer, bad hash, and an
  unsupported schema; every case must use one coherent Pages release rather
  than mixing R2 and Pages shards.
- Disable the R2 hostname completely and verify the full core application still
  works from Pages.
- Verify pointer activation cannot race, an interrupted upload never changes
  the pointer, a sequentially stale run cannot reactivate an older release, and
  an unchanged release still checks every active object's bytes, role, cache
  policy, and content type.

Pages rollback selects the previous Pages deployment. Data rollback verifies a
known immutable release and conditionally repoints the R2 manifest; it never
rebuilds or overwrites that release. If compatibility is uncertain, roll data
back before rolling back the application.

## Email remains disabled

Phase 1 creates a `METHOD:PUBLISH` calendar file entirely in the browser. It has
no attendee, organizer, RSVP, or email field, and the application collects no
email address.

Email delivery remains a separate future phase. It must not be enabled until its
account billing boundary, authentication, unsubscribe and privacy handling,
account deletion, quota exhaustion, and abuse tests pass. The downloadable
calendar file remains the always-available fallback.
