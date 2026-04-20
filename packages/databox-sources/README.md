# databox-sources

dlt ingestion sources for databox. Three upstream APIs:

- **ebird** — eBird API v2 (requires `EBIRD_API_TOKEN`)
- **noaa** — NOAA Climate Data Online v2 (requires `NOAA_API_TOKEN`)
- **usgs** — USGS Water Services NWIS (no auth)

## Test Harness

Tests live in `packages/databox-sources/tests/<source>/` and ship with recorded
VCR cassettes under `tests/<source>/cassettes/`. CI runs them offline — no
network, no API tokens required.

### Run all tests

```bash
uv run pytest packages/databox-sources
```

Flags of note:

| Flag                        | Behavior                                                   |
|-----------------------------|------------------------------------------------------------|
| `--record-mode=none`        | Default. Replay cassettes; fail on any unmatched request.  |
| `--record-mode=once`        | Record if no cassette exists, else replay.                 |
| `--record-mode=rewrite`     | Always re-record (use after upstream API changes).         |
| `--snapshot-update`         | Regenerate dlt schema snapshots (syrupy).                  |

### Re-recording cassettes

When an upstream API changes shape, re-record:

```bash
# 1. Confirm tokens are set in .env (EBIRD_API_TOKEN, NOAA_API_TOKEN)

# 2. Delete the stale cassettes for the affected source
rm -rf packages/databox-sources/tests/<source>/cassettes/

# 3. Re-record live (hits real API once)
uv run pytest packages/databox-sources/tests/<source>/ --record-mode=once

# 4. Regenerate schema snapshots if the schema intentionally changed
uv run pytest packages/databox-sources/tests/<source>/test_schema.py --snapshot-update

# 5. Verify cassettes contain no secrets
TOKEN=$(grep <TOKEN_NAME> .env | cut -d= -f2 | tr -d "\"'")
grep -r "$TOKEN" packages/databox-sources/tests/<source>/cassettes/ && echo LEAK || echo clean
```

`vcr_config` in `tests/conftest.py` redacts auth headers (`authorization`,
`x-ebirdapitoken`, `token`, `x-api-key`) and query params (`token`, `api_key`)
automatically. Response bodies are scrubbed of any known token echoes via
`_scrub_response_body`.

### What each test file covers

Every source gets three test files:

- `test_resources.py` — Invoke a single `@dlt.resource` generator and assert row
  shape (primary keys present, expected types).
- `test_schema.py` — Run `pipeline.run(source)` into in-memory DuckDB, then diff
  the inferred dlt schema against a committed snapshot. Catches column
  adds/drops/retypes.
- `test_smoke.py` — Full pipeline run through `:memory:` DuckDB; assert no
  failed jobs and row counts > 0.

### Freezing time

NOAA and USGS source functions derive their `startdate`/`enddate` from
`pendulum.now()`. Tests pin the clock via `@pytest.mark.time_machine(...)` so
cassette request URLs stay stable between recording and replay.

### Adding tests for a new source

1. Create `tests/<new_source>/` with `__init__.py`, `test_resources.py`,
   `test_schema.py`, `test_smoke.py`.
2. Copy patterns from one of the existing sources.
3. Record cassettes with `--record-mode=once`, snapshot schema with
   `--snapshot-update`.
4. Scan cassettes for any secrets that slipped past the default filters;
   extend `vcr_config` if needed.
5. Commit cassettes and snapshots alongside source code.
