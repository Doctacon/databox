# Rufous operations

Application-only commands and operator procedures live here so the warehouse
command reference and runbook remain focused on data-platform work.

## Agent evaluations

```bash
task eval:agent
```

This runs the deterministic DeepEval suite at
`tests/evals/test_birding_trip_copilot_deepeval.py`. The target opts out of
DeepEval telemetry, keeps the cache under the ignored `.cache/` tree, disables
browser opening, and sets `PYTEST_ADDOPTS=--no-cov` so the focused eval run is
not affected by the repository-wide coverage gate. It uses a fake model client
and makes no live Cloudflare request.

Opt in to the three live credential/model schema checks with:

```bash
task smoke:cloudflare-ai
```

The smoke command makes one bounded request for each trip-plan, target-bird,
and watched-report structured-output contract. It uses only
`@cf/zai-org/glm-4.7-flash` and never prints Cloudflare credentials.

## Rufous local birding app

```bash
task app:dev           # FastAPI :8000 + Vite :5173 with hot reload
task app:check         # typecheck + tests + build + configured bundle audit
task app:audit-bundle  # audit an existing build for configured names and values
task app               # build and serve the complete app at http://127.0.0.1:8000
```

Both launch paths bind to loopback. On a new database, follow the README's
one-time AVONET bootstrap and run `task full-refresh` to populate the local
warehouse. `task verify` is only a bounded smoke refresh. Rufous uses an original
local rust-orange/teal field-device theme with no remote fonts or theme assets. The Trip Planner remains at `/`; the read-only Arizona Birds
catalog is available at `/birds`, with direct modeled profiles at
`/birds/{species_code}`. Native browser history supports direct reload,
back, and forward without a routing dependency. Catalog search, species/hybrid
filtering, and 24-row pagination operate entirely on the bounded 706-row API
snapshot; profile pages use only persisted modeled facts and public Arizona
locations, with no request-time discovery or mutation. A public modeled location
whose name includes `(private)` is shown with an access-restriction warning;
eBird's modeled privacy flag, not the display-name suffix, governs observation
privacy. The private local collection UI is available at `/my-birds` with Life
List, Observations, and Watches surfaces. Species profiles expose only explicit
observation and watch mutations. Watch centers are per-watch Arizona selections;
the browser stores no global home location, and none of these controls evaluate
matches or trigger weather, model, calendar, or SMTP work.

Catalog photo/call metadata is populated only by an explicit local batch. Inspection is
read-only and performs no discovery:

```bash
uv run --no-sync python scripts/catalog_media.py --inspect
```

Before apply, check Xeno-canto readiness without printing the credential value:

```bash
uv run --no-sync python scripts/catalog_media.py --check-prerequisites
# {"xeno_canto_api_key_configured": true}
```

Apply and refresh fail before creating tables or rows when `XENO_CANTO_API_KEY` is absent.
After independent review, run one bounded sequential checkpoint while the API, Quack,
and SQLMesh writers are stopped:

```bash
uv run --no-sync python scripts/catalog_media.py --apply --batch-size 25
uv run --no-sync python scripts/catalog_media.py --refresh --batch-size 25
```

Apply resumes missing exact identities; refresh resumes one explicit refresh campaign.
Neither command stores media bytes. Catalog GETs never invoke these commands or media
providers and return typed unavailable metadata until enrichment is complete.

The local personal-collection API stores runtime-owned tables in
`birding_personal` inside the same DuckDB file. It exposes observation CRUD at
`/api/observations`, the derived `/api/life-list`, per-species `/api/watches`,
and `/api/birds/{species_code}/collection-state`.
Observation deletion requires `confirm=true`; life-list membership is never an
independent stored flag. Collection reads are network-free, and collection
mutations do not evaluate watches or call weather, models, calendar, or SMTP.

Each current bird profile links to `/birds/{species_code}/find`. Target planning
requires an Arizona origin, 1–300-mile radius, local start, and 1–1440-minute
duration. `POST /api/target-plans` ranks at most ten exact-species valid,
reviewed, non-private public eBird locations with Haversine distance, then calls
Open-Meteo and the sole strict-schema GLM 4.7 Flash model before atomically persisting
the result. `GET /api/target-plans` and `GET /api/target-plans/{id}` replay only
persisted facts without network access or writes. Direct result routes use
`/target-plans/{id}`. Target plans never read personal collection state or
change the existing Trip Planner.

The shared `full-refresh` path evaluates active watches only after all source
loads and SQLMesh transformation succeed and release warehouse ownership.
Evaluation uses exact species/submission identity, the watch activation boundary,
a 48-hour freshness window, reviewed valid non-private public locations, and the
per-watch 1–300-mile radius. It persists deterministic decisions, at most ten
ranked public clusters, the earliest sunrise-centered two-hour morning, optional
strict-schema GLM 4.7 Flash emphasis, and stable-UID event intent in `birding_alerts`.
The GLM prompt contains only target identity, the confirmed public destination
and derived distance, morning, weather, caveats, and fact grounding—never the
personal watch-center name or coordinates. Model/weather failure degrades to
explicit persisted facts; it does not select an alternate model or send SMTP.
Cancellation handoffs become a cancel intent only for the same accepted,
unexpired watch activation. `GET /api/watch-evaluations`,
`GET /api/watch-reports`, and `GET /api/watch-reports/{id}` replay bounded local
state without network access or writes.

Every sendable REQUEST/CANCEL event intent now atomically creates one canonical
`birding_alerts.alert_outbox` row keyed by stable UID, sequence, and method. Only
exact `pending_request`/`REQUEST` and `pending_cancel`/`CANCEL` pairs qualify;
event/report species, watch activation, windows, horizon, and coherent public
location identity/metadata must match before enqueue. Pre-release intent tables
are transactionally rebuilt with explicit source-report/location linkage, and an
unrecoverable sendable row fails rather than being guessed. Persisted payload
JSON contains only validated calendar facts and its SHA-256;
organizer, recipient, SMTP configuration, MIME bytes, and full message bodies are
never stored. Pure builders add organizer/attendee only in memory and produce
RFC 5545/5546 calendar plus deterministic multipart calendar MIME. Atomic claims,
pre-send lease recovery, post-send `delivery_unknown`, supersession, terminal
suppression, append-only safe attempt facts, and 90-day payload cleanup are local
state mechanics only. Bird-alert outbox construction, suppression, and
reconciliation never open an SMTP connection or send mail. Transport is
implemented separately and runs only through the explicit operator commands
documented below; application startup, watch evaluation, and background refresh
never invoke it automatically.

Trip Planner eBird evidence is independently constrained in its SQLMesh view and
Python lookup to valid, reviewed, non-private rows. To inspect or remediate saved
plans created before that boundary, stop the API and refresh writers and run:

```bash
uv run --no-sync python scripts/remediate_trip_planner_ebird_privacy.py --inspect
uv run --no-sync python scripts/remediate_trip_planner_ebird_privacy.py --apply
```

The inspect command is read-only and emits aggregate counts only. Apply performs
no source, weather, model, or media call; it atomically removes every complete
saved-plan aggregate joined by authoritative eBird source-record identity to an
ineligible row. It fails closed when an identity cannot be verified and is safe
to rerun.

The browser calls `/api/*`; only the Python process can access
DuckDB or Cloudflare credentials. After any standalone build, the copy-pasteable
`task app:audit-bundle` command checks the compiled files for all configured
Cloudflare variable names and non-empty local values without printing secrets.
The version-locked MapLibre renderer is emitted as a same-origin, content-hashed
asset and loaded only when a valid map can be shown. Production static responses
of at least 1 KiB are gzip-compressed when the client supports it, and only
content-hashed assets receive a one-year immutable cache policy; no map runtime
is fetched from a CDN.

Location autocomplete calls Open-Meteo geocoding through the local Python API;
the browser never calls the upstream service directly. Search results and manual
coordinates are restricted with a compact official US Census TIGERweb-derived
Arizona polygon because the current bird evidence is Arizona-scoped. A missing
negative longitude such as `34.54,112.50` is rejected
before weather, evidence, model, or persistence work; valid Arizona coordinates
such as `34.54,-112.50` remain available when geocoding is unavailable. Selected
location identity and all completed plan artifacts persist in the single local
`data/databox.duckdb` warehouse.

GBIF planner evidence is conformed to the eBird-first species dimension by an
authority-free scientific-name key, so available common names lead result cards
while the scientific name remains visible underneath. Open-Meteo measurements
are reloaded from the persisted trip-plan evidence payload and displayed in both
US customary and metric units; the browser does not refetch or ask the model to
convert weather values.

Trip Planner recommendations are evidence prominence, not encounter probability.
Species with distinct eBird submissions in the configured eBird lookback (30
days back by default, with both boundary dates included) form the recently
reported group, ranked by eligible submission count, newest report, then species
name. Species without qualifying eBird submissions in that lookback but supported
by GBIF records form the occurrence-context group, ranked by distinct occurrence
count, newest occurrence date or year, then species name. Each source record
counts once. The planner trace records the exact inclusive date range; all eBird
and GBIF evidence used for ranking is within the enforced 50 km radius.

Xeno-canto metadata, URLs, recordist attribution, and licenses are reloaded from
persisted DuckDB evidence. The API exposes a separate typed media projection and
activates source/audio URLs only for exact HTTPS Xeno-canto hosts, matching
recording IDs, and expected `/{id}` or `/{id}/download` paths. The React app uses
native audio controls with `preload="none"` and no autoplay. Audio bytes stream
directly from Xeno-canto only after user interaction; Rufous does not proxy,
download, cache, or store audio.

Existing persisted recommendations are enriched only by an explicit local
maintenance command. Stop source refresh and the local API writer first, inspect
the bounded target set, then apply once:

```bash
task media:backfill -- --dry-run
task media:backfill -- --apply
```

Dry-run opens `data/databox.duckdb` read-only and performs no discovery. Apply
uses DuckDB's single-writer transaction and the same validated GBIF/Xeno-canto
selector used for new plans. It inserts only missing photo/call JSON metadata,
including durable unavailable results; a one-time compatibility repair replaces
only exact `media_backfill_v2_` GBIF rows having the defective unavailable status
and caveat from before the reviewed HTTP-license and `United States of America`
normalization fix. It does not invoke the model,
alter plan content, or download/proxy media bytes. Re-running apply is a no-op after
every recommendation has one current photo and one call result. `--database-path` may target a
test copy; it does not create a missing database.

## Bird alert delivery operations

No live bird-alert mail is sent by application startup, GET requests, watch
changes, refresh/watch evaluation, outbox construction, My Birds reconciliation
or cleanup actions, or tests. Rufous has no scheduler or background mail worker.
SMTP runs only when an operator invokes one of these commands; output is bounded
and never includes host, port, identities, certificate paths, or credentials.

```bash
# Open and authenticate a loopback STARTTLS connection using exact public-
# certificate trust and hostname verification, without calling send.
uv run --no-sync python scripts/verify_bird_alert_smtp.py --preflight

# Attempt delivery for at most one due persisted outbox row.
uv run --no-sync python scripts/deliver_bird_alerts.py

# Explicit live sends; each verification kind is durably limited to one attempt.
uv run --no-sync python scripts/verify_bird_alert_smtp.py --test-email
uv run --no-sync python scripts/verify_bird_alert_smtp.py --test-invitation
```

A transient failure persists `next_attempt_at`, but no process dispatches it
automatically; rerun the delivery command after it becomes due. Each invocation
handles at most one row. `delivery_unknown` is never automatically resubmitted
and requires explicit reconciliation. The SMTP boundary accepts only a numeric
loopback host, STARTTLS, one exact public CA certificate, and an organizer equal
to the authenticated username. An `accepted` result means only that the local
Bridge accepted the message, not that an inbox received or a calendar rendered
it.

My Birds → Alert Delivery shows safe local status and only state-derived actions. Active
ambiguous results can be marked not delivered and retried with a greater sequence;
suppressed/inactive ambiguous results can only be terminally marked not delivered, without
retry, or marked delivered so Rufous enqueues a coherent cancellation. Ambiguous results
are never automatically resent. SMTP acceptance means accepted by the local Bridge, not proof of
inbox receipt or calendar rendering. Resolved history expires after 90 days; unresolved
ambiguous rows remain until reconciliation.

## Trip-plan calendar invitations

Trip invitations are enqueued and, when SMTP is configured, attempted only by a
confirmed `POST` to
`/api/trip-plans/{plan_id}/calendar-invite?confirm=true`. Confirmed retry and
not-delivered reconciliation actions may also attempt their replacement
immediately. Plan creation, application startup, replay, and all `GET` routes
are status-only and never send.
The action reuses the server-only `BIRD_ALERT_SMTP_*` loopback STARTTLS settings;
no recipient or transport value is returned by the API.

Apply `migrations/20260711_trip_plan_calendar.sql` for an offline migration. The
same additive DDL is applied idempotently by the first explicit invite mutation.
Trip tables use only `trip_plan_id`; they never fabricate watch, species, or
activation-generation relationships.

An `accepted` status means **Accepted by local mail bridge**, not confirmed inbox
or calendar delivery. A `delivery_unknown` row must be reconciled explicitly with
mark-delivered or mark-not-delivered-and-retry. Never resend it automatically.
Failed retries and not-delivered reconciliation atomically supersede the old row,
regenerate the canonical plan with the stable UID and a greater sequence, and immediately
claim/send the replacement through the confirmed reconciliation API. Transient rows are
scheduled at 1, 5, and 15 minutes; an operator or local worker must invoke confirmed
`POST /api/trip-calendar-deliveries/deliver-due?confirm=true` at or after `next_attempt_at`
to claim and send at most one due row. No worker is bundled. This endpoint never
claims `delivery_unknown`; those rows remain manual-reconciliation-only. Resolved
non-current rows may be cleaned after 90 days; the current intent/action and
unresolved unknown rows are retained.

Feature verification must use an injected fake SMTP transport. The prior bounded
live Bridge authorization is exhausted; do not run another live verification
without a new explicit authorization.
