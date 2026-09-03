Status: recorded
Created: 2026-09-03
Updated: 2026-09-03
Relates-To: .10x/tickets/done/2026-09-03-inventory-rufous-extraction-boundary.md

# Rufous extraction boundary inventory

## Purpose and method

This is the cold-start manifest for splitting public and private Rufous from Databox. It classifies repository surfaces by path pattern, traces observed dependencies, proposes the first bounded data-product contract, and identifies decisions that must be ratified before implementation. Inspection covered tracked source-shaped files under `app`, `workers`, `packages/databox`, `packages/databox-sources`, `scripts`, `tests`, `transforms`, `soda`, `.github/workflows`, `config`, `infra`, `docs`, `.schema`, `migrations`, root manifests, and `.10x`. Generated/local `app/dist`, `app/node_modules`, root `node_modules`, `build`, `site`, `.cache`, `.dagster`, `.logs`, `.wrangler`, `.venv`, and DuckDB/dlt runtime data were observed only to exclude them.

Classification terms: **move** means copy into Rufous, verify there, then delete from Databox; **remain** means Databox owns it; **split** means extract Rufous concerns while retaining/replacing the Databox portion; **regenerate** means do not copy generated output; **historical-only** means preserve as imported context, never active authority; **delete-after-verification** means no destination copy is required.

## Exhaustive path-pattern classification

### Move

| Path pattern | Owner/action |
|---|---|
| `app/index.html`, `app/package*.json`, `app/tsconfig*.json`, `app/vite.config.ts`, `app/public.env.example`, `app/public/**`, `app/src/**` | Rufous web applications, fixtures, artwork, adapters, and tests. Exclude `.DS_Store`, `dist`, `node_modules`, and `*.tsbuildinfo`. |
| `workers/rufous-ai/{package*.json,tsconfig.json,wrangler.jsonc,src/**,test/**}` | Rufous AI worker and tests. Exclude local Wrangler state. |
| `packages/databox/databox/api.py` | Split physically by moving the complete Rufous FastAPI application; destination must rename package/import identity rather than retain `databox.api`. |
| `packages/databox/databox/agents/**` | Rufous trip planner and Workers AI client. |
| `packages/databox/databox/agent_tools/**` | Product tools: Arizona bounds, weather/geocoding, persistence, media enrichment/backfill, wishlist removal, and privacy remediation. |
| `packages/databox/databox/{bird_alert_delivery,bird_alert_delivery_api,bird_alert_outbox,catalog_media,curated_photo,personal_collection,personal_collection_api,place_suggestions,target_planning,target_planning_api,trip_plan_calendar,trip_plan_calendar_api,watched_bird_evaluator,watched_bird_evaluator_api}.py` | Private Rufous product capabilities and writable application state. |
| `packages/databox/databox/public_*.py` | Public Rufous export, audit, hydration, media/audio discovery, review, approval, pins, delta, release, and restricted-mark policies, except that reusable provider source implementations remain in `databox-sources`. |
| `packages/databox/databox/{source_refresh_api,source_refresh_gate,source_refresh_runner}.py` | Current feature is Rufous UI/backend behavior, but it cannot move unchanged; see source-refresh decision below. |
| `scripts/birding/**`, `scripts/rufous_media/**`, `scripts/cloudflare/smoke_cloudflare_ai.py` | Rufous operator and release commands. |
| `tests/birding/**`, `tests/rufous_media/**`, `tests/cloudflare/**`, `tests/evals/**` | Product tests; Cloudflare tests move with their clients/workers. |
| `transforms/main/models/birding_agent/**`, `transforms/main/models/rufous_public/**` | Product SQLMesh models. |
| `soda/contracts/birding_agent/**`, `soda/contracts/rufous_public/**` | Product contracts. |
| Product portions of `transforms/main/tests/test_avonet_catalog.yaml` and `transforms/main/tests/test_models.yaml`; all of `test_rufous_public_avonet_species_traits.yaml` | Split monolithic YAML by model owner; move cases whose `model:` is `birding_agent.*` or `rufous_public.*`. |
| `.github/workflows/rufous-ai-worker.yaml`, `.github/workflows/rufous-public.yaml` | Rufous CI/deployment ownership. Preserve production fail-closed state. Rebuild path filters and remove stale Databox commands. |
| `config/rufous-*.json` | Product-reviewed selections, approvals, and pins. |
| `infra/cloudflare/**` | Product hosting/worker configuration and operations. |
| `migrations/20260711_structured_observation_locations.sql`, `migrations/20260711_trip_plan_calendar.sql` | Rufous writable application database migrations. |
| `docs/rufous-operations.md`, `docs/rufous-public-release.md`, `docs/images/rufous-trip-planner.jpg` | Product operations and illustration. |

### Remain in Databox

| Path pattern | Reason |
|---|---|
| `packages/databox-sources/databox_sources/{avonet,ebird,gbif,noaa,usfws,usgs,usgs_earthquakes,xeno_canto}/**` and matching source tests/cassettes/snapshots | Governed reusable ingestion sources. |
| `packages/databox/databox/config/sources.py`, `destinations/**`, `orchestration/**`, `quality/**` | Source registry, Polaris/Iceberg, Dagster, and platform quality. Exception: remove Rufous-owned USFWS target orchestration from `orchestration/domains/usfws.py` after destination replacement; retain only generic source ownership/observability appropriate to Databox. |
| `scripts/{analytics,operations,platform,sources}/**` | Platform commands. References to Rufous schemas or deleted product commands must be split/reconciled. |
| `tests/platform/**`, source-focused `tests/sources/**`, generic analytics tests | Platform validation. Exceptions listed under split. |
| `transforms/main/models/environmental_observations/**`, `transforms/main/models/analytics/platform_health.sql` | Ratified Databox model ownership. |
| `soda/contracts/environmental_observations/**`, `soda/contracts/analytics/**`, `soda/contracts/raw_ebird/**`, `soda/contracts/raw_noaa/**` | Databox model/source quality. |
| `.github/workflows/{ci,docs,release-please}.yaml` | Databox CI/docs/release; prune product jobs/paths if present. |
| `compose.iceberg.yml`, Polaris infra, `.env.example` platform fields | Databox source platform. Rufous gets a separate example with only its settings. |
| `docs/adr/0001..0008`, generic docs and generated dictionary for retained models | Databox architecture. Amend current ADR/index language to point to the cross-repository contract. |
| `.schema/environmental_observations/ontology.md` | Databox environmental ontology; remove only application-specific prose if any. |

### Split

| Surface | Required split |
|---|---|
| Root `pyproject.toml`, `uv.lock`, `Taskfile.yaml`, `README.md`, `mkdocs.yml`, `.gitignore`, `.pre-commit-config.yaml`, `LICENSE` | Rufous receives a minimal independent toolchain, tasks, README, ignore rules, hooks, and license. Databox removes product dependencies/tasks/docs navigation. Never copy lock state blindly; regenerate Rufous lock from its manifest. |
| `packages/databox/pyproject.toml` | Move product runtime dependencies to Rufous; keep Dagster/dlt/SQLMesh/platform dependencies in Databox. Rename destination Python package to `rufous`. |
| `packages/databox/databox/config/settings.py` | Rufous defines its own settings for application DB, data-product artifact, AI, SMTP, and release paths. Databox keeps source/Polaris/AWS settings. No import crosses repositories. |
| `packages/databox/databox/orchestration/_factories.py`, `definitions.py`, source domain modules | Remove product SQLMesh groups/models/check expectations from Databox after moved models run in Rufous. Keep source and `environmental_observations`/analytics orchestration. USFWS target job moves; Databox retains provider implementation and generic load-status ownership only if it can materialize without Rufous targets. |
| `tests/analytics/test_analytics_contract_inventory.py` | Split expected model/check inventory by owner. |
| `tests/analytics/test_fact_bird_observation.py` | Remains with Databox because it tests retained environmental model; remove any product fixture assumptions. |
| `tests/sources/test_avonet_catalog_models.py`, `test_ebird_models.py`, `test_usfws_orchestration.py`, `test_source_registry.py` | Preserve source/model tests in Databox; move product-model and Rufous-target assertions. Replace the current USFWS manual-job assertion with stable public-source contract tests. |
| `transforms/main/config.py`, `transforms/main/tests/test_avonet_catalog.yaml`, `test_models.yaml` | Rufous receives independent SQLMesh configuration and product test fragments; Databox retains environmental fragments. |
| `docs/{index,commands,configuration,contracts,analytics-examples,runbook,source-layout,incremental-loading}.md`, dictionary index/lineage | Move product sections to Rufous and rewrite Databox around artifact production. Product dictionary pages move/regenerate; retained pages and lineage regenerate in Databox. |
| `.github/workflows/rufous-public.yaml` references to source loading and environmental models | Workflow moves, but direct source refresh, Databox checkout-relative paths, local `data/databox.duckdb`, and raw model assumptions must be replaced by artifact acquisition plus Rufous-owned SQLMesh/app DB. |

### Regenerate; do not copy

- `app/dist/**`, `app/node_modules/**`, root `node_modules/**`, `app/*.tsbuildinfo`.
- `build/**`, `site/**`, `htmlcov/**`, coverage/test caches, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`.
- `transforms/main/.cache/**`, SQLMesh logs/state, `.dagster/**`, `.dlt_state/**`, `packages/databox/data/**`, `data/*.duckdb*`, `data/dlt/**`, `logs/**`, `.logs/**`.
- `docs/dictionary/index.md`, `docs/dictionary/lineage.md`, and per-model dictionary pages are regenerated independently from each repository's owned SQLMesh project. Move no generated product pages as authority.
- Rufous `uv.lock` and npm lock files: npm locks move with their exact package; Python lock regenerates from the new Rufous manifest.

### Delete after destination verification

- `app/.DS_Store` and other OS/editor artifacts.
- Databox product package modules, scripts, tests, configs, migrations, app/worker directories, and product workflows listed as move.
- Rufous-specific task aliases, docs navigation, release audit paths, and dependencies remaining in Databox after equivalent destination checks pass.
- Current Databox `usfws_ingest` modeled-target Dagster job after the Rufous manual job passes; do not delete the reusable `databox_sources.usfws` source.

### `.10x` records

Classification is semantic and exhaustive rather than filename-only:

1. **Move as active authority**: records governing the application, `birding_agent`, `rufous_public`, public media/audio/release, Cloudflare/Rufous UI, personal collection, target planning, watches/alerts/calendar, product privacy, Arizona catalog/map/place UX, and product AI. This includes matching decisions/specs/knowledge plus their tickets/evidence/reviews.
2. **Remain active in Databox**: canonical source registry, source testing/VCR, dlt/Polaris/Iceberg, platform health, generic environmental CDM, source-package direction, refresh orchestration, and source migrations (AVONET/GBIF/eBird/Xeno/USFWS provider-level records).
3. **Split**: `local-rufous-polaris-aws-iceberg-architecture`, `usfws-manual-media-discovery`, cross-source species conformance, AVONET trait/catalog records, source-refresh controls, and 2026-09-02 aggregate migration/merge evidence. Databox retains the source/platform clauses; Rufous receives product clauses and a provenance link to the original commit.
4. **Historical-only in Rufous**: relevant superseded MotherDuck/Quack/local-only product records may be copied into a clearly marked `superseded/imported-from-databox` area. They must not be active authority.
5. **Extraction records remain in Databox until closure**: the split decision, both extraction specs, parent/child tickets, inventory, and final two-repository evidence. Rufous receives a thin decision/index after bootstrap, not divergent duplicate active specs.

Keyword inventory found 30 decisions, 43 specs, 11 research records, 4 knowledge records, 124 evidence records, 115 reviews, and 128 done tickets potentially touching bird/Rufous/media/product terms. Filename keywords are not ownership proof; each copy/delete manifest must apply the semantic rules above and record the resulting explicit path list before mutation.

## Observed cross-boundary dependencies

### Python imports

The current Rufous module cluster imports itself through `databox.*`: `api.py` composes agents, weather/geocoding, recommendation media, alert delivery, catalog media, curated photos, personal collection, places, source refresh, target planning, calendar, and watched-bird routes. Public modules form a second dense cluster around `public_export`, `public_media_*`, `public_release*`, and `public_restricted_marks`. These must move as a vertical package and be renamed together; piecemeal movement would create prohibited private Databox imports.

Provider edges:

- `public_media_ingest.py` imports `databox_sources.usfws.source.{USFWS_MAX_TARGET_SPECIES,usfws_source}` plus private Databox settings/destination helpers. Destination must pin `databox-sources` but own its destination configuration and load-status publication or call a newly documented public run surface.
- `public_inaturalist_media_ingest.py` imports the private `databox_sources._public_inaturalist.source.inaturalist_public_photo_source` and Databox Quack helpers. Ownership is unresolved below.
- `public_wikimedia_media_ingest.py` implements product-specific provider access inside `databox`; it moves with Rufous.

### SQL dependencies

Moved `birding_agent` models currently read:

- `environmental_observations.dim_species`
- `environmental_observations.dim_bird_hotspot`
- `environmental_observations.dim_bird_species_traits`
- `environmental_observations.fact_bird_observation` (product queries filter `is_valid`, `is_reviewed`, and `is_location_private = false`)
- `environmental_observations.fact_bird_occurrence`
- `environmental_observations.fact_bird_sound_recording`
- `polaris_aws.raw_ebird.species_list`, `polaris_aws.raw_ebird.taxonomy`
- `raw_gbif.occurrences` / `polaris_aws.raw_gbif.occurrences`
- `raw_xeno_canto.recordings` / `polaris_aws.raw_xeno_canto.recordings`

Moved `rufous_public` models currently read GBIF, AVONET, USFWS and product-owned iNaturalist raw snapshots. Rufous may not retain these Polaris/raw references; models must read the artifact interfaces below. `raw_inaturalist.*` is produced by the Rufous-specific target workflow and belongs in Rufous's writable/model database, not the Databox artifact.

### Filesystem and command dependencies

Current product defaults assume `data/databox.duckdb`; scripts, API settings, media preparation, workflow SQLMesh steps, and app tasks share it for both modeled inputs and writable state. Split into explicit `RUFOUS_DATABOX_PRODUCT_PATH` (regular read-only artifact) and `RUFOUS_DATABASE_PATH` (Rufous-owned writable DB). No repository-relative Databox default is allowed.

`Taskfile.yaml` currently owns app build/dev, media backfill, API launch, and Cloudflare smoke tasks; these move. Databox `full-refresh`/`verify` remain. Rufous adds artifact contract-check, product-model plan/test, private app, public build/audit, media maintenance, and worker tasks.

The public workflow contains stale `scripts/sources/load_dlt_quack.py`, broad environmental/source path filters, direct `data/databox.duckdb` creation, and Databox package commands. It must not be enabled while moving. PR/synthetic validation can be ported after paths are destination-relative; production remains `if: ${{ false }}`.

### Generated documentation

`generate_docs.py` discovers one SQLMesh project and emits model pages/index/lineage. Each repository must run it against its own model set. Databox's generated lineage will end at exported contract relations; Rufous's will begin at external artifact AssetSpecs/models. Cross-repository lineage should be documented by contract ID/version, not fabricated SQLMesh edges.

## Proposed initial DuckDB artifact contract

Exact relation identities below are the observed minimum to preserve current product semantics without giving Rufous Polaris credentials or unrestricted private locations. The implementation ticket must freeze columns/types/checksums from the referenced current relations before coding.

### Compatibility metadata

Schema `databox_product_meta`:

- `contract`: exactly one row with `contract_name = 'rufous-inputs'`, integer `schema_version = 1`, immutable Databox Git revision, generation timestamp, producer version, and canonical contract SHA-256.
- `relations`: one row per relation with schema/name, row count, ordered-schema SHA-256, content/snapshot identifier where available, and privacy classification.

Rufous must reject missing tables, unsupported schema versions, duplicate metadata rows, schema-hash mismatch, or artifact paths that are not regular files. It attaches the artifact read-only.

### Data relations

Schema `rufous_inputs_v1`:

1. `dim_species` ← current `environmental_observations.dim_species`.
2. `dim_bird_hotspot` ← current `environmental_observations.dim_bird_hotspot`.
3. `dim_bird_species_traits` ← current `environmental_observations.dim_bird_species_traits`.
4. `public_bird_observation` ← current `fact_bird_observation` restricted at export to non-null source identity, `is_valid = true`, `is_reviewed = true`, `is_location_private = false`; this is the only observation-location interface.
5. `fact_bird_occurrence` ← current `environmental_observations.fact_bird_occurrence`.
6. `fact_bird_sound_recording` ← current `environmental_observations.fact_bird_sound_recording`.
7. `ebird_arizona_species_snapshot` ← latest coherent `US-AZ` species-list/taxonomy snapshot fields currently consumed by `birding_agent.arizona_species_catalog`, including snapshot load/time provenance.
8. `avonet_species_traits_snapshot` ← validated complete AVONET source snapshot required to preserve all 10,661 public trait rows, including pinned file/version/license and dlt provenance; `dim_bird_species_traits` alone is insufficient because it contains only conformed matches.
9. `gbif_occurrence_snapshot` ← current latest-by-key GBIF source projection containing every field consumed by `gbif_iceberg_occurrences`, `gbif_occurrence_evidence`, and `rufous_public.gbif_eod_occurrence`, with dlt/source provenance.
10. `xeno_canto_recording_snapshot` ← current latest-by-id recording projection consumed by product media evidence, with dlt/source provenance. (The retained fact relation may supersede this only after column-equivalence proof.)
11. `usfws_image_records` and 12. `usfws_image_search_runs` ← current Iceberg source outputs required for latest-complete run validation and commercial-image modeling, including run and dlt provenance.

Not included: raw private eBird observations, weather/streamgage/earthquake tables, analytics health, personal/application schemas, `raw_inaturalist` product state, API/model credentials, media binaries, or local operational metadata.

## Public `databox-sources` USFWS surface

Current package behavior is implemented in `databox_sources.usfws.source`; `databox_sources.usfws.__init__` exports nothing. The required Databox child must expose a stable public path such as `databox_sources.usfws` with only documented provider-level symbols: `usfws_source`, `USFWS_MAX_TARGET_SPECIES`, and the target mapping contract/type needed by Rufous. It must not expose Databox settings, Dagster assets, Rufous target derivation, DuckDB paths, Polaris credentials, or publication helpers. A contract test must install/import the package in isolation and execute cassette-backed explicit-target extraction. Rufous pins an immutable Databox Git revision until package releases exist.

## Ratified boundary decisions

On 2026-09-03 the user ratified all six inventory decisions:

1. Rufous-specific iNaturalist photo ingestion moves to Rufous rather than becoming a public Databox source.
2. Rufous source-refresh controls are removed; operators refresh/export in Databox and explicitly select the resulting artifact.
3. Artifact distribution is local explicit file only for v1; remote publication is deferred.
4. Artifact schemas are `databox_product_meta` and `rufous_inputs_v1`; incompatible changes require a new versioned schema.
5. The initial artifact exports only valid, reviewed, non-private observations. Private locations are excluded.
6. Databox removes the current Rufous-target USFWS job after destination verification and retains only reusable source/status/publication primitives and provider contract tests; Rufous owns every target-bearing run.

## Bounded sequenced child-ticket recommendations

The decisions are ratified. Recommended sequence:

1. **Define/export Databox Rufous input artifact**: add the 12 input projections, metadata/contract checker, atomic exporter, privacy tests, deterministic fixture, and operator command. Databox-only; no destination repo.
2. **Publish stable USFWS source API**: public re-export, typed target contract, isolated cassette test, and immutable revision instructions. Decide iNaturalist ownership in this slice.
3. **Bootstrap standalone Rufous**: create fresh repo/package/toolchain, copy only non-generated product surfaces, establish dual DuckDB paths, fixture artifact, credential-free tests, and fail-closed workflows. No Databox deletions.
4. **Move Rufous models and backend**: split SQLMesh tests/config and Soda contracts; rewrite inputs to `rufous_inputs_v1`; rename Python imports; move migrations and private app database; port manual USFWS orchestration.
5. **Move web/public/media/deployment**: app, worker, configs, scripts, infra, docs, audits, public tests/workflows; production remains disabled.
6. **Transfer records and reconcile documentation**: explicit record manifest under semantic rules, active/superseded statuses, generated dictionaries, README/task/docs in both repositories.
7. **Prune Databox**: only after corresponding Rufous gates pass; delete moved surfaces, remove dependencies, source-refresh coupling, product checks/docs, and regenerate lock/docs.
8. **Two-repository aggregate gate**: independently run CI, SQLMesh, docs, pre-commit, secret scans, residue/coupling searches, artifact compatibility test, and adversarial reviews; no merge or production enablement.

Each ticket should cite exact predecessor evidence and be closed before the next destructive slice.

## Evidence commands

Inventory used bounded `find` over each governed root, `rg` for Rufous/bird ownership, Python import edges, SQL relation references, database/path/command/workflow dependencies, DDL ownership, mixed SQLMesh tests, generated docs, and durable record themes. Final checks validate references/statuses and whitespace only; no runtime/product files or destination paths were mutated.
