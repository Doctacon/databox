Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Recommendation Media Enrichment

## Purpose and scope

This specification governs server-side request-time selection, validation, and persistence of one representative bird photo and one representative call for each completed trip-plan recommendation.

It supplements the scheduled GBIF and Xeno-canto pipelines governed by `.10x/specs/birding-agent-data-integrations.md`. `data/databox.duckdb` remains the only database and system of record.

## Execution boundary

- Media enrichment MUST begin only after the deterministic recommendation set and rank order are fixed.
- Media results MUST NOT add, remove, reorder, relabel, or change the confidence/rationale of recommendations.
- The local Python process MUST own discovery requests, validation, selection, and persistence. The browser MUST NOT call GBIF or Xeno-canto discovery APIs.
- Work MUST be bounded to the recommendations in one plan, currently at most five high-likelihood plus three uncommon-plausible targets.
- Network concurrency, response bytes, candidate count, and timeout MUST be explicitly bounded and tested.
- Media lookup failure MUST NOT fail the plan or trigger model retry/fallback. It MUST persist a typed unavailable result for that recommendation/media kind.
- Media enrichment MUST complete or persist its unavailable state before the plan is returned as completed.

## Photo lookup and selection

For each recommendation with a conformed scientific name:

1. Query GBIF occurrence search for the exact normalized binomial, `country=US`, `stateProvince=Arizona`, and `StillImage` media.
2. Reject occurrences whose accepted/species scientific identity does not normalize to the recommendation identity.
3. Inspect a bounded candidate set and choose exactly one deterministically.
4. Eligible photos MUST have:
   - a valid GBIF occurrence key,
   - HTTPS media identity/reference data,
   - an image media type and supported image format,
   - recognized Creative Commons license metadata,
   - creator or rights-holder attribution,
   - a safe source reference.
5. The returned occurrence MUST independently report country `US`/`United States` and `stateProvince=Arizona`; query parameters alone MUST NOT confer Arizona scope.
6. Candidate preference MUST be total and deterministic: complete attribution first, then normalized immutable occurrence/media fields. Selection MUST NOT depend on API return order or media array position.
7. Eligible non-ND photos MUST activate only the derived `https://api.gbif.org/v1/image/cache/500x500/occurrence/{numeric occurrence key}/media/{lowercase md5 of the exact original identifier}` URL. Validation MUST reject any other host, size, path grammar, key/hash mismatch, query, fragment, credentials, or traversal. Original/discovery/root URLs MUST NOT be active display URLs.
8. Photo licenses are limited to CC0, BY, BY-SA, BY-NC, and BY-NC-SA with explicit sane Creative Commons versions. Photo ND variants MUST persist as unavailable because no exact-original display policy is active.
9. Unknown slugs, malformed/unknown versions, missing, malformed, non-Creative-Commons, or internally inconsistent license/identity data MUST fail closed.

The persisted photo evidence MUST include recommendation ID, GBIF occurrence/media identifiers, normalized species identity, original media identifier as provenance, active display URL when safe, source reference, creator, rights holder, publisher, format, license code/URL, selection reason, status, caveats, and lookup timestamp.

## Call lookup and selection

For each recommendation with a conformed scientific name:

1. Query Xeno-canto API v3 for exact genus/species plus United States/Arizona scope.
2. Validate candidates using the existing canonical recording-ID, exact HTTPS host/path, explicit license allowlist, and attribution constraints. Arizona candidates MUST independently report `United States` and locality/state evidence containing Arizona; query scope alone is insufficient. Global fallback candidates MAY be non-Arizona but MUST be labeled `Global example`.
3. Prefer call-like recording types over song and other vocalization types, then quality A through E and numeric recording ID. Tie-breaking MUST include normalized immutable selection fields followed by every exact persisted output field, including case-sensitive recording type, recordist, country, locality, source/audio URLs, and license metadata, so case-equivalent duplicates are total and independent of API order while preserving selected attribution spelling.
4. Select exactly one valid Arizona recording when available.
5. Only when no valid Arizona candidate exists, perform one exact-species global query and apply the same deterministic selection.
6. Persist geographic scope as `Arizona` or `Global example`; the UI MUST display that distinction.
7. Recognized CC0/BY/BY-SA/BY-NC/BY-NC-SA licenses and BY-ND/BY-NC-ND variants with explicit sane versions are allowed for unchanged remote audio streaming. Unknown slugs and malformed or invented versions MUST fail closed. Databox MUST NOT alter the audio bytes.

The persisted call evidence MUST include recommendation ID, canonical recording ID, normalized species identity, Arizona/global scope, recording type, quality, recordist, locality/country where available, source/audio URLs, license code/URL, selection reason, status, caveats, and lookup timestamp.

## Persistence and API contract

- Media metadata MUST use `birding_agent.*` persistence inside `data/databox.duckdb`.
- The implementation SHOULD reuse recommendation-linked trip-plan evidence rather than add a parallel database unless a focused schema need proves otherwise.
- Each recommendation MUST have at most one selected photo result and one selected call result for a plan, including explicit unavailable results.
- Persistence MUST be atomic with completed-plan persistence or provide equivalent cleanup so a failed plan cannot leave a falsely completed partial artifact.
- The stable plan-detail API MUST expose recommendation-centric `photo` and `call` objects, each typed as available or unavailable.
- Raw upstream payloads MUST be bounded and MUST NOT expose arbitrary active URLs to the browser.
- A bounded aggregate media-enrichment tool trace MUST record counts, scopes, durations, and safe caveats without credentials or raw transport details.

## Existing-plan backfill

- One explicit command/task MUST enumerate existing persisted recommendations and enrich missing photo/call results.
- The backfill MUST be idempotent and MUST NOT call the model, alter plan text, recommendation identity/rank, weather, or original creation timestamps.
- GET endpoints MUST remain read-only and MUST NOT trigger enrichment.
- Re-running the backfill MUST not duplicate evidence.
- Media failures during backfill MUST persist unavailable results and continue with other recommendations.

## Binary-media boundary

- Databox MUST NOT download, proxy, cache, transcode, crop, or persist image/audio bytes.
- Images MUST load lazily in the browser.
- Audio MUST use native controls, `preload="none"`, and no autoplay.
- Source and license attribution MUST remain visible when later image/audio loading fails.

## Acceptance scenarios

### Queen Valley coverage

Given the eight recommendations in the observed Queen Valley plan, when exact media enrichment runs, then each recommendation has one persisted photo result and one persisted call result. Current source observations support available GBIF photos for all eight and Xeno-canto calls through Arizona-first/global-fallback selection for all eight.

### Local call preferred

Given a species with valid Arizona and global Xeno-canto recordings, when selection runs, then the chosen call has scope `Arizona`.

### Global fallback

Given Ross's Goose has no valid Arizona recording but has a valid global recording, when selection runs, then one global example is persisted and clearly labeled `Global example`.

### Media unavailable

Given GBIF or Xeno-canto is unavailable, times out, returns malformed data, or has no valid licensed candidate, when planning completes, then the factual recommendation remains, an unavailable media result and caveat are persisted, and no unsafe URL is active.

### Idempotent backfill

Given two existing plans with 16 recommendations, when the explicit backfill is run twice, then plan/recommendation content is unchanged and each recommendation has no more than one photo result and one call result.

## Explicit exclusions

- No browser discovery calls.
- No media binary storage, proxy, offline cache, crop, transform, waveform, or transcoding.
- No model involvement in media selection or captions.
- No media-driven recommendation/ranking changes.
- No Wikimedia Commons source in this slice.
- No unrecognized license or arbitrary-host activation.
