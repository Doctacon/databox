Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Arizona catalog photo and call media

## Purpose and ownership

This specification governs representative media metadata for Arizona Birds catalog cards and profiles. It extends `.10x/specs/arizona-bird-catalog-and-profile.md` without changing catalog membership, exact taxon identity, warehouse facts, or GET side-effect boundaries.

Runtime-owned DuckDB tables MUST store exactly one current photo result and one current call result per catalog species code, each available or unavailable. SQLMesh does not own these request/external-service artifacts. Browser code never performs discovery.

## Explicit batch lifecycle

A resumable explicit command/job MUST:

1. Read the exact current 706-row catalog in stable order.
2. Skip already complete current results unless explicit refresh is requested.
3. Resolve only exact scientific-name/species-code identities through existing bounded GBIF and Xeno-canto selectors.
4. Persist each taxon's photo/call result atomically with source/provenance and safe failure state.
5. Record bounded run/checkpoint counts and sanitized failures so interruption resumes without repeating completed lookups.
6. Use controlled sequential or tightly bounded concurrency and existing source timeout/size/license/URL rules.
7. Never run from GET, startup, normal source refresh, watch evaluation, or frontend code.

The command MUST support inspect/dry-run and explicit apply/refresh modes, one local writer, rollback for each taxon aggregate, idempotent rerun, and safe database-busy behavior. It MUST NOT run while Quack/SQLMesh owns the warehouse.

## Photo contract

Reuse the governed GBIF recommendation-photo eligibility, exact identity, Arizona evidence, license allowlist, canonical derived image-cache URL, attribution, and fail-closed URL/hash checks. Persist metadata only. Available results expose safe display/source URL, creator/rights/publisher/format/license, selection reason, and lookup time. Unknown/malformed licensing or identity is unavailable.

## Call contract

Reuse governed Xeno-canto exact recording ID, HTTPS host/path, unchanged-stream license allowlist, Arizona-first/global-fallback selection, attribution, quality/type/location, source/audio URL, selection reason, and lookup time. Global fallback MUST be labeled. Native playback uses remote bytes unchanged and stores none.

## Identity and unavailable behavior

- Exact current catalog scientific identity is mandatory.
- Hybrids and taxonomy-drift taxa MUST NOT use parent, common-name, historical-name, or report-as guesses.
- Missing/unsafe media persists an unavailable result with bounded caveat; it never removes a catalog row.
- Catalog refresh does not silently remap media. Stale species-code/scientific-name identity is unavailable until explicit refresh.

## API

`GET /api/birds` summaries and `GET /api/birds/{species_code}` profiles MUST include exact bounded `photo` and `call` objects. When the media table is absent/incomplete/stale, return typed unavailable objects. GETs remain read-only/network-free.

The browser validator MUST reject extra fields, unsafe URLs/licenses, identity mismatches, duplicate media, malformed dates, and available states missing required attribution.

## Browser

Catalog cards show:

- lazy-loaded 4:3 photo or an original Rufous silhouette placeholder;
- common/scientific name and category;
- one compact accessible Play/Stop control when a call is available, with only one catalog call active at a time and `preload="none"`;
- concise attribution/media-unavailable state.

Profiles show larger photo, native or compact playable call, full creator/recordist/source/license/scope attribution, selection caveat, and lookup freshness. Image/audio load failure preserves attribution and a visible unavailable/error state. Playback MUST stop on route/page change and respect keyboard/focus semantics.

## Acceptance scenarios

- Exact species with safe GBIF/Xeno results renders one photo and one call on card/profile with attribution.
- Hybrid and taxonomy-drift rows remain present with deliberate placeholders and no parent inference.
- Unsafe host/hash/license/identity persists unavailable and never activates a URL.
- Interrupted batch resumes without duplicate lookup or row; second apply performs zero work.
- Catalog/profile GET with no media tables performs zero writes/network and returns unavailable objects.
- Paging/search/filter changes stop prior playback and enforce one active call.

## Explicit exclusions

No binary storage/proxy/cache/transcode, autoplay, waveform generation, parent fallback, catalog GET discovery, scheduled bulk refresh, proprietary media source, or guarantee that every taxon has available media.
