Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: `.10x/tickets/done/2026-07-11-migrate-catalog-and-map-curated-photos.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`

# Catalog photo final live resume and verification

## What was observed

The final explicitly authorized missing-only resume completed on its one permitted launch. The current catalog now has exactly 706 valid curated photo results for 706 identities and zero missing identities. The sole photo run is `complete`, with target/processed counts 706/706, cumulative lookup count 1,473, and no safe failure. Final provider/status counts are 621 available `inaturalist` results and 85 unavailable `curated_photo` results.

The 456 identities complete at preflight are all present afterward. All 706 final identity keys are unique, and the lookup counter increased by exactly 250, equal to the exact missing set at preflight. This proves the resume did not query any previously completed current identity.

## Preflight

The repaired resume and timeout checkpoint evidence were read before execution:

- `.10x/evidence/2026-07-12-catalog-photo-resume-root-cause-and-repair.md`
- `.10x/evidence/2026-07-12-catalog-photo-live-resume-timeout-checkpoint.md`

`/tmp/catalog_photo_state_snapshot.py` produced `/tmp/catalog-photo-final-pre.json` and proved:

- catalog count 706;
- valid current curated count 456;
- missing current count 250;
- provider/status counts `inaturalist:available=373` and `curated_photo:unavailable=83`;
- run state `running`, target 706, processed 456, lookups 1,223, failure null;
- completed identity SHA-256 `07fd1edcb1b7596ed33474679ae9f60b2c5437d12563cf4d1009fed4421dab81`;
- all 86 protected table/subset fingerprints exactly matched the timeout checkpoint;
- all 19 protected external-state files exactly matched their original hashes.

`lsof data/databox.duckdb` returned no handle, and a process listing returned no Quack, SQLMesh, catalog-media, source-refresh, or parallel-refresh writer. Provider prerequisites reported the Xeno-canto key configured without exposing it. The 43 focused selector/catalog tests, focused MyPy, Ruff, format, diff, and empty-staging gates passed.

## Exact launch

Launched exactly once, without polling, restart, manual SQL/counter changes, or any second invocation:

```text
.venv/bin/python scripts/catalog_media.py --refresh-photos --batch-size 706
```

The bash/tool timeout was exactly 9,000 seconds. The command returned successfully within that window:

```json
{"available_call_count":600,"available_photo_count":621,"catalog_count":706,"complete_taxa_count":706,"lookup_count":1473,"mode":"photo_refresh","processed_taxa_count":706,"remaining_taxa_count":0,"run_id":"catalog_photo_2b8741d643ec4f97a8f566ee1a79b943","target_taxa_count":706,"unavailable_call_count":106,"unavailable_photo_count":85}
```

## Final state and protected-state proof

Post-run snapshots `/tmp/catalog-photo-final-post.json` and `/tmp/catalog-photo-final-gates-post.json` independently observed:

- 706/706 valid current curated results and zero missing;
- provider/status `inaturalist:available=621`, `curated_photo:unavailable=85`;
- completed identity SHA-256 `d931be9cf76b77ef73f347a6a5b104d0c540c5fa18ac45016b0dbbbf8e44a140`;
- run `complete/706 processed/1473 lookups/NULL failure`;
- all 456 preflight completed identities preserved;
- exactly 706 unique completed identities;
- lookup delta exactly 250, equal to the missing preflight identities;
- all 86 protected table/subset fingerprints unchanged before and after the run and after all test/build gates;
- all 19 protected external-state files unchanged;
- no DuckDB handle remained after completion.

The protected fingerprints include exact call rows plus every warehouse table except the expected-mutating curated photo result and photo-run surfaces. They prove unchanged catalog facts, observations, personal collection, Watches, calendar/outbox, refresh state/settings, planner/model state, raw sources, AVONET, SQLMesh state/models, calls, and all other protected warehouse data. External hashes prove the protected DLT and SQLMesh files did not change. The selector's governed metadata-only transport and passing no-binary tests, together with no new protected external artifact, support that no image/media binary was fetched. No model, email, routine refresh, Quack, SQLMesh apply, AVONET refresh, or catalog call refresh command ran.

Sample exact available records were read after completion (metadata only):

- `abetow`: iNaturalist photo `242995`, taxon `73041`, curated position 2, `CC BY-NC 4.0`, source `https://www.inaturalist.org/photos/242995`, 1552×1035;
- `acafly`: iNaturalist photo `225536`, taxon `16638`, curated position 1, `CC BY-NC 4.0`, source `https://www.inaturalist.org/photos/225536`, 1000×1500;
- `acowoo`: iNaturalist photo `3085`, taxon `18209`, curated position 1, `CC BY 4.0`, source `https://www.inaturalist.org/photos/3085`, 2048×1536.

## Remaining gates

- Full Python: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest` — 766 passed, three snapshots passed, 85.60% coverage.
- Static Python: `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/mypy packages/` — passed; 162 files formatted and 99 source files typed, with one existing unchecked-body informational note.
- Frontend: `npm run typecheck`, `npm test`, `npm run build` — passed; 18 files/273 tests passed and Vite built successfully. Only the existing large MapLibre chunk advisory appeared.
- Bundle audit passed: 12 configured names and 10 configured values absent.
- Secret scan, staging generator check, platform-health generator check, `git diff --check`, and empty staged-file check passed.
- Final protected snapshot after all gates still proved 706/706, zero missing, 86 protected fingerprints unchanged, 19 external files unchanged, and all 456 preflight identities preserved.

## Limits

The live provider response bodies and credentials were intentionally not retained. Fingerprints prove exact protected database equality without exposing personal rows. Metadata-only source samples prove representative persisted shape but are not a visual assessment of image content.
