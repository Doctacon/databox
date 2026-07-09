Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-implement-shared-quack-parallel-refresh.md, .10x/specs/parallel-quack-local-refresh.md

# Parallel Quack local refresh evidence

## What was observed

The local refresh now starts one Quack server over `data/databox.duckdb`, launches all six registered source jobs as concurrent Dagster client processes, records actual dlt/Quack ingest-session intervals across processes, stops the server, deduplicates raw tables, validates core raw row counts and `main._dlt*` hygiene, and only then runs native SQLMesh.

Independent source jobs retain their own server lifecycle. Their Quack client files are cleaned on both success and failure.

## Procedure and results

### Focused tests

Command:

`uv run --no-sync pytest --no-cov -q tests/test_parallel_refresh.py tests/test_quack_destinations.py tests/test_settings.py tests/test_source_registry.py`

Result: 29 passed.

Coverage includes:

- one shared server lifecycle,
- actual ingest-timeline parsing,
- rejection of non-overlapping ingest intervals,
- source failure attribution when dedupe and cleanup also fail,
- standalone client cleanup on success/failure,
- partial Quack startup cleanup,
- union metadata views and transient `main._dlt*` behavior,
- raw row-count and `main._dlt*` inspection,
- all six source schedules plus the parallel schedule in Dagster Definitions.

### Consecutive live smoke refreshes

Commands:

`task verify`

`task verify`

Results:

- `.logs/verify-20260709-115401.log` — passed.
- `.logs/verify-20260709-115426.log` — passed.

Both runs launched all six source jobs concurrently and reported all 15 pairwise actual ingest-session overlaps. Both completed native SQLMesh after ingestion validation.

Second-run core row counts:

- `raw_ebird.recent_observations=289`
- `raw_ebird.notable_observations=2055`
- `raw_ebird.hotspots=2912`
- `raw_ebird.species_list=706`
- `raw_gbif.occurrences=5`
- `raw_xeno_canto.recordings=5`
- `raw_noaa.daily_weather=27050`
- `raw_noaa.stations=1720`
- `raw_usgs.daily_values=6040`
- `raw_usgs.sites=204`
- `raw_usgs_earthquakes.events=320`

Both runs reported `main_dlt_relations=0`. The second run retained the same core counts as the first, supporting repeat-load state/idempotency behavior. `.quack-clients` was removed after refresh.

### Full CI

Command: `task ci`

Result: passed.

- Ruff check and format passed.
- mypy passed for 68 source files.
- 153 pytest tests passed.
- Coverage: 80.37%.
- Secret scan passed.
- Staging and platform-health drift checks passed.

## What this supports

This evidence supports every acceptance criterion in `.10x/specs/parallel-quack-local-refresh.md`: real source overlap through one server, independent Dagster attribution, repeat-run metadata behavior, failure propagation, cleanup, raw-schema isolation, no persistent `main._dlt*`, and SQLMesh-after-success ordering.

## Limits

- Quack remains a beta extension and the solution depends on transient union-by-name metadata views because dlt performs unqualified metadata reads through the attached catalog.
- Live validation used smoke-sized source pulls, not a full production-window refresh.
- Source subprocess startup is still included in `SOURCE_START` logging, but the overlap gate uses the separate actual ingest-session timeline artifacts.
