Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-verify-local-birding-product.md, .10x/tickets/2026-07-09-build-local-birding-copilot-product.md, .10x/tickets/2026-07-09-resolve-cloudflare-workers-ai-live-inference-timeout.md

# Local Birding Trip Copilot aggregate verification

## What was observed

The local-only product passed a fresh production-sized source refresh, SQLMesh production materialization/state checks, all production Soda contracts, Python CI, offline agent evaluation, React checks/build, API controlled persistence/reload tests, compiled-bundle audit, built loopback launch, documentation build, active MotherDuck/Dive audit, and repository integrity checks.

The one opt-in live Cloudflare request again reached the configured fixed Cloudflare route but ended in the client's bounded timeout before a model response. This external availability/entitlement risk is owned by `.10x/tickets/2026-07-09-resolve-cloudflare-workers-ai-live-inference-timeout.md`. No fallback model or credential disclosure occurred.

## Procedure and results

### Shared-server Quack full refresh and SQLMesh production refresh

Command:

```text
task full-refresh
```

Result: passed. Durable log: `.logs/full-refresh-20260709-132711.log`.

The refresh launched all six registered Dagster source jobs as hermetic clients under one `parallel_quack_refresh` server context. The log recorded all six source starts within 16 milliseconds, all six successful source ends, and all 15 possible pairwise overlaps from actual `quack_ingest_session` intervals. The implementation has one `with server_factory(target)` lifecycle around the concurrent client pool; the one-server/failure lifecycle is also covered by the passing aggregate CI tests.

Actual ingest durations reported by the log:

- eBird: 115.345 seconds
- GBIF: 5.683 seconds
- Xeno-canto: 8.765 seconds
- NOAA: 38.404 seconds
- USGS: 2.560 seconds
- USGS earthquakes: 0.563 seconds

Post-deduplication core raw counts:

- `raw_ebird.recent_observations=389`
- `raw_ebird.notable_observations=2143`
- `raw_ebird.hotspots=2912`
- `raw_ebird.species_list=706`
- `raw_gbif.occurrences=1000`
- `raw_xeno_canto.recordings=1000`
- `raw_noaa.daily_weather=28061`
- `raw_noaa.stations=1720`
- `raw_usgs.daily_values=6243`
- `raw_usgs.sites=204`
- `raw_usgs_earthquakes.events=506`

The live refresh reported `main_dlt_relations=0`, removed `data/.quack-clients`, and invoked native SQLMesh only after every source succeeded. SQLMesh applied 16 model batches and finalized the `prod` environment.

Commands:

```text
cd transforms/main && ../../.venv/bin/sqlmesh test
cd transforms/main && ../../.venv/bin/sqlmesh info && ../../.venv/bin/sqlmesh diff prod
```

Results:

- 10 SQLMesh tests passed against DuckDB.
- SQLMesh reported 16 models; warehouse and state connections succeeded.
- Project files matched `prod` with no pending changes.

### Production quality and source-layout checks

A non-mutating Python invocation executed `ContractVerificationSession` for every `soda/contracts/**/*.yaml` file against the configured local DuckDB datasource using the same API as Dagster's asset checks.

Exact corrected command:

```bash
uv run --no-sync python - <<'PY'
from pathlib import Path
from soda_core.common.yaml import ContractYamlSource, DataSourceYamlSource
from soda_core.contracts.contract_verification import ContractVerificationSession
from databox.config.settings import settings
paths = sorted(Path('soda/contracts').rglob('*.yaml'))
failed = []
checks = 0
for path in paths:
    result = ContractVerificationSession.execute(
        contract_yaml_sources=[ContractYamlSource.from_str(path.read_text())],
        data_source_yaml_sources=[DataSourceYamlSource.from_str(settings.soda_datasource_yaml)],
    )
    checks += result.number_of_checks
    if result.is_failed:
        failed.append(str(path))
print(f'contracts={len(paths)} checks={checks} failed={len(failed)}')
if failed:
    raise SystemExit(1)
PY
```

Result: `contracts=23 checks=104 failed=0`. This included raw eBird/NOAA contracts, all environmental-observations CDM contracts, all four birding-agent planner interfaces, and analytics platform health.

Commands:

```text
uv run --no-sync python scripts/check_source_layout.py
uv run --no-sync python scripts/generate_platform_health.py --check
uv run --no-sync python scripts/generate_staging.py --check
```

Results: six source layouts passed; platform-health and staging generated artifacts matched their sources.

The first ad hoc contract-loop attempt used a non-existent result attribute and exited before evaluating the contracts. The corrected invocation used the repository's actual `result.is_failed` API and produced the 23/23 result above; this was a verifier-command correction, not a product failure.

### Python CI and offline agent evaluation

Command:

```text
task ci
```

Result: passed.

- Ruff check passed.
- Ruff format check passed for 104 files.
- MyPy passed for 70 source files.
- 183 tests passed.
- Coverage was 81.78%, above the 70% gate.
- Secret scan passed.
- Staging and platform-health drift checks passed.

Command:

```text
task eval:agent
```

Result: two DeepEval scenarios passed at 100% with no token cost. The golden and sparse-source scenarios used deterministic fake/no-op model clients, verified the exact bounded tool sequence, persisted evidence, unavailable-source caveats, no personal-history assumptions, and no fallback from `@cf/zai-org/glm-4.7-flash`. No live inference was performed.

### React, API, controlled persistence/reload, and bundle security

Commands:

```text
task app:check
task app:audit-bundle
uv run --no-sync pytest --no-cov -q tests/test_api.py tests/test_audit_app_bundle.py
```

Results:

- Strict TypeScript check passed.
- Six Vitest/jsdom product tests passed.
- Vite built 28 modules; JavaScript bundle was 154.47 kB (49.42 kB gzip).
- The executable bundle audit passed: all three Cloudflare configuration names and all three configured values were absent from compiled browser assets.
- Three API tests and three audit tests passed.

The API suite is the controlled end-to-end scenario: it uses a deterministic fake model and fake Open-Meteo response, creates a plan through `POST /api/trip-plans`, reloads persisted `birding_agent.*` data through detail/list endpoints, asserts the reloaded detail exactly equals the create response, and verifies recommendations, weather, evidence/media attribution, and tool traces. It also covers invalid input, model timeout/unavailability, empty history, missing plans, and database-busy handling.

The exact corrected built-loopback request harness was:

```bash
set -euo pipefail
log=$(mktemp /tmp/databox-uvicorn.XXXXXX.log)
health=$(mktemp /tmp/databox-health.XXXXXX.json)
index=$(mktemp /tmp/databox-index.XXXXXX.html)
uv run --no-sync uvicorn databox.api:app --host 127.0.0.1 --port 8765 >"$log" 2>&1 &
pid=$!
cleanup() { kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; rm -f "$log" "$health" "$index"; }
trap cleanup EXIT
for _ in $(seq 1 50); do
  if curl --fail --silent http://127.0.0.1:8765/api/health >"$health"; then break; fi
  sleep 0.2
done
HEALTH="$health" uv run --no-sync python - <<'PY'
import json, os
from pathlib import Path
health = json.loads(Path(os.environ['HEALTH']).read_text())
assert set(health) == {'status', 'database_ready', 'model_ready'}
assert health['database_ready'] is True
assert health['model_ready'] is True
print('health_shape=ok database_ready=true model_ready=true')
PY
curl --fail --silent http://127.0.0.1:8765/ >"$index"
grep -q 'Birding Trip Copilot' "$index"
echo 'static_page=ok title=Birding Trip Copilot'
```

Loopback requests proved the exact health shape, strict database/model readiness, and compiled Birding Trip Copilot page. The first shell harness used an unavailable unqualified `python` binary after the server had started; its trap stopped the server. The corrected harness above passed. This was a verifier-shell correction, not an application failure.

### Documentation and active-capability audit

Command:

```text
task docs:build
```

Result: generated 16 model pages plus lineage/index and completed strict MkDocs build. MkDocs emitted only its upstream Material/MkDocs 2.0 advisory and the existing informational list of generated dictionary pages not explicitly present in nav.

The exact bounded active-capability audit was:

```bash
set -euo pipefail
if rg -n -i 'motherduck|mother duck|\bdive(s)?\b' packages scripts app tests Taskfile.yaml .env.example pyproject.toml workspace.yaml --glob '!app/node_modules/**' --glob '!app/dist/**'; then
  echo 'active_capability_matches=found'
  exit 1
fi
uv run --no-sync python - <<'PY'
import re, subprocess
from pathlib import Path
pattern = r'motherduck|mother duck|\bdive(s)?\b'
result = subprocess.run(
    ['rg', '-l', '-i', pattern, 'README.md', 'docs', 'mkdocs.yml', '--glob', '!docs/dictionary/**'],
    check=False, capture_output=True, text=True,
)
files = {Path(line) for line in result.stdout.splitlines() if line}
allowed = {
    Path('README.md'), Path('docs/index.md'), Path('docs/adr/README.md'),
    Path('docs/adr/0004-per-source-raw-catalogs.md'),
    Path('docs/adr/0006-motherduck-as-cloud-path.md'), Path('mkdocs.yml'),
}
assert files <= allowed, sorted(str(path) for path in files - allowed)
for path in files:
    text = path.read_text()
    if path.name.startswith(('0004-', '0006-')):
        assert re.search(r'superseded|historical', '\n'.join(text.splitlines()[:10]), re.I), path
    else:
        for line in text.splitlines():
            if re.search(pattern, line, re.I):
                assert re.search(r'superseded|historical|legacy', line, re.I), (path, line)
print(f'active_capability_matches=0 historical_files={len(files)} classified=yes')
PY
```

Result: `active_capability_matches=0 historical_files=6 classified=yes`. No active commands/configuration advertised either capability. Remaining docs references are the explicitly superseded/historical ADR-0004/ADR-0006 and their indexes. Former `.dive-preview/`, `dives/`, browser SDK, and executable Dive tests remain deleted; terminal/superseded `.10x` records remain historical evidence.

### Secrets and repository integrity

`task ci` secret scanning passed, and `task app:audit-bundle` found no configured name/value in browser assets.

A separate value-only audit read the current local `.env` without printing it, then searched `.logs/` and `.10x/`. The exact command was:

```bash
uv run --no-sync python - <<'PY'
from pathlib import Path
MODEL = '@cf/zai-org/glm-4.7-flash'
names = ('CF_WORKERS_AI_API_KEY', 'CF_WORKERS_AI_ACCOUNT_ID', 'CF_WORKERS_AI_MODEL_BASE_URL')
values = {}
for line in Path('.env').read_text().splitlines():
    if not line or line.lstrip().startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    key, value = key.strip(), value.strip().strip('"\'')
    if key in names and value and not (key == 'CF_WORKERS_AI_MODEL_BASE_URL' and value == MODEL):
        values[key] = value
leaks = []
for root in (Path('.logs'), Path('.10x')):
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for key, value in values.items():
            if value.encode() in data:
                leaks.append((str(path), key))
print(f'sensitive_configured_values_checked={len(values)} log_record_leaks={len(leaks)} public_model_selector_excluded=yes')
if leaks:
    raise SystemExit(1)
PY
```

It checked the sensitive API-key and account-ID values and found zero matches. The configured base selector equals the public required model identifier, so that public identifier was deliberately excluded from the secret-value check; it necessarily appears in governing records. Result: `sensitive_configured_values_checked=2 log_record_leaks=0 public_model_selector_excluded=yes`.

Repository checks after record updates are captured in the verification ticket/review: `git diff --check` passed and `git diff --cached --quiet` confirmed no staged files. Generated `.pi-subagents/` review artifacts and Task checksum cache files were removed after review; ignored `.env`, `.venv/`, `data/`, `.dagster/`, and `.logs/` were preserved. Existing roadmap work was preserved.

After the final review found that `/api/health` could overstate readiness for malformed Cloudflare configuration, the owning React/API child was reopened and repaired. Health now uses the same strict client configuration validation, focused tests cover malformed-host and exact-model cases, and the post-repair `task ci` passed 189 tests at 82.01% coverage.

### Opt-in live Cloudflare smoke

Command, run exactly once during aggregate verification:

```text
task smoke:cloudflare-ai
```

Result: failed with the safe bounded `CloudflareTimeoutError` after reaching the configured fixed route. The traceback contained no credentials, endpoint value, response body, or chained transport details. The runtime did not select a fallback model. Earlier evidence records a successful HTTP 200 token verification and timeouts from both OpenAI-compatible and native model routes, so account/model response availability remains externally unproven rather than silently attributed to local correctness.

Durable owner: `.10x/tickets/2026-07-09-resolve-cloudflare-workers-ai-live-inference-timeout.md`.

## Acceptance mapping

- **All four implementation children:** each is `done`, references recorded evidence, and has a pass review with resolved findings.
- **One database/local-only platform:** settings/source-registry tests passed; fresh refresh, SQLMesh, API, and product use `data/databox.duckdb`; active MotherDuck/Dive audit passed.
- **Required Quack concurrency:** fresh live log proves six actual overlapping clients, all 15 overlap pairs, raw rows, cleanup, and no `main._dlt*`.
- **SQLMesh/quality:** production refresh passed; 10 SQLMesh tests and all 23/104 Soda contracts passed; `prod` has no pending diff.
- **Agent/model:** deterministic tests/evals prove the exact allowlisted model boundary, bounded structured action selection, deterministic factual rendering, and atomic persisted artifacts.
- **React/API:** controlled create/list/detail reload, frontend states/accessibility/media attribution, compiled build, and loopback launch passed.
- **Secrets/offline behavior:** CI/evals incurred no live inference; repository, browser bundle, logs, and records exposed no sensitive configured values.
- **Live model:** timeout is precisely recorded and durably owned; no fallback was used.

## Limits and residual risk

- Live inference from `@cf/zai-org/glm-4.7-flash` remains unproven because Cloudflare did not return a model response within the bounded timeout. The local product's model-dependent create action may therefore remain unavailable until the follow-up resolves provider/account availability.
- Quack is beta and dlt's unqualified metadata reads still depend on the tested transient union metadata views.
- UI verification is rendered-DOM plus a built static-page smoke, not a cross-browser pixel-regression suite.
- Source values and upstream response volumes are time-dependent; this evidence records the exact 2026-07-09 refresh rather than promising fixed counts.

## Retrospective extraction

No new reusable procedure or domain convention crystallized beyond existing source/verification records. The only unresolved operational learning is captured as the bounded Cloudflare timeout follow-up ticket rather than left in chat or this evidence alone.
