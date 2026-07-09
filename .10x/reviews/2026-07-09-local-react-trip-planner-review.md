Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-build-local-react-trip-planner.md
Verdict: pass

# Local React Trip Planner adversarial review

## Target

The local FastAPI contract, React product surface, launch paths, tests, and evidence governed by `.10x/specs/local-birding-trip-copilot-app.md`.

## Assumptions tested

- The browser cannot query DuckDB or receive Cloudflare configuration.
- Plan creation uses the existing ADK planner and reads success from persisted artifacts.
- Input, provider, and DuckDB failures return bounded user-safe messages.
- The UI includes the complete Trip Planner surface without restoring a generic explorer.
- External media metadata cannot create an unsafe executable link.
- Development and built launch paths bind only to loopback.
- Tests remain deterministic without paid inference.

## Findings

### Resolved during review

1. **Significant — unsafe persisted media URLs could have been activated.** `app/src/App.tsx` originally trusted the persisted recording URL as an anchor target. The implementation now permits only HTTPS `xeno-canto.org` and subdomain URLs; a deterministic UI test rejects a `javascript:` value.
2. **Minor — Taskfile dependency names containing colons were invalid YAML scalars.** The dependency values are now quoted. The YAML pre-commit hook and `task app:check` pass.
3. **Minor — whitespace location and zone-qualified timestamps did not precisely express the local timestamp contract.** The API now rejects whitespace-only locations and requires a timezone-naive local ISO timestamp; tests cover both.
4. **Minor — generated TypeScript build metadata appeared as untracked artifacts.** `*.tsbuildinfo` is ignored while source and lock files remain tracked.

### Resolved after independent follow-up review

5. **Significant — persisted Xeno-canto recordist attribution was not rendered.** Media rows now render the persisted recordist from the evidence payload together with the Xeno-canto source, license, and safe recording link; a rendered-DOM test asserts the complete attribution.
6. **Significant — the unavailable Xeno-canto sentinel was exposed as a media item.** The API now includes only `status = available` Xeno-canto evidence in `media` while retaining the sentinel in `evidence`; the UI also filters defensively and tests the explicit unavailable-media state.
7. **Significant — browser-facing detail queries used `SELECT *` and success responses were untyped.** All browser-facing queries now project explicit fields into Pydantic response models. Exact-key contract assertions cover health, list, create, detail, and error responses, including nested recommendation/evidence/trace shapes.
8. **Minor — the bundle secret audit was evidence prose rather than a reusable command.** `task app:audit-bundle` runs `scripts/audit_app_bundle.py`, checking the compiled bundle for all three configured Cloudflare names and every non-empty configured value without printing secrets. Unit tests cover pass, name/value detection, and missing-build behavior.
9. **Significant — health readiness accepted arbitrary nonempty Cloudflare configuration.** `GET /api/health` now uses `CloudflareWorkersAIClient.from_settings` for the same strict local account/host/model-selector validation as runtime construction. Injected deterministic clients are ready only for the exact allowlisted model ID. Tests cover arbitrary-host and malformed-account degradation, both approved configuration forms, and exact/wrong injected model IDs. The endpoint performs no inference and retains only the stable three-field response.

### Open findings

None.

## Verification inspected

- Deterministic API create/list/detail persistence, strict health readiness, unavailable-media, exact-shape, and error tests: 9 passed.
- Executable configured bundle-audit tests: 3 passed.
- Rendered React product, attribution, unavailable-media, URL-safety, and state tests: 6 passed.
- Frontend strict typecheck and Vite production build: passed.
- `task app:audit-bundle`: passed for 3 names and 3 configured values.
- Built loopback health and HTML requests: passed.
- Full Python CI: 189 passed with 82.01% coverage.
- Strict documentation build and all pre-commit hooks: passed.
- `git diff --cached --quiet`: no staged files.

## Verdict

Pass. No blocker remains for this child ticket. The aggregate verification ticket still owns full-product refresh, SQLMesh, live-smoke retry/external limitation recording, and final parent closure.

## Residual risk

The UI evidence is deterministic rendered DOM rather than cross-browser pixel comparison. This is proportionate for the local first version and does not leave an uncovered behavioral criterion.
