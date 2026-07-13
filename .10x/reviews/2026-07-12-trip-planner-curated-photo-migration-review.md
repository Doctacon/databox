Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: `.10x/tickets/done/2026-07-11-migrate-trip-planner-curated-photos.md`, Trip Planner curated-photo implementation and saved-photo migration
Verdict: pass

# Trip Planner curated-photo migration review

## Assumptions tested

- Production photo enrichment actually enters the shared curated selector rather than the legacy injected GBIF compatibility seam.
- Saved-photo migration cannot regenerate recommendations, refresh calls, duplicate evidence, or re-query completed curated rows.
- API and browser contracts bind provider, record ID, exact scientific identity, URL grammar, license, creator, and dimensions rather than accepting superficially plausible metadata.
- GBIF occurrence context, Xeno-canto calls, calendar/outbox, personal state, timestamps, and unrelated warehouse/runtime state remain independent of photo replacement.
- Failure between recommendations leaves a resumable completed checkpoint rather than deleting or duplicating prior results.

## Findings

No blocker or significant finding remains.

- Correctness: production selector conversion and photo-only persistence are direct and bounded. Per-recommendation transactions make completed rows durable; current curated rows are excluded on inspection, and cardinality verification rejects incomplete/duplicate completion.
- Source integrity: available rows must use exact curated provider metadata and strict provider-specific HTTPS URL grammars. Legacy GBIF representative URLs are rejected while GBIF occurrence-context evidence remains accepted separately.
- Side effects: the live result inserted eight photos and zero calls. Pre/post fingerprints prove all non-photo data and 19 external files unchanged. The command path contains no model, email, source-refresh, catalog, or binary download operation.
- API/frontend: Python serialization and TypeScript exact-key validation agree on provider, license code, and dimensions. Presentation labels the actual provider and fails malformed metadata closed before partial plan rendering.
- Tests: focused tests cover the production selector path, replacement, idempotence, partial persistence failure, call/context preservation, and malformed frontend metadata. Full Python/frontend/static/build/SQLMesh gates pass.

## Verdict

Pass. The implementation and the one authorized live migration satisfy the active spec and owning ticket without scope expansion.

## Residual risk

Provider-hosted images may later disappear or change availability; metadata-only storage intentionally avoids binary retention. The existing Vite large MapLibre chunk advisory is unrelated and unchanged. Neither is a closure blocker.
