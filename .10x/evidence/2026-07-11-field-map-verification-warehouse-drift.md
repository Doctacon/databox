Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-investigate-field-map-verification-warehouse-drift.md, .10x/tickets/done/2026-07-11-build-field-map-data-api.md

# Field Map verification warehouse-drift investigation

## Finding

The live byte drift was caused by a coherent concurrent loopback product mutation, not by the Field Map GET, its tests, or the verification commands. A long-running local Rufous server accepted one personal observation while verification was in progress. The row must not be removed or guessed away; it is valid local user data.

## Timeline and process evidence

- At `2026-07-12T01:05:09.890Z`, a network-forbidden live `GET /api/map-snapshot` began. It returned at `01:05:13.269Z` with 1,575 rows and proved the warehouse SHA-256 was unchanged before/after at `805d6d929988bc7b01d08e89021f39d245074d9532ae42f27e9ca063bda9551b`.
- First full-gate commands began at `01:05:35.503Z`. Static/docs/frontend commands ended by `01:05:50.054Z`; full Python ended at `01:07:12.123Z` with one unrelated stale profile-test failure and 700 passes.
- The repaired second full Python gate later passed 701/701 and completed before the persisted personal-row time.
- The sole live personal observation reports `created_at=updated_at=2026-07-12T01:12:10.774956+00:00` (18:12:10 local). The warehouse mtime became July 11 18:13:31 local as DuckDB completed persistence/checkpointing.
- Read-only process inspection found PID `10470`, launched July 11 16:29:35 local as `.venv/bin/uvicorn databox.api:app --host 127.0.0.1 --port 8000`, cwd this repository, still listening on `127.0.0.1:8000`.
- `packages/databox/databox/personal_collection_api.py` uses `duckdb.connect(database_path)` only inside explicit collection mutations. `POST /api/observations` creates exactly the observed row shape and timestamps. Read routes use `read_only=True`.
- Repository search found no test/source fixture containing the observed species code or date. All map API tests create `tmp_path/map.duckdb`; the map endpoint itself calls `duckdb.connect(db_path, read_only=True)`.

This evidence distinguishes an intended explicit local action from test leakage. Because the local server and verification shared the ignored warehouse concurrently, whole-session byte immutability was not a valid isolated-test assertion.

## Read-only logical reconciliation

The current warehouse was opened only with `read_only=True`. Before/after every investigation query, the current hash remained:

```text
87d45ece558cd248aa6efdd295798276775093a4906eeac40f8c41a9eea245bc
```

Inventory:

```text
18 schemas
127 tables/views in information_schema.tables excluding system schemas
schema inventory SHA-256: e667bddc1251d9ef3176bf3d53b2de277433270ca763d5a9b1e26910126e18ae
```

Critical deterministic current logical checksums (ordered rows plus column names, Python `repr` encoding):

```text
birding_agent.arizona_species_catalog:
  759356293c679655aba8a6edbdd9f1f2491ca8015bb068f33736f0e77ee4c5b2
environmental_observations.fact_bird_observation:
  e98faa34ff412c6c24bd6113c4473cbf5fd0982111dc92153849ad5b2fde38a2
birding_catalog_media.results:
  990ce330834e836637a20162911164f25305103f02cc8ff17dd71130142724d7
birding_personal.observations (sensitive text excluded; presence booleans only):
  4aa0a4bfec2bbf8cea7b85d1e3d58b9b6ec7136e97e3bd6220f24730c87038c3
birding_personal.watches:
  5fbf02332a3e203f2920d31b6489981df3c958611488856420cd6e15708427d8
birding_personal.watch_cancellation_requests:
  b734da957ef26895dc6c4f0e0d36d8f3e121dfa5f66e59c3feb188470bf76fc4
```

Comparison to `.10x/evidence/2026-07-11-rufous-product-evolution-aggregate-verification.md`:

```text
catalog: 706 = unchanged (624 species, 82 hybrids)
media: 1,412 = unchanged; 706 taxa
photos: 524 available / 182 unavailable = unchanged
calls: 600 available / 106 unavailable = unchanged
broad valid+reviewed+non-private US-AZ evidence: 1,676 rows, 1,676 IDs,
  173 taxa, 217 locations, 2026-06-08 through 2026-07-09 = unchanged
strict current-taxon/count-present map evidence: 1,575 rows/IDs,
  152 taxa, 208 locations = coherent
personal observations: 1, previously 0 = the identified concurrent write
watches: 0 = unchanged
watch cancellation requests: 0 = unchanged
Wishlist tables: 0 = unchanged
birding_calendar tables: 0 = unchanged
SMTP verification rows: 2 = unchanged
SQLMesh state SHA-256:
  c4995254709053ebffabcc16fbfe235e1d47b93208a7a1b1a81bb77b75852a93 = unchanged
```

No unexpected schema/table, source, catalog, media, map-evidence, Watch, calendar, Wishlist, or SMTP logical drift was found. The personal row is internally coherent: a current species, valid date, timestamped creation/update equality, optional location present, optional notes absent. Its actual location and identifiers beyond the non-sensitive species/date diagnostics were not recorded.

## Verification-path assessment

Every current Field Map test uses a temporary DB. `test_get_is_network_free_and_does_not_change_the_database` hashes its temporary file before/after the GET and passes. The live reconciliation separately proved the map GET preserved the original live hash before the concurrent POST. No Field Map code or test repair is needed.

The operational lesson is that a byte-hash gate over the ignored live database requires quiescence: before claiming whole-session immutability, identify/stop or isolate long-running local app writers, or compare logical state while explicitly accounting for authorized concurrent user changes. This investigation did not stop the user-owned server because that was not authorized.

## Baseline and limits

`87d45e…` is a defensible observed post-write baseline as of the read-only reconciliation, not a reconstruction of the pre-write file. Repeated read-only queries preserve it. No source copy exists for byte restoration, and restoration would incorrectly delete a coherent personal observation. The server remains live and can legitimately change the warehouse again; future verification must snapshot the starting hash immediately and confirm writer quiescence if byte identity is a required claim.

No restore, refresh, apply, live delivery, source/provider/model call, stage, or commit occurred during the investigation. Independent review remains required.
