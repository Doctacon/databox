Status: recorded
Created: 2026-09-08
Updated: 2026-09-08
Target: 1bec4ea
Verdict: pass

# Isolated restore volume-race repair review

## Findings

None.

## Verdict

Pass. The P1 from `.10x/reviews/2026-09-08-isolated-restore-runner-review.md` is repaired.

The execute path generates a 32-byte cryptographically secure per-run token, applies it as a target-volume ownership label, then inspects and exact-compares that label before any container mount. Pre-existing, unlabeled, or mismatched targets are refused without `docker run`, deletion, or cleanup. Prepare-only remains nonmutating and token-free. Tokens and secret values are absent from user output and errors. Existing no-active-volume, no-socket, no-port, no-bootstrap, no-archive-write, no-delta, no-cutover, and preserve-on-failure properties remain intact.

## Residual risk

No live restore has run. Restored PostgreSQL/Polaris startup, catalog validation, PITR behavior, and achieved RPO/RTO remain unproven and separately gated.
