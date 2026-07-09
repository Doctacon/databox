Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-decommission-motherduck-platform-support.md
Verdict: pass

# Review: MotherDuck platform decommission

## Target

The MotherDuck/Dive decommission implementation and closure records against:

- `.10x/tickets/done/2026-07-09-decommission-motherduck-platform-support.md`
- `.10x/specs/local-only-databox-platform.md`
- `.10x/specs/birding-trip-copilot.md`
- `.10x/evidence/2026-07-09-motherduck-platform-decommission.md`

## Findings

### Runtime review: pass

Runtime review found the supported execution path consistently local-only:

- settings expose the local `data/databox.duckdb` warehouse path and local SQLMesh gateway,
- dlt uses Quack without a MotherDuck destination branch,
- Dagster performs no MotherDuck bootstrap,
- MotherDuck Dive/preview artifacts and executable tests are removed,
- active runtime documentation and commands no longer advertise MotherDuck or Dives.

No runtime blocker was found.

### Initial closure blockers resolved

Initial closure review found two blockers:

1. The active `.10x/specs/birding-trip-copilot.md` still referred to a MotherDuck Dive, so active specification language conflicted with the local-only decommission.
2. The focused regression suite did not directly test the local-only settings contract.

Both were fixed:

- Active Dive references in the birding spec now name the local React/API product and local React app.
- `tests/test_settings.py` directly asserts that SQLMesh has only the `local` gateway/default and that both the gateway catalog and runtime database path resolve to `data/databox.duckdb`.

Follow-up review inspected these fixes. The focused command
`uv run pytest --no-cov -q tests/test_settings.py tests/test_source_registry.py tests/test_quack_destinations.py`
passed all 18 tests.

## Verdict

Pass. The runtime review passed, both initial closure blockers were resolved, and follow-up inspection plus 18 passing focused tests support closure.

## Residual risk

Focused pytest still emits a non-failing SQLMesh analytics shutdown logging warning. Live source ingest and a long-running Dagster UI smoke were not run; these remain outside this decommission ticket's focused validation and are recorded in the evidence limits.
