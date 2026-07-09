Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-build-local-react-trip-planner.md, .10x/specs/local-birding-trip-copilot-app.md

# Local React Trip Planner implementation evidence

## What was observed

The former Streamlit explorer was replaced by a strict-TypeScript Vite/React Trip Planner. A loopback FastAPI service now exposes health, persisted plan list, plan creation, and persisted plan detail endpoints. The create endpoint invokes the existing async Google ADK planner, permits one in-flight request, then reloads the completed result from `birding_agent.*` rather than returning transient model output.

The result UI renders the persisted field plan, high-likelihood and uncommon-plausible recommendations, weather/elevation, evidence status and provenance, Xeno-canto source/recordist/license/link attribution, plan and source caveats, and ordered tool traces. The browser receives no DuckDB connection or Cloudflare configuration. Xeno-canto links are activated only for HTTPS URLs on `xeno-canto.org` or its subdomains. Unavailable Xeno-canto sentinel evidence remains visible as provenance but is excluded from the `media` collection and renders the explicit unavailable-media state.

## Procedure and results

### Strict health readiness repair

The final aggregate review found that `GET /api/health` treated any three nonempty Cloudflare settings as model-ready, even when the account shape or configured host would be rejected by the runtime client. Health now constructs `CloudflareWorkersAIClient` through `from_settings` solely for its strict local configuration validation and catches only `CloudflareConfigurationError`; it never calls inference. When a deterministic client is injected, readiness is true only when its `model` exactly equals the single allowlisted model ID.

The focused API tests prove that an arbitrary HTTPS host and malformed account report the stable `{"status":"degraded","database_ready":true,"model_ready":false}` shape, both the exact model selector and approved HTTPS `api.cloudflare.com` configuration report ready, and injected exact/wrong model IDs report ready/degraded respectively. No credential, endpoint detail, validation reason, or provider response is added to the response.

### API contract and controlled end-to-end persistence

Command:

```text
uv run --no-sync pytest --no-cov -q tests/test_api.py
```

Result: 9 tests passed. The suite uses a deterministic fake model and fake Open-Meteo getter to create a plan, checks the persisted detail response, lists it, and reloads the identical detail by ID. Exact-key assertions cover health, list, create, detail, nested plan/recommendation/evidence/tool-trace records, and error responses. Strict health cases cover invalid host/account configuration, both approved configuration forms, and exact/non-allowlisted injected model IDs without inference. The suite also proves unavailable Xeno-canto sentinel evidence is retained in `evidence` but excluded from `media`, while an available persisted row retains recordist/license/link metadata. Bounded/forbidden-extra validation, whitespace rejection, local timestamp enforcement, stable timeout/model-unavailable responses without provider details, empty history, 404, and DuckDB busy handling remain covered.

Static validation:

```text
uv run --no-sync ruff check packages/databox/databox/api.py scripts/audit_app_bundle.py tests/test_api.py tests/test_audit_app_bundle.py
uv run --no-sync mypy packages/databox/databox/api.py scripts/audit_app_bundle.py tests/test_api.py tests/test_audit_app_bundle.py
```

Result: both passed.

### Frontend behavior and captured UI-equivalent evidence

Command:

```text
cd app && npm run typecheck && npm test && npm run build
```

Result: TypeScript passed; 6 Vitest/jsdom tests passed; Vite built 28 modules into `app/dist`. The rendered-DOM tests cover the complete persisted plan surface, semantic required form control, persisted Xeno-canto source/recordist/license/link attribution, caveats and tool trace, unavailable Xeno-canto evidence without a media item, rejection of a `javascript:` media link, bounded form submission, model-unavailable alert, database-busy alert, and empty history. These rendered-DOM assertions are the ticket's equivalent captured UI evidence.

Production bundle summary:

```text
dist/index.html                  0.49 kB (0.31 kB gzip)
dist/assets/index-*.css         4.86 kB (1.78 kB gzip)
dist/assets/index-*.js        154.47 kB (49.42 kB gzip)
```

### Browser secret audit

The copy-pasteable executable audit is:

```text
task app:audit-bundle
```

It runs `scripts/audit_app_bundle.py`, concatenates every compiled file in `app/dist`, and checks both the three environment variable names and their non-empty configured local values:

- `CF_WORKERS_AI_API_KEY`
- `CF_WORKERS_AI_ACCOUNT_ID`
- `CF_WORKERS_AI_MODEL_BASE_URL`

Result: `bundle configuration audit passed: 3 names and 3 configured values absent`. Three focused audit tests also passed, covering configured-name/value detection, a clean bundle, and a missing build.

### Loopback built-launch verification

The compiled app was launched with:

```text
uv run --no-sync uvicorn databox.api:app --host 127.0.0.1 --port 8765
```

Loopback `GET /api/health` returned only `status`, `database_ready`, and `model_ready`; `GET /` returned the compiled Birding Trip Copilot page. Both development services also explicitly bind to `127.0.0.1` in `scripts/run_local_app.py` and `app/package.json`.

Documented launch paths are:

```text
task app:dev
task app
```

`task app:check` completed `npm ci`, typecheck, 6 tests, the production build, and the configured bundle audit.

### Repository validation

```text
task ci
```

Result: 189 Python tests passed, total coverage 82.01%, Ruff passed, Ruff formatting passed for 104 files, MyPy passed for 70 source files, secret scan passed, and generated staging/platform-health checks passed.

```text
task docs:build
uv run --no-sync pre-commit run --all-files
```

Result: strict MkDocs build passed; all pre-commit hooks passed.

## What this supports

- The API contract and persisted-artifact boundary match `.10x/specs/local-birding-trip-copilot-app.md`.
- A controlled complete plan can be created and revisited without live model inference.
- User-visible busy, unavailable, invalid, loading, empty, and completed states have deterministic coverage.
- The browser bundle does not contain Cloudflare configuration names or configured values.
- Both supported launch paths remain local-only and the compiled frontend is served by the Python API.

## Limits

- Vitest/jsdom rendered-DOM assertions substitute for a pixel screenshot; no cross-browser visual-regression suite was introduced.
- Live Cloudflare response behavior remained outside this child ticket and was checked by `.10x/tickets/done/2026-07-09-verify-local-birding-product.md`; the continuing external timeout is owned by `.10x/tickets/done/2026-07-09-replace-cloudflare-model-with-glm-5-2.md`. Controlled model tests establish the local API/UI contract.
- The existing repository-wide `.env`, warehouse, logs, and earlier uncommitted roadmap changes were preserved and were not staged or committed.
