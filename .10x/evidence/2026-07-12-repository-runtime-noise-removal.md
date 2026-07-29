Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-remove-repository-runtime-noise.md

# Repository runtime noise removal

## What was observed

The repository tracked exactly three Task runtime checksum files:

- `.task/checksum/install`
- `.task/checksum/install-dev`
- `.task/checksum/install-orchestration`

`.pi-subagents/` repeatedly appeared as untracked local worker output, and
`.deepeval/` was an unignored runtime directory even though DeepEval cache is
configured under ignored `.cache/deepeval`. No repository-native ignore/hygiene
test surface was found; existing references only cover secret-scan guidance and
DeepEval cache configuration.

## Change

`.gitignore` now ignores only these local runtime roots:

- `.task/`
- `.pi-subagents/`
- `.deepeval/`

The three tracked checksum cache files are deleted. No other `.task` path was
tracked or removed. The local `.task` directory became empty and was removed.

## Procedure and results

- Pre-change `git ls-files '.task/**'` returned exactly the three checksum files
  above.
- `git check-ignore -v` resolves probe paths to the three new exact directory
  rules at `.gitignore:66-68`.
- Tracked-authority preservation scan using `git check-ignore --no-index`:
  - `.pi/skills`: 5 tracked, 0 ignored;
  - `.schema`: 11 tracked, 0 ignored;
  - `.10x`: 492 tracked, 0 ignored;
  - `docs/dictionary`: 20 tracked, 0 ignored.
- `git diff --name-status -- .gitignore .task` shows one `.gitignore`
  modification and exactly the three intended checksum deletions.
- Unexpected tracked deletion scan returned zero paths.
- `git diff --check` passed.
- `git diff --cached --name-only` was empty.

No automated test was added because the repository has no existing hygiene-test
surface and the contract is completely exercised by repository-native Git
ignore/tracked-path assertions.

## What this supports

This supports the ticket criteria: the commit candidate removes all tracked
Task checksum cache files, ignores Task/subagent/DeepEval runtime state, and
preserves every named tracked authority without changing Task behavior.

## Limits

The deleted paths remain present in Git's index as deletions until the parent
commits the aggregate change; after that commit, no `.task/checksum/*` path will
remain tracked. Git ignore behavior does not delete any developer-local runtime
file that may be recreated later. No Task command, test, build, provider,
warehouse, SQLMesh, Rufous, staging, commit, or push operation occurred.
