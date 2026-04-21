---
id: ticket:add-usgs-earthquakes-source
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T16:48:00Z
scope:
  kind: workspace
links: {}
---

# Goal

Add USGS Earthquake Hazards Program as a 4th data source — no API key required — exercising the full scaffold-polish "add-a-source" path end-to-end:
`scripts/new_source.py` → dlt source → staging SQL → Soda contract → Dagster domain → layout lint → `task verify`.

Dual purpose: (a) a useful geospatial/temporal dataset that pairs with existing bird/weather/streamflow location data, and (b) a real-world test of whether the scaffold delivers on its "under one day" fork-to-first-pipeline promise. Reflection on smoothness is a deliverable.

# Why

USGS Earthquake fits the scaffold's constraints perfectly:

- **No credentials.** Public GeoJSON endpoint. Satisfies constitution's zero-infra-default.
- **Well-documented, stable.** `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson` has been live since 2013 with a documented schema.
- **Geospatial + temporal.** Each feature has lat/lon + time + magnitude — matches existing marts' shape.
- **Analytics potential.** Cross-source joins: quake proximity to eBird hotspots, seismic effects on USGS streamflow gauges, weather station elevation shifts.
- **Small enough to land in one session.** ~30–100 rows/day in the all-day feed — trivial ingest volume.

Scaffold-polish closed with the claim "Fork-to-first-pipeline under one day." This ticket tests that claim on a real, never-before-integrated source by the person who built the scaffold. If it takes more than an afternoon, the claim needs revision.

# Source Details

- **API**: https://earthquake.usgs.gov/fdsnws/event/1/ (FDSN standard) + static summary feeds
- **Endpoint for this ticket**: `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson` (rolling 24h, updated every ~1 min)
- **Auth**: none
- **Format**: GeoJSON FeatureCollection — each feature has `id`, `properties.{mag, place, time, updated, tz, url, type, status, code}`, `geometry.coordinates = [lon, lat, depth_km]`
- **Cadence**: rolling 24h window; safe to pull once/day for the scaffold

# In Scope

- `scripts/new_source.py usgs_earthquakes` (or equivalent) to generate scaffold
- `packages/databox-sources/databox_sources/usgs_earthquakes/source.py` — dlt resource pulling `all_day.geojson`, flattening GeoJSON features to rows
- `packages/databox-sources/databox_sources/usgs_earthquakes/config.yaml` — pipeline config
- `transforms/main/models/usgs_earthquakes/staging/stg_usgs_earthquakes_events.sql` — rename/flatten to typed columns
- One mart: `transforms/main/models/usgs_earthquakes/marts/fct_daily_earthquakes.sql` — daily counts / max magnitude / locations
- `soda/contracts/usgs_earthquakes_staging/stg_usgs_earthquakes_events.yaml`
- `soda/contracts/usgs_earthquakes/fct_daily_earthquakes.yaml`
- `packages/databox/databox/orchestration/domains/usgs_earthquakes.py` — Dagster domain wiring
- `python scripts/check_source_layout.py` passes for `usgs_earthquakes`
- `task verify` completes green with the new source included

# Out of Scope

- A cross-source analytics mart (e.g. quake-near-hotspot). Leave to a follow-up so this ticket scope-closes cleanly.
- Historical backfill beyond the 24h summary feed.
- SQLMesh `dev → prod` promotion flow — `task verify` is sufficient.
- Data dictionary / docs regeneration — follow-up if the scaffold doesn't handle it automatically.

# Acceptance

- `python scripts/check_source_layout.py` shows `✓ usgs_earthquakes`.
- `task verify` logs zero STEP_FAILURE and zero Soda `did_not_pass` for the new source's contracts.
- At least one row lands in `stg_usgs_earthquakes_events` and one row in `fct_daily_earthquakes`.
- Reflection section populated in Close Notes capturing:
  - wall-clock time
  - friction points (manual steps the scaffold didn't cover)
  - documentation gaps
  - surprises
  - verdict on "under one day" claim

# Reflection Rubric

Score each on a 1–5 scale:

- **Discovery**: Did docs make it obvious what files to touch?
- **Scaffolding**: Did `new_source.py` generate enough to avoid boilerplate?
- **dlt integration**: Was writing the source module mechanical or trial-and-error?
- **SQLMesh integration**: Did staging generator handle the rename case, or manual?
- **Soda integration**: Was contract shape obvious from existing contracts?
- **Dagster integration**: Was the domain-file pattern discoverable?
- **End-to-end feedback loop**: How fast was "change one thing, see the effect"?

# Close Notes — 2026-04-21

## Outcome

End-to-end integration landed in ~30 minutes of active work (research + ticket drafting excluded). Final state:

- 5 earthquake events loaded into `raw_usgs_earthquakes.main.events` (smoke cap)
- 1 row in `databox.usgs_earthquakes.fct_daily_earthquakes` (today, 5 events, max mag 1.96)
- `check_source_layout.py` shows `4 ok · 0 skipped · 0 failing`
- `task verify` — 23 STEP_SUCCESS, 0 STEP_FAILURE, 0 Soda `did_not_pass`

## Reflection Rubric Scores

| Area | Score | Notes |
|------|-------|-------|
| Discovery | 4/5 | `CLAUDE.md` "Adding a New Data Source" section is accurate and has numbered steps. `docs/source-layout.md` is authoritative. Missed only the `settings.py` + SQLMesh-catalogs registration step (see friction #1). |
| Scaffolding | 3/5 | `new_source.py` generates 8 files cleanly. Dagster domain stub is helpful. But: stub `source.py` assumes API-key auth even in `--shape rest` (no `--no-auth` flag), and stub's "next steps" message still references `task check:layout` / `task staging:generate` which were dropped in taskfile-trim (see friction #4). |
| dlt integration | 4/5 | Copying pattern from `packages/databox-sources/databox_sources/usgs/source.py` was mechanical. GeoJSON flattening was straightforward. No trial-and-error. |
| SQLMesh integration | 5/5 | `scripts/generate_staging.py` handled the trivial-rename staging from the Soda contract automatically. Mart SQL was hand-written but ~15 lines. |
| Soda integration | 4/5 | Contract shape copied from `stg_usgs_sites.yaml`. Two things to remember: `source_table` key drives staging codegen; `_loaded_at → loaded_at` rename via `source_column` is the convention. Not obvious without reading an example. |
| Dagster integration | 4/5 | Domain file pattern is clean once `usgs.py` is open alongside. The stub generated by `new_source.py` does lay out the five concrete steps, which helped. |
| End-to-end feedback | 3/5 | `task verify` smoke takes ~1 min — fast enough. But the first run failed with a cryptic MotherDuck "database not found" error that did not point at "run CREATE DATABASE in MotherDuck first" (see friction #2). |

Mean: 3.9 / 5.

## Verdict on "Under One Day" Claim

**Claim holds, with caveats.** Pure implementation was ~30 min. With the friction points below fixed, it could be under 20 min. A forker unfamiliar with the stack would probably spend 2–3 hours — still well inside a day.

## Friction Points (Ordered by Severity)

### 1. `settings.py` + SQLMesh catalog registration is undocumented and not scaffolded

**Severity**: high. Every new source needs:
- a `raw_<source>_path` property in `DataboxSettings`
- an entry in `local_gateway` catalogs
- an entry in `motherduck_gateway` catalogs

`new_source.py` does not touch `settings.py`. `CLAUDE.md` step 1–6 does not mention it. I only discovered this because (a) I knew the codebase and (b) the Dagster domain file needed `settings.raw_usgs_earthquakes_path` and would have `AttributeError`'d.

**Fix**: extend `new_source.py` to patch `settings.py` (add property + two catalog entries). Or add it as explicit step 7 in `CLAUDE.md`.

### 2. MotherDuck cloud databases must be created manually before first load

**Severity**: high for MotherDuck backend (medium otherwise — local DuckDB auto-creates).

The MotherDuck `ATTACH` fails with "no database/share named 'raw_xxx' found" if the DB doesn't exist. The scaffold does not auto-create it, and the error is not forwarded to the user with a "run `CREATE DATABASE raw_xxx`" hint. Local DuckDB doesn't have this problem — the file is created on first write.

**Fix**: either (a) run `CREATE DATABASE IF NOT EXISTS raw_<source>` at Dagster startup when backend=motherduck, or (b) add to `docs/runbook.md` / `CLAUDE.md` a prominent "first-time setup for MotherDuck" step.

### 3. Stale references to removed Task targets

**Severity**: medium.

- `new_source.py` final message: "Run `task check:layout` and `task ci` to verify." — `task check:layout` was dropped in taskfile-trim (it's now `python scripts/check_source_layout.py`).
- Generated Dagster domain stub docstring says "run `task staging:generate`" — same issue (`python scripts/generate_staging.py`).
- Generated staging SQL header comment says "DO NOT EDIT by hand — run `task staging:generate` to regenerate." — same.

**Fix**: grep for `task staging:generate` and `task check:layout` across `scripts/`, `scripts/templates/`, and `databox.quality.staging_codegen`; replace with the real `python scripts/...` form.

### 4. `--shape rest` defaults assume API-key auth

**Severity**: low.

Scaffolded `source.py` enforces `API_KEY_<SOURCE>` env var. Three of the existing sources (USGS) and the new one use public endpoints. Had to delete that guard manually.

**Fix**: add `--no-auth` flag or a separate `--shape public-rest` template.

### 5. `.env.example` / secrets docs unchanged

**Severity**: low. Since this source needs no secrets, nothing to add. But `new_source.py` logic to optionally append to `.env.example` only makes sense when there's a token. Worth making that an explicit branch (`--no-auth` implies "don't touch .env.example").

### 6. `db:reset` taskfile target doesn't cover new sources

**Severity**: low.

`Taskfile.yaml:db:reset` deletes `data/databox.duckdb data/raw_ebird.duckdb data/raw_noaa.duckdb data/raw_usgs.duckdb` — hardcoded. Would leave `raw_usgs_earthquakes.duckdb` behind. Not caught by any lint.

**Fix**: either glob `data/raw_*.duckdb` or drive from `settings.DataboxSettings`.

### 7. Freshness threshold choice is manual

**Severity**: low.

Had to guess 36h for events staging, 25h for daily mart. No rubric in docs. Related to just-closed ticket:soda-freshness-realistic-thresholds — same underlying gap.

## What Worked Surprisingly Well

- **Staging codegen.** Write Soda contract → run one script → staging SQL exists. Removes an entire class of manual work.
- **Per-domain files.** `definitions.py` stayed small. Adding a new source is additive, not a merge-conflict risk.
- **Layout lint.** `scripts/check_source_layout.py` gave a green checkmark immediately after the last file landed. Fast, honest signal.
- **Scaffold-lint marker.** `# scaffold-lint: skip=scaffolded` let the source be committed early without breaking lint.
- **Pattern density.** Three existing sources means any question ("how do I write a Soda contract?", "what does a Dagster domain look like?") has a grep-able answer within one command.

## Fully Integrated Yes/No

**Yes for the pipeline + contracts. Partial for the overall system.** Missing to reach "fully":

- No entry in `docs/source-layout.md` example tree for `usgs_earthquakes`
- No row in `analytics.platform_health` — the flagship health mart doesn't know about earthquakes (follow-up: cross-source join, e.g. `fct_earthquake_impact_on_birding`)
- No entry in `data/` `.gitkeep` behavior for the new raw DB
- No docs page under `docs/` describing the source

Those are follow-up work, not blockers.

## Follow-up Tickets Worth Opening

1. `scaffold-settings-codegen` — teach `new_source.py` to patch `settings.py`
2. `motherduck-db-autocreate` — CREATE DATABASE IF NOT EXISTS on Dagster startup when backend=motherduck
3. `scaffold-doc-freshness` — replace stale `task check:layout` / `task staging:generate` references in templates + generated output
4. `scaffold-no-auth-flag` — optional `--no-auth` for `new_source.py --shape rest`
