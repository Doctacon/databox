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
| AVONET v7 traits | Re-load the pinned 21.5 MiB complete workbook through dlt and validate its file ID, byte size, MD5, worksheet, row count, and CC BY 4.0 provenance | Publish morphology and ecology only for exact scientific-name matches; omit geographical range fields |
| USFWS bird media | No automatic refresh; reuse the committed, audited metadata pin for the 167 selected immutable objects | Never re-fetch or re-upload an existing image during app or data deployment |
| iNaturalist bird media | No automatic refresh; reuse the committed, audited metadata pin for the 16 selected immutable objects | Contact iNaturalist only during an explicit manual media refresh for newly approved, currently unpictured species |
| Wikimedia Commons gap-fill media | One-time, offline curated metadata input for the 24 approved gap-fill species; never queried by a push, schedule, or normal deploy | Publish each reviewed content-addressed WebP once, then reuse its pinned immutable object |
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

Approved bird images use a separate shared namespace instead of being copied
inside every JSON release. All 207 catalog species have a pinned selection:
167 USFWS, 16 iNaturalist, and 24 Wikimedia Commons. They are recorded in
`config/rufous-pinned-public-media.json`. That file
contains only audited public metadata and immutable R2 URLs; it contains no
provider image URL or image bytes. Automatic app deployments and scheduled data
refreshes consume the pin; they never call USFWS, iNaturalist, or Wikimedia
Commons, prepare WebPs, or publish media objects. Species without a pinned
selection retain the neutral silhouette.

Adding an image for an unpictured species uses the manual-only `media-refresh`
release scope. It is never selected by a push or schedule. That explicit
maintenance path may hydrate the active JSON release, computes the exact set of
newly approved blank profiles, and stops before provider or deployment work when
that set is empty. When it is nonempty, the iNaturalist path contacts
iNaturalist only for that set, while the Wikimedia path loads only its committed
offline metadata. Both paths rebuild and verify the exact selected WebPs,
publish only their missing immutable objects, and activate the resulting JSON
release. Existing USFWS and iNaturalist selections are never refresh targets,
and the approved Wikimedia batch is not retrieved again after its immutable
objects are present. Image replacement requires a separate reviewed contract
and is intentionally refused. The committed pin and
approval ledger must be updated together before the manual release. Ordinary
Pages deployments are R2-only shells: they remove the checked-in synthetic data
fixture and do not hydrate the active snapshot.
If R2 is unavailable, public data features report unavailable instead of
silently falling back to fictional or stale bundled data.

DuckDB and SQLMesh select eligible records; the offline builder downloads the
reviewed USFWS, iNaturalist, or Wikimedia Commons source image, verifies that its model and HTTP media
types are allowlisted hints, independently identifies the bytes as a still JPEG,
PNG, or WebP with reviewed dimensions, strips metadata, creates a WebP no larger
than 650×650 and 1 MiB, and hashes the final bytes. The internal preparation
manifest records the provider and decoded source media type so a
metadata-versus-bytes normalization remains auditable. A public profile
references only:

```text
https://rufous-data.loughondata.com/rufous-media/v1/objects/<2hex>/<sha256>.webp
```

There is no media pointer, listing, overwrite, or browser write path. Existing
objects are verified and reused. A failed metadata snapshot, integrity check,
systemic download, decode, license check, or upload leaves the prior public JSON
release active.

Preparation is not publication selection. The committed
`config/rufous-media-visual-approvals.json` ledger must select exactly one final
WebP for every eligible species represented by the prepared manifest. Each selection
records the reviewer, review date, exact scientific name, final SHA-256, and
canonical provider source-page set, plus an explicit attestation that the pixels
show a live bird without a human or migration map. A changed derivative gets a
new hash and a new review; a known hash used with new provenance also blocks
until that provenance is reviewed. Other prepared candidates are implicit
exclusions: they need no approval, cannot block merely by remaining unreviewed,
and never enter public JSON or R2. Explicit rejections persist with a fixed
reason (`dead_bird`, `human_present`, `migration_map`, or `other`) as an audit
trail. If every current candidate for a species violates the user content
policy, the ledger instead records one human-confirmed `no_safe_image`
exclusion containing the complete species/hash/source-page candidate snapshot.
Any new or changed candidate invalidates that exclusion and forces a fresh
review. Excluded species publish no image and use the app's silhouette fallback.

The image path is deliberately bounded without silently dropping a tail of
results. A refresh fails before detail downloads if the complete USFWS snapshot
would exceed 10,000 candidate records or 10,000 unique media pages. Preparation
writes each verified derivative directly into an atomic staging tree instead of
retaining the set in memory, and permits at most 1 GiB of prepared WebP data.
Publication permits at most 5,000 new objects or 1 GiB of new bytes in one run,
and refuses any write that would take the immutable media prefix above 20,000
objects or 5 GiB. Exceeding any limit keeps the existing release active for a
reviewed cap or scope decision.

An individual source image that remains unavailable after six bounded retries
is quarantined rather than silently accepted or allowed to suppress every other
verified image. The internal preparation manifest records the complete semantic
row, public source page, image URL, and fixed rejection reason. At most 10
unique source objects may be quarantined; an eleventh is treated as a systemic
outage and aborts the atomic build. Exhausted retryable transport failures,
including an empty or prematurely truncated response body, may enter this
quarantine. Unsafe redirects, decoded formats outside JPEG, PNG, and WebP,
ambiguous or corrupt bytes, decoder failures, invalid dimensions, animation,
pixel or prepared-byte limit failures, and restricted-mark failures always
abort instead.

The reusable preparation cache is an optimization, not release authority. Each
entry is keyed by the complete semantic source row plus a fingerprint of the
preparer code and Pillow/WebP runtime. The cache manifest has its own stable
identity that excludes refresh timestamps. Invalid entries are cache misses;
unchanged valid rows remain reusable when other rows are added or removed.
Quarantined rows participate in that identity but never become cache hits, so
every later refresh retries them and automatically restores a repaired source.

Production publishes that complete projection twice:

1. A dedicated public R2 bucket receives content-addressed, immutable releases.
   The mutable `rufous-public/manifest.json` pointer is conditionally written
   only after every immutable object has been uploaded and verified.
2. Cloudflare Pages receives an independent copy under `/data`. The browser
   prefers the configured R2 release but falls back to this same-origin snapshot
   after any R2, CORS, pointer, hash, schema, or network failure.

Pages still hosts only static application assets. There are no Pages Functions,
R2 bindings, R2 SQL, Data Catalog, custom analytics runtime, or email calls.
Cloudflare's free, privacy-first Web Analytics beacon is injected at the edge;
it receives no application credential and reports through the same-origin
`/cdn-cgi/rum` endpoint. Search, planning, watch evaluation, browser
persistence, and `.ics` generation run on the visitor's device. A separate,
credential-isolated Workers Free service may optionally select allowlisted
field-strategy actions for an already completed deterministic trip plan;
browser code renders the corresponding fixed prose. It never becomes a Pages
runtime, data API, or dependency of core planning. R2 credentials exist only in
the production GitHub Actions environment; neither the browser nor the AI
Worker receives them.

Web Analytics records the current pathname, including SPA route changes. Public
target-plan paths contain a random browser-local plan identifier; the identifier
does not encode the plan contents, but downstream analytics exports must
normalize or omit it rather than retaining linkable, high-cardinality paths.
The companion `streams2r2` lab maps these routes to `/target-plans/:plan` before
publishing them to Kafka or R2.

Pull requests build fictional fixtures without production-data access or
deployment credentials (dependency installation still uses the network):

```bash
uv run python scripts/rufous_media/export_rufous_public.py \
  --mode synthetic --output build/rufous-public-data
uv run python scripts/rufous_media/audit_rufous_public.py \
  build/rufous-public-data --workflows .github/workflows --repository-root .
uv run python scripts/rufous_media/publish_rufous_public.py \
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

rufous-media/v1/objects/
  <first-two-sha>/<sha256>.webp                   shared immutable display copy
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
published there under CC BY 4.0. Bird morphology and ecology come from
[AVONET version 7](https://doi.org/10.6084/m9.figshare.16586228.v7), also
published under CC BY 4.0. The release additionally uses an official USGS GNIS
extract for Arizona place search and the bundled Census-derived Arizona
boundary.

This is specifically the GBIF-mediated, licensed dataset path. The production
workflow does not call the direct eBird API, require an eBird token, or publish
direct eBird downloads, checklist identifiers, hotspot records, or taxonomy
responses. Cornell's pending written permission is therefore not a gate for
this GBIF release. It remains a fail-closed gate for any future release that
would add direct eBird data or eBird hotspots under Cornell's separate [data-use
terms](https://support.ebird.org/en/support/solutions/articles/48001078113).

The production warehouse refresh is intentionally source-scoped:

```bash
mkdir -p data .dagster
DAGSTER_HOME="$PWD/.dagster" PYTHONPATH="$PWD" \
  uv run dg launch --target-path packages/databox --job avonet_ingest
uv run python scripts/sources/load_dlt_quack.py \
  --source gbif \
  --database data/databox.duckdb --skip-sqlmesh
bash scripts/rufous_media/sqlmesh_plan_rufous_public.sh
```

AVONET is loaded first through its independent, atomic snapshot job; it is not
passed to the parallel routine-source loader. Both commands target the same
`data/databox.duckdb` warehouse before SQLMesh builds the public projections.

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

SQLMesh builds `rufous_public.gbif_eod_occurrence` from
`raw_gbif.occurrences` and `rufous_public.avonet_species_traits` from the pinned
`raw_avonet.species_traits` snapshot. The exporter joins the two only by an
exact normalized scientific name. A missing match leaves that bird's trait
fields unavailable instead of guessing across taxonomy drift. Neither model
needs private eBird, Xeno-canto, NOAA, or application models to exist.

Media discovery is an explicit local or manually dispatched maintenance task;
it is not part of an automatic production deploy. When a reviewer deliberately
looks for a new image, the maintenance path derives exact target species from
the public model and runs the normal dlt → Quack/DuckDB path. The USFWS source calls the official
image search used by <https://www.fws.gov/search/images>, fetches canonical
`/media/<slug>` pages with bounded concurrency and retries, and records raw
metadata without deciding whether it may be published. It is an offline
snapshot input, not a browser API dependency:

USFWS's species and media-type controls are multi-select filters. Rufous sends
their values as compact JSON arrays and, for every nonempty response, requires
the returned facet count to equal the declared result total. This prevents a
silently ignored filter from turning a targeted refresh into a crawl of the
full USFWS catalog. Because the target list is derived from the reviewed public
model, this source is invoked only by the explicit maintenance script; it is not
exposed as an unconfigured Dagster job and is never invoked by a push or schedule.

```bash
uv run python scripts/rufous_media/load_rufous_usfws_media.py \
  --database data/databox.duckdb \
  --max-images-per-target 500
bash scripts/rufous_media/sqlmesh_plan_rufous_media.sh
uv run python scripts/rufous_media/prepare_rufous_media.py \
  --database-path data/databox.duckdb \
  --output-dir build/rufous-media
```

During explicit local media discovery, the fallback target list is the public
catalog minus every exact committed selection, regardless of provider. This
preserves the 167 USFWS and 16 iNaturalist selections without retrieving their
metadata or bytes again. The completed first fallback pass covered the 40
species that lacked a USFWS selection and added 16 images. The final 24 species
now have one approved, commercially reusable Wikimedia Commons image recorded
in `config/rufous-pinned-public-media.json`; they remain unpictured in the
active public release only until the explicit one-time Wikimedia media refresh
publishes those immutable objects and activates the JSON delta.
A prior USFWS `no_safe_image` exclusion does not suppress a
separately licensed candidate. The manual release path independently removes
exact active iNaturalist selections from its target set and refuses replacement.
The iNaturalist source is an offline dlt snapshot into the transient DuckDB—not a
browser request and not a replacement for the pipeline. It resolves an exact
active taxon, inspects at most 20 curated photos per target, and records the
run, every target outcome, and each eligible candidate for SQLMesh validation.

The fallback source accepts only an exact positive iNaturalist photo identity,
an exact `https://www.inaturalist.org/photos/<photo-id>` source page, and the
matching original object under
`https://inaturalist-open-data.s3.amazonaws.com/photos/<photo-id>/`. Its license
allowlist is intentionally narrower than USFWS: CC0 1.0, CC BY 4.0, or CC BY-SA
4.0 only. NC, ND, older versions, all-rights-reserved, a bare Public Domain
label, missing attribution, or mismatched page/object identities fail closed.
Discovering a candidate does not publish it.

The Wikimedia gap fill is deliberately a one-time offline input rather than a
new recurring scraper. Each of its 24 rows records one exact Commons `File:`
page, one exact `upload.wikimedia.org` image object, creator, commercial-use
license, source dimensions, and the matching production GBIF species identity.
The loader has no network client and transactionally replaces only
`rufous_public.wikimedia_commercial_image` in a transient DuckDB. Normal deploys
never execute it or contact Wikimedia:

```bash
uv run python scripts/rufous_media/load_rufous_wikimedia_media.py \
  --database data/databox.duckdb \
  --input config/rufous-wikimedia-public-media.json
uv run python scripts/rufous_media/prepare_rufous_media.py \
  --database-path data/databox.duckdb \
  --output-dir build/rufous-wikimedia-media \
  --provider wikimedia
```

The resulting WebPs pass through the same local human review, committed
selection ledger, additive R2 publication, and pinned-manifest gates as every
other image. No automated job may infer an approval from the curated metadata.

That preparation remains usable for a local refresh even when nothing is
selected. To produce a deterministic list without granting a selection:

```bash
uv run python scripts/rufous_media/verify_rufous_media_approvals.py \
  --manifest build/rufous-media/manifest.json \
  --approvals config/rufous-media-visual-approvals.json \
  --write-review-candidates build/rufous-media/review-candidates.json
```

The command intentionally exits nonzero until every represented species has
one selection. A human chooses one suitable image per species at full useful
resolution. A selection attests that it depicts a live bird, contains no human,
and is not a migration map. Wrong birds, dead birds, people, maps, restricted
marks, logos, seals, stamp imagery, and other unsuitable candidates can be
recorded as explicit rejections. No refresh or script bulk-selects pixels.

The committed ledger uses canonical, key-sorted JSON. One human selection
has this shape (the hash and provenance must come from the reviewed candidate):

```json
{
  "mode": "rufous-media-human-species-selections",
  "rejections": [],
  "review_policy": "one-live-bird-image-per-species-v1",
  "schema_version": 2,
  "selections": [
    {
      "decision": "selected",
      "reason": "live_bird_without_human_or_migration_map",
      "reviewed_at": "2026-08-03",
      "reviewed_by": "Human reviewer name",
      "scientific_name": "Selasphorus rufus",
      "sha256": "<64 lowercase hexadecimal characters>",
      "source_page_urls": ["https://www.fws.gov/media/reviewed-page-slug"]
    }
  ],
  "species_exclusions": []
}
```

For the browser-based review app, build a separate marked bundle and serve it
only on loopback:

```bash
uv run python scripts/rufous_media/build_rufous_media_review.py \
  --source build/rufous-media \
  --approvals config/rufous-media-visual-approvals.json \
  --recommendations /path/to/curated-local-recommendations.json \
  --output /tmp/rufous-media-LOCAL-REVIEW-ONLY \
  --only-missing-species \
  --local-review-only
python -m http.server 4174 --bind 127.0.0.1 \
  --directory /tmp/rufous-media-LOCAL-REVIEW-ONLY
```

`--only-missing-species` removes every species with a current committed
selection from this local gallery. It is the normal fallback-review mode: all
current selections stay untouched while the reviewer sees only newly prepared
candidates for any future gaps. Omit the flag only for a separate,
deliberate audit; the production add-only release contract still refuses image
replacement. Neither mode edits the ledger.

When `--recommendations` is omitted, the gallery opens on one deterministic
recommendation per species, ranked by the prepared hero score and then stable
source/media identifiers, without selecting or approving it. A visually
curated recommendation file may replace that starting set. The file is
canonical JSON, is bound to the exact prepared-manifest SHA-256, contains the
exact scientific name, final WebP SHA-256, and complete current source-page set,
and covers every represented species with either exactly one current
recommendation or an explicit `no_safe_image` entry containing every current
candidate. Duplicate, missing, stale, or provenance-mismatched coverage fails closed.
This local input only changes which cards appear first; it cannot create a
production selection. Every alternate remains available through the
`All alternatives` view, and searching automatically searches alternatives as
well. Rejecting a recommendation opens that species' alternatives. Choosing an
image automatically replaces any prior local selection for that species.
Rejections require a reason. The progress line counts species with exactly one
selection rather than requiring a decision on every candidate. Exporting
browser-local decisions still does not select anything for production. The
builder never edits the ledger, requires the explicit `--local-review-only`
acknowledgement, and stamps every bundle with
`RUF_LOCAL_MEDIA_REVIEW_ONLY_DO_NOT_DEPLOY`.

```json
{
  "excluded_species": [],
  "mode": "rufous-media-local-review-recommendations",
  "recommendations": [
    {
      "scientific_name": "Selasphorus rufus",
      "sha256": "<64 lowercase hexadecimal characters>",
      "source_page_urls": ["https://www.fws.gov/media/reviewed-page-slug"]
    }
  ],
  "schema_version": 1,
  "source_manifest_sha256": "<prepared manifest SHA-256>"
}
```

Convert an exported browser file into a separate canonical ledger, with the
human reviewer's identity added explicitly:

```bash
uv run python scripts/rufous_media/verify_rufous_media_approvals.py \
  --manifest build/rufous-wikimedia-media/manifest.json \
  --approvals config/rufous-media-visual-approvals.json \
  --import-local-decisions /path/to/rufous-local-review-decisions-NOT-YET-COMMITTED.json \
  --write-updated-ledger /tmp/rufous-media-visual-decisions.json \
  --reviewed-by "Human reviewer name" \
  --provider wikimedia
```

The import is bound to the exact prepared-manifest SHA-256 and exact candidate
provenance. It writes a separate file and then runs the production gate; a
partial review remains safely non-publishable. Review the diff before replacing
the committed ledger. The production release audit rejects the local marker if
any review bundle is copied into a deployable site.

For a reviewed additive provider batch, compose a separate candidate for the
provider-free immutable pin. This command requires the exact updated human
ledger, retains every existing pinned item unchanged, selects only the reviewed
provider hashes, normalizes ranking out of the pin, and omits upstream image
object URLs:

```bash
uv run python scripts/rufous_media/compose_rufous_media_pin.py \
  --base config/rufous-pinned-public-media.json \
  --prepared build/rufous-wikimedia-media/manifest.json \
  --approvals /tmp/rufous-media-visual-decisions.json \
  --provider wikimedia \
  --output /tmp/rufous-pinned-public-media.json
```

Review both diffs before replacing either committed file. A later explicit
`media-refresh` dispatch chooses `media_provider: wikimedia`; it revalidates the
active production catalog, prepares only that selected batch, proves those
exact public projections are already in the committed pin, publishes the
content-addressed objects, and activates the JSON delta last. Ordinary pushes,
full releases, and scheduled releases continue to use only the committed pin
and never contact Wikimedia.

Run the same command without `--write-review-candidates` to verify the finished
ledger. Manual media publication and every production export both require that
verification. The automatic workflow verifies the committed pinned manifest;
it does not rediscover candidates. A newly discovered or changed image therefore
cannot publish itself and cannot affect an unrelated app or data deployment.

`rufous_public.usfws_commercial_image` selects only the latest complete
snapshot. It requires an exact scientific-name tag, canonical USFWS media page,
safe USFWS image URL, credible creator, usable dimensions and MIME type, and an
explicitly commercial-use-compatible license. The preparation step independently
repeats those gates before downloading bytes.

`rufous_public.inaturalist_commercial_image` independently selects only the
latest complete fallback snapshot and repeats the exact taxon, photo-ID,
original-object, creator, dimensions, MIME, and strict 4.0-or-CC0 license gates.
The common preparer tags each row with its reviewed provider before downloading
and preserves provider-specific source attribution in the internal manifest.
It creates the same bounded, content-addressed WebP contract for both sources;
the provider never changes the public object-store permissions.

Production also requires the official Arizona GNIS text extract and its independently
pinned SHA-256. The workflow's reviewed, committed source metadata points to USGS's
`DomesticNames_AZ_Text.zip`; CI extracts `Text/DomesticNames_AZ.txt` and verifies
both the archive and extracted-text SHA-256 values before publishing anything:

```bash
uv run python scripts/rufous_media/export_rufous_public.py \
  --mode production \
  --database data/databox.duckdb \
  --gnis data/DomesticNames_AZ.txt \
  --gnis-sha256 "$RUF_GNIS_SHA256" \
  --media-manifest config/rufous-pinned-public-media.json \
  --media-approvals config/rufous-media-visual-approvals.json \
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
- AVONET traits must retain the pinned version 7 DOI, source file ID and MD5,
  and CC BY 4.0 license. Only sample, morphology, and ecology fields on the
  explicit public allowlist may cross the exporter; AVONET geographical range
  fields are excluded.
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
- USFWS media accepts only exact Public Domain, CC0, CC BY, or CC BY-SA terms.
  NC, ND, all-rights-reserved, missing, malformed, or ambiguous terms are
  rejected. Public Domain links to the USFWS notices page; Creative Commons
  terms link to their canonical license page.
- iNaturalist fallback media accepts only CC0 1.0, CC BY 4.0, or CC BY-SA 4.0.
  NC, ND, older Creative Commons versions, all-rights-reserved, missing,
  malformed, ambiguous, and bare Public Domain labels are rejected. The
  canonical photo page and original-object URL must contain the same positive
  photo ID.
- Wikimedia Commons media accepts only exact per-file Public Domain, CC0,
  CC BY, or CC BY-SA terms. Each credit links to the authoritative Commons
  `File:` page; NC, ND, all-rights-reserved, missing, or malformed terms fail
  closed. Rufous records that its display copy was resized, re-encoded, and
  stripped of metadata.
- USFWS logos and seals, Federal and Junior Duck Stamp imagery, Wildlife and
  Sport Fish Restoration symbols, and Blue Goose refuge marks are excluded
  under the [USFWS notices](https://www.fws.gov/notices) and
  [Duck Stamp licensing guidance](https://www.fws.gov/service/license-duck-stamps-or-junior-duck-stamp-imagery),
  even when the surrounding record otherwise has an accepted license. This
  fail-closed metadata gate cannot identify an unlabeled restricted mark
  embedded only in image pixels. Production therefore requires a full-pixel
  human review of the one selected hash for each represented species, recorded
  in the committed selection ledger. Every other prepared candidate is excluded.
- Every photo requires exact scientific identity, credible creator credit, a
  canonical source page for its reviewed provider, alt text, dimensions, MIME
  type, derivative hash, and immutable public URL. The upstream image URL and
  internal ranking score never enter browser JSON.
- Production must contain a selected Rufous Hummingbird photo. Species without
  an eligible image retain the built-in silhouette and all non-media behavior.
- Missing creator/provider credit, source URL, license, attribution, Arizona
  scope, or privacy status rejects an item.

The audit checks every referenced JSON file, source-policy metadata, forbidden
personal/raw fields, Pages file limits, unreviewed Worker/Functions entrypoints,
metered Cloudflare bindings, known metered browser services, repository-level
Wrangler or Functions discovery paths, and workflow runners. It permits only
the standard GitHub-hosted Ubuntu runners. The sole exception is the reviewed
`workers/rufous-ai` project: it must use the exact custom domain, disable
`workers.dev` and previews, and declare only AI and rate-limit bindings.

Synthetic pull-request builds continue to test the provider adapters and media
models with credentialless fixtures. Automatic production builds run the GBIF
publication model and verify the committed media pin against the human approval
ledger; they do not execute a live media source or the offline Wikimedia loader.

## Deployment controls

The `Rufous public R2-backed release` workflow builds a synthetic, credentialless
preview on pull requests. A relevant push to `main`, a manual dispatch from
`main`, or the monthly schedule may run production. Monthly is deliberate: the
allowlisted EOD dataset is an annual release, so a six-hour occurrence crawl
would add provider load without making this snapshot fresher.

The automatic production sequence is fail-closed:

1. Run the licensed GBIF occurrence snapshot and pinned AVONET v7 workbook in
   parallel through dlt and DuckDB, build both public SQLMesh models, and verify
   the pinned GNIS archive.
2. Verify `config/rufous-pinned-public-media.json` against every committed human
   selection. All 207 selected hashes, species identities, source pages,
   licenses, credits, and immutable R2 URLs must match exactly.
3. Export the sanitized JSON projection and refuse to continue if the refreshed
   catalog would drop even one pinned approved media species.
4. Build the browser application, delete the bundled synthetic `/data` fixture,
   and audit the resulting R2-only shell independently from the generated data.
5. Require the checked-out commit to remain the current `main` head and preflight
   the atomic JSON publisher. No automatic step calls a media provider, prepares
   an image, lists the media namespace, or publishes a media object.
6. Deploy the shell on non-scheduled releases. Scheduled data-only refreshes do
   not redeploy Pages.
7. Recheck the `main` head, conditionally upload and verify the immutable JSON
   release, then CAS-write and verify the no-cache pointer last.

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
Cornell approval, AI secret, Turnstile secret, weather, media, or email
credential in the public workflow. The public Turnstile site key is a GitHub
variable, not a credential.

The Pages project remains static-only: no Functions, D1, KV, R2 binding, Queue,
Durable Object, Email, Analytics Engine, Worker entrypoint, or runtime API. The
optional AI Worker is deployed from its separate directory and workflow with a
separate token. R2 is accessed only through its public custom domain for
GET/HEAD and through its S3 endpoint by the production publisher.

The static Pages Content Security Policy permits images only from the Pages
origin, `data:`/`blob:` browser-local sources, and the exact
`https://rufous-data.loughondata.com` media origin. `media-src` permits only the
Pages origin and that same Rufous origin. `connect-src` additionally permits
only the exact `https://rufous-ai.loughondata.com` Worker and OpenFreeMap
origins. Turnstile is permitted only from
`https://challenges.cloudflare.com` in `script-src` and `frame-src`. The
edge-injected Web Analytics beacon is permitted only from
`https://static.cloudflareinsights.com` in `script-src`; its proxied-site
delivery remains same-origin. Broad `https:`, wildcard `workers.dev`, and
preview origins are rejected by the release audit.

### Optional Workers AI Free augmentation

The `Rufous Workers AI Free augmentation` workflow is separate from the Pages
and R2 workflow. Pull requests run its tests without secrets. A current `main`
revision can deploy only when the operator has set both exact manual gates:

- `RUF_AI_RELEASE_ENABLED=true`
- `RUF_AI_WORKERS_PLAN=free`

The second value attests that the dashboard was checked and still reports
Workers Free; it is not inferred from R2 billing and is not a substitute for a
quarterly plan/pricing review. `RUF_AI_ACCOUNT_ID` and the public
`RUF_AI_TURNSTILE_SITE_KEY` are repository variables. The workflow's only
secret is `RUF_AI_WORKER_API_TOKEN`. Its achievable Cloudflare scope is Workers
Scripts Edit for the account plus Workers Routes Edit for the
`loughondata.com` zone; repository policy limits its use to `rufous-ai`. It
never receives the Pages token, R2 S3 credentials, billing access, Turnstile
permission, or the Turnstile secret. The latter is provisioned directly on the
Worker.

Production accepts only `https://rufous.loughondata.com`, the exact Turnstile
hostname, and the action `trip_plan_enrich`. Previews remain disabled. The
Worker validates a fresh single-use token, rate-limits the request, and makes at
most one bounded model call without a retry. The model returns only allowlisted
field-strategy action IDs; fixed browser code renders the corresponding text.

Workers AI quota, Worker request-limit, timeout, validation, and unavailable
responses all retain the completed deterministic browser plan. Quota
exhaustion is intentionally a loss of optional enhancement, not a reason to
enable Workers Paid. See the
[`infra/cloudflare/rufous-ai-free.md`](https://github.com/Doctacon/databox/blob/main/infra/cloudflare/rufous-ai-free.md)
runbook for the exact account setup, emergency stop, and quarterly checklist.

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
   `/rufous-public/releases/*` and `/rufous-media/v1/objects/*` objects and a
   separate cache-bypass rule for the
   mutable `/rufous-public/manifest.json` pointer. Reject query-string variants
   with WAF. Do not enable Cache Reserve.
6. Use one hostname-scoped WAF rule to allow only GET, HEAD, and OPTIONS and to
   block paths outside the pointer, immutable-release, and immutable-media
   namespaces. Keep the
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
   Apply the same or a longer retention lock to `rufous-media/v1/objects/`;
   content-addressed media is never intentionally overwritten.
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

The optional AI path has a different boundary: while the account remains on
Workers Free, its daily Workers AI and Worker request allowances fail closed
rather than becoming paid overages. The manual plan gate and isolated token
protect that boundary. They do not cap the separately metered R2 product.

Caching, immutable URLs, WAF, and rate limiting reduce exposure but cannot
guarantee zero cost against distributed abuse. The emergency cost stop is to
block or disable the R2 custom domain; Rufous then automatically uses the
complete Pages snapshot. Recheck Cloudflare pricing, plan status, token scope,
usage, provider terms, and published attribution at least quarterly.

The repository-enforced 5 GiB immutable-media ceiling and 1 GiB per-run upload
ceiling leave storage headroom and stop unbounded scheduled accumulation. They
do not cap cached or uncached public read operations, so they do not restore a
hard-zero-cost guarantee.

## Required launch tests

- Build pull requests without any production Worker, AI, email, Turnstile
  secret, eBird, or Cornell credential. Leave public AI browser variables empty
  and verify the deterministic planner remains complete.
- Confirm pull requests receive no production or R2 credentials and make no R2
  request.
- Reject a staged release containing personal fields, raw identifiers, direct
  eBird material, forbidden licenses, a database signature, an unreferenced
  file, or a path not listed by the application manifest.
- Verify R2 primary loading, pointer and manifest hashes, immutable shard and
  media paths, catalog heroes, gallery pagination/credits/failure states,
  catalog/profile/map/planner behavior, local watches and observations, and
  `.ics` download.
- Simulate R2 timeout, CORS failure, 404, malformed pointer, bad hash, and an
  unsupported schema; every case must use one coherent Pages release rather
  than mixing R2 and Pages shards.
- Disable the R2 hostname completely and verify the full core application still
  works from Pages.
- Exercise invalid, expired, and reused Turnstile tokens, the wrong hostname or
  action, rate limiting, model timeout, Workers AI quota exhaustion, Worker
  request-limit exhaustion, and a completely disabled AI custom domain. Every
  case must retain the deterministic plan and its calendar download.
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
