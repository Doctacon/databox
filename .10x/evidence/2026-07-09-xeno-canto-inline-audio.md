Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-add-inline-xeno-canto-audio.md, .10x/specs/xeno-canto-inline-audio.md

# Xeno-canto inline audio evidence

## What was observed

The stable plan-detail API now separates raw persisted evidence from a typed `media` projection. For available Xeno-canto evidence, the projection exposes species/recording context, quality, recordist, readable license information, one canonical recording ID, source page, and direct audio URL.

The backend collects every available recording identifier used by the row: top-level `source_record_id` plus summary/payload `source_record_id` and `recording_id`. Each supplied value must be an exact numeric or uppercase `XC`-prefixed numeric string. Equivalent forms such as `XC2`, `2`, and `002` normalize to canonical `2`; any malformed, non-string, or conflicting supplied identifier makes the canonical typed `recording_id` null.

Source and audio are then validated independently against that canonical ID. A safe source uses exact HTTPS Xeno-canto host/path grammar and `/{canonical_id}`; safe audio independently uses `/{canonical_id}/download`. A valid source remains active when audio is missing, unavailable, malformed, or has another ID. A valid audio URL remains playable when the source is independently invalid. Missing canonical identity still disables both. Raw evidence remains preserved as provenance but unsafe values do not become active targets.

The React result view independently requires a canonical numeric typed `recording_id` and applies an exact raw full-string grammar before any WHATWG URL normalization: only `https://xeno-canto.org/{digits}`, `https://www.xeno-canto.org/{digits}`, and their exact `/download` forms with optional trailing slash are accepted. This rejects credentials, ports, query/fragment text, dot segments, percent-encoded traversal/segments, and unexpected hosts before normalization. Each extracted raw path ID is compared independently with the typed canonical ID. The view uses native `<audio controls preload="none">` with no autoplay and keeps species/recording context, recordist, quality, readable license information, and any independently valid source link nearby. No proxy, download, cache, storage, custom audio engine, waveform, or new media host was added.

## Live media-header observation

A header-only request was made; no audio body was stored:

```text
curl -sSIL --max-time 20 https://xeno-canto.org/145961/download
```

Relevant result:

```text
HTTP/2 200
access-control-allow-origin: *
content-type: audio/mpeg
```

This supports direct browser streaming for the evidenced Xeno-canto download path. It does not guarantee every future recording remains available.

## Deterministic validation

### API and URL safety

```text
uv run --no-sync ruff check packages/databox/databox/api.py tests/test_api.py
uv run --no-sync ruff format --check packages/databox/databox/api.py tests/test_api.py
uv run --no-sync mypy packages/databox/databox/api.py
uv run --no-sync pytest --no-cov -q tests/test_api.py
```

Initial results: Ruff, format, and MyPy passed; all 15 then-current API tests passed. Tests covered the stable media key set, persisted `audio_file_url`, exact hosts, credentials, explicit ports, unexpected subdomains, wrong paths, unavailable sentinels, malformed URLs, missing IDs, URL-to-recording-ID mismatches, HTTPS Creative Commons licenses, unsafe license URLs, and preservation of raw evidence.

### React

```text
cd app && npm run typecheck && npm test && npm run build
```

Initial results: strict TypeScript passed; 20 Vitest tests passed across two files; Vite built 30 modules. Rendered tests proved native controls, accessible context label, `preload="none"`, absent autoplay, direct safe audio source, separate source link, readable license link/text, recordist/quality context, unsafe URL defense-in-depth, unavailable sentinel exclusion, missing audio fallback, and failed-load fallback with attribution retained.

```text
task app:audit-bundle
```

Result: all three Cloudflare configuration names and all three configured values were absent from compiled browser assets.

### Aggregate repository

```text
task ci
task docs:build
.venv/bin/pre-commit run --all-files
```

Results: final full CI passed Ruff, formatting, MyPy for 72 source files, all 212 tests at 82.77% coverage, secret scan, staging drift, and platform-health drift. Strict MkDocs generated 16 model pages plus lineage/index and built successfully. Every pre-commit hook passed.

### No-audio-storage audit

```text
git ls-files | grep -Ei '\.(mp3|wav|ogg|m4a|flac|aac|opus|webm)$'
find . <excluding .git, .venv, data, node_modules, dist, site> -type f <audio extensions>
```

Results: no tracked or relevant untracked audio artifact was found. `git diff --cached --name-only` returned no staged files; `git diff --check` passed.

## What this supports

- Valid persisted Xeno-canto MP3 URLs can stream through native in-app controls only after user interaction.
- Opening a plan does not eagerly preload audio.
- Unsafe/malformed/mismatched identifiers or URLs never become active player or link targets in either the API projection or React defense-in-depth layer.
- Attribution, license information, and context survive malformed/missing media; an independently valid source link survives missing, invalid, unavailable, mismatched, or runtime-failed audio.
- Databox continues to store metadata/links only in the single DuckDB; no audio bytes are stored.

## Independent-review repair

Independent review directly proved two significant gaps in the initial implementation:

1. `payload.recording_id="2"` could win over conflicting `source_record_id="XC1"`, activating `/2` URLs instead of failing closed.
2. React could activate a source page for recording `1` and audio for recording `2` because it validated path shapes independently without comparing their IDs.

The repair establishes one canonical identity chain across all persisted identifiers and the typed response. Each exact URL path ID must independently equal that canonical identity. New end-to-end API cases prove:

- top-level `XC1` conflicting with payload `2` yields `recording_id`, `source_url`, and `audio_url` all null;
- top-level/summary/payload values `XC2`, `2`, `XC002`, and `002` normalize consistently to typed `recording_id="2"` and permit only `/2` plus `/2/download`;
- canonical ID `3` with page `/3` and audio `/4/download` preserves typed ID `3` and the valid source while nulling only audio;
- malformed row, summary, payload, lowercase-prefix, decimal, and non-string identifiers null the canonical ID and both URLs.

New React cases inject malformed typed responses with page `1`/audio `2`, typed ID `2` against both URL IDs `1`, and non-canonical typed `XC1`. Each source/audio value is now handled independently: matching values remain active while mismatched values fail closed, and attribution always remains visible.

Repair validation:

```text
uv run --no-sync ruff check packages/databox/databox/api.py tests/test_api.py
uv run --no-sync ruff format --check packages/databox/databox/api.py tests/test_api.py
uv run --no-sync mypy packages/databox/databox/api.py
uv run --no-sync pytest --no-cov -q tests/test_api.py
cd app && npm run typecheck && npm test && npm run build
task app:audit-bundle
git diff --check
git diff --cached --name-only
```

Results: Ruff, format, and MyPy passed; all 16 API tests passed; strict TypeScript passed; 23 Vitest tests passed across two files; Vite built 30 modules; bundle audit passed. Diff check passed and no staged files were present. No live model or audio-body request ran during the repair.

## Independent re-review repair

Independent re-review found two remaining closure blockers in that first repair:

1. Coupling source and audio as one pair violated the active fallback contract by removing a valid source page whenever audio was absent or invalid.
2. React passed URLs through WHATWG normalization before checking their paths, allowing raw dot segments or percent-encoded traversal to be normalized away before validation.

The final repair keeps the canonical persisted-ID chain but validates each media URL independently. API regressions now prove:

- a valid source remains exposed with missing, `javascript:`, unavailable-sentinel, or mismatched-ID audio;
- a valid canonical audio URL remains exposed when source is independently invalid;
- identifier conflicts/malformed identifiers still null canonical identity and therefore both URLs;
- page `/3` with audio `/4/download` exposes only page `/3` for canonical `3`.

React now matches the raw input against an anchored full-string grammar without first constructing a `URL`. Tests prove raw `/1/../2` and `/1/%2e%2e/2` are rejected even when WHATWG normalization would produce an otherwise approved path. Additional cases prove source fallback with missing/invalid audio and playable canonical audio with independently invalid source.

Final focused validation:

```text
uv run --no-sync ruff check packages/databox/databox/api.py tests/test_api.py
uv run --no-sync ruff format --check packages/databox/databox/api.py tests/test_api.py
uv run --no-sync mypy packages/databox/databox/api.py
uv run --no-sync pytest --no-cov -q tests/test_api.py
cd app && npm run typecheck && npm test && npm run build
cd .. && task app:audit-bundle
.venv/bin/pre-commit run --all-files
git diff --check
git diff --cached --name-only
```

Results: Ruff, format, and MyPy passed; all 16 API tests passed; strict TypeScript passed; 27 Vitest tests passed across two files; Vite built 30 modules; bundle audit and all pre-commit hooks passed. Diff check passed and no staged files were present.

## Limits

- Playback still depends on the user's browser and current Xeno-canto availability/CORS behavior.
- Only the exact ratified Xeno-canto hosts and numeric recording paths are active; a future upstream host/path change will fail closed until separately ratified.
- Creative Commons links are active only for exact HTTPS Creative Commons hosts and `/licenses/{code}/{version}` paths; other license values remain readable text or an unavailable-link label.
- No live Cloudflare model call was made.
