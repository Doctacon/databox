Status: done
Created: 2026-09-02
Updated: 2026-09-02
Parent: None
Depends-On: None

# Pause Rufous public production deployment

## Scope

Fail closed by disabling only the `production` deployment job in `.github/workflows/rufous-public.yaml` while retaining pull-request validation, synthetic checks, Pages shell behavior, and manual media maintenance workflows.

## Acceptance criteria

- The production job can never run from push, schedule, or workflow dispatch while paused.
- Existing non-production validation and maintenance jobs remain unchanged.
- The workflow records why production is paused and the condition for restoration.
- A focused test guards the disabled production condition.

## Explicit exclusions

- Repairing the Iceberg-based public release build.
- Deleting the production job or changing its release semantics.
- Modifying the currently deployed Pages/R2 release.

## References

- `.github/workflows/rufous-public.yaml`
- `docs/rufous-public-release.md`

## Progress and notes

- 2026-09-02: User ratified disabling only production deployment while preserving validation and maintenance paths.
- 2026-09-02: Set the production job condition to the literal fail-closed `${{ false }}` with the restoration condition documented inline. Added a focused regression assertion; all 11 public-workflow tests, Ruff, and `git diff --check` passed.

- 2026-09-02: Final adversarial closure review passed. Evidence and the exact workflow regression establish the fail-closed pause; no follow-up remains until a separately authorized restoration.

## Blockers

None.
