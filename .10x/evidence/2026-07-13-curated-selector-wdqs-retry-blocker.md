Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Relates-To: `.10x/tickets/cancelled/2026-07-12-repair-curated-selector-source-integrity.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`

# Curated selector WDQS retry blocker

## What was observed

The user explicitly authorized retrying the remaining live phase. A fresh writer/process preflight and protected-state snapshot passed, but the bounded production-path `Trogon elegans` confirmation again failed closed at the Wikidata Query Service exact-P225 request. The selector returned typed unavailable with attempted sources limited to `wikimedia_commons`; no iNaturalist endpoint or limiter callback ran.

Because the required confirmation did not return an eligible `wikimedia_commons` result, neither the catalog nor saved-plan apply command was launched. All current photo rows and protected state remain unchanged.

## Procedure and results

### Fresh preflight

- Process inspection found no Quack, SQLMesh, Uvicorn, source-refresh, catalog-media apply/refresh, recommendation-media apply, or competing DuckDB writer.
- `lsof data/databox.duckdb` returned no handle before the snapshot and after the probe.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/curated_final_state_snapshot.py data/databox.duckdb /tmp/curated-final-pre2.json` reported:
  - catalog 706/706 valid current singleton results: 621 `inaturalist:available`, 85 `curated_photo:unavailable`;
  - planner one plan/eight recommendations/eight valid singleton photos: eight `inaturalist:available`;
  - zero planner invalid/missing photos and zero duplicates;
  - 86 protected database fingerprints and 19 external-file hashes.

### Bounded production-path confirmation

`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/curated_live_probe.py` called `select_curated_photo("Trogon elegans")` with a counting wrapper around the production `_get_json` transport and a counting iNaturalist callback. Result:

```text
status=unavailable
source=curated_photo
attempted_sources=[wikimedia_commons]
endpoints=[https://query.wikidata.org/sparql]
inat_callbacks=0
display_url=null
caveat=Wikimedia exact-taxon discovery was unavailable or malformed
```

The assertion requiring an available `wikimedia_commons` result failed. There was no iNaturalist request. This is the active specification's required stop-on-Wikimedia-failure behavior.

### No-mutation proof

- A second read-only snapshot at `/tmp/curated-final-postprobe2.json` exactly equaled `/tmp/curated-final-pre2.json`, including current photos, all 86 protected fingerprints, all photo-run values, and all 19 external hashes.
- `git diff --check` passed.
- Cached/staged diff remained empty.
- No catalog `--refresh-photos` or planner `--curated-photos` command was launched.

## What this supports

This supports that the second live attempt remained within the authorized metadata-only boundary, exercised the production selector transport, proved zero iNaturalist fallback, and preserved all database/external state when WDQS did not provide exact-P225 discovery.

## Limits and blocker

The retry did not prove live Wikimedia selection or the repaired <=1024 Commons thumbnail behavior because WDQS failed before Commons metadata discovery. The exactly-once catalog and planner re-evaluations remain unexecuted. The owning ticket cannot close until a later bounded confirmation succeeds; migration must continue to remain stopped while WDQS exact-P225 discovery is unavailable.
