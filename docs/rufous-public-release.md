# Rufous public static release

Rufous keeps the existing data-engineering architecture. Parallel dlt ingestion
loads a local DuckDB warehouse, SQLMesh builds the modeled publication tables,
and the release exporter compiles an allowlisted projection into static files.
The static projection is a deployment artifact, not a replacement database or a
second ingestion path.

The DuckDB file, raw source tables, FastAPI routes, personal collection, watches,
plans, calendar outbox, and email settings are never deployed. Cloudflare Pages
receives only the browser application and versioned JSON under `data/`:

- `manifest.json`
- `species/{species-code}.json`
- `cells/{grid-cell}.json`
- `places/{two-character-prefix}.json`
- `attribution.json`

There are no Pages Functions, Workers, databases, storage bindings, server-side
AI calls, weather calls, geocoding calls, analytics calls, or email calls in the
Phase 1 release. Search, watch evaluation, sunrise timing, browser storage, and
`.ics` generation all run on the visitor's device.

Pull requests build fictional fixtures without production-data access or
deployment credentials (dependency installation still uses the network):

```bash
uv run python scripts/export_rufous_public.py \
  --mode synthetic --output build/rufous-public-data
uv run python scripts/audit_rufous_public.py \
  build/rufous-public-data --workflows .github/workflows --repository-root .
```

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

The `Rufous public static release` workflow builds a synthetic static preview on
pull requests. A relevant push to `main`, a manual dispatch from `main`, or the
monthly schedule may run the production build. The production job runs its own
focused tests before it can deploy. Scheduled builds compare the deployed and
newly built `data_version` values and skip an unchanged deployment. Monthly is
deliberate: the allowlisted EOD dataset is an annual release, so a six-hour
occurrence crawl would add provider load without making the showcase fresher.

Production is protected by the explicit repository variable
`RUF_PUBLIC_RELEASE_ENABLED=true`. The other repository variables are:

- `RUF_PUBLIC_URL`
- `CLOUDFLARE_PAGES_PROJECT`

The only production secrets are `CLOUDFLARE_ACCOUNT_ID` and a least-privilege
`CLOUDFLARE_API_TOKEN` with Pages-edit access and no billing permissions. There
is no eBird token, Cornell approval secret, Worker URL, Turnstile site key,
weather token, media token, or AI credential in this workflow.

The target Pages project must remain static-only. Do not add Functions, D1, KV,
R2, Queues, Durable Objects, Email, Analytics Engine, a Worker entrypoint, or a
runtime API dependency. Wrangler is pinned as a development-only dependency of
the browser project, runs from GitHub's isolated temporary directory, and deploys
only the already-audited absolute `app/dist` path.
All `/data/*` files use the same mandatory-revalidation cache policy, so a new
manifest cannot be combined with stale observation, place, species, or
attribution shards from an older release. Content-hashed browser assets remain
long-lived and immutable.

## Manual setup before enabling release

Repository code cannot create or verify the Cloudflare account boundary. Before
setting `RUF_PUBLIC_RELEASE_ENABLED=true`, an operator must:

1. Create the `rufous` Cloudflare Pages project in the existing
   `loughondata.com` account as a static, GitHub-Actions-deployed project. Do not
   configure a Functions directory or any runtime binding, and set the Pages
   production branch to `main`.
2. Point `rufous.loughondata.com` only at that Pages project and verify that
   `loughondata.com/projects/rufous/` can frame it.
3. Protect Cloudflare and GitHub with passkeys or two-factor authentication.
4. Store only the Pages-edit deployment token in GitHub; do not grant that token
   billing, Worker, storage, database, queue, email, or DNS-edit authority.
5. Keep Cloudflare's default DDoS protection enabled. Bot Fight Mode may also be
   enabled for the hostname, but Rufous has no runtime endpoint that needs a
   Turnstile widget or application-level rate limiter.
6. Verify the Pages project is on the intended plan and has no paid add-ons
   before launch and during the quarterly provider review.

This static-only setup does not require a second Cloudflare account, a payment
card, Turnstile, Worker configuration, AI binding, or weather-service account.
The code invariant prevents Rufous visitor traffic from calling a metered
Cloudflare product; it does not remove unrelated paid subscriptions or a billing
method already attached to the wider Cloudflare account. Account-wide cardless
protection is a separate operator decision.

## Required launch tests

Run these tests against the production-shaped build before enabling deployment:

- build with no Worker URL, Turnstile key, weather token, AI credential, eBird
  token, or Cornell approval setting;
- disconnect the browser from the network after the static application and
  required shards are loaded;
- verify bird/place search, grid-cell loading, local watch evaluation, the map,
  deterministic sunrise guidance, browser storage, and `.ics` download;
- inspect the built artifact for personal records, observer names, raw/private
  identifiers, forbidden licenses, direct eBird material, Functions, Worker
  code, runtime bindings, and calls to metered browser services;
- verify each visible GBIF observation has matching item-level attribution and
  the dataset-level citation is present;
- verify a pull request receives only synthetic fixtures and no production
  source or deployment credential.

Pages deployments are atomic. Roll back by selecting the previous successful
Pages deployment in Cloudflare; do not rebuild a questionable snapshot in place.
Recheck provider terms, pricing, account plan, token permissions, and published
attribution before launch and at least quarterly.

## Email remains disabled

Phase 1 creates a `METHOD:PUBLISH` calendar file entirely in the browser. It has
no attendee, organizer, RSVP, or email field, and the application collects no
email address.

Email delivery remains a separate future phase. It must not be enabled until its
account billing boundary, authentication, unsubscribe and privacy handling,
account deletion, quota exhaustion, and abuse tests pass. The downloadable
calendar file remains the always-available fallback.
