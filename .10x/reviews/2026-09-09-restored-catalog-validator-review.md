Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Target: 877b898..1c6bd66
Verdict: pass

# Restored catalog validator review

## Findings

No unresolved findings. The initial review found five fail-closed gaps: recovery-point source provenance, restored-container identity, elapsed timing, per-table request aggregation, and malformed identifier bounds. Commit `1c6bd66` repaired all five and added focused regression coverage.

## Verdict

Pass. The validator requires and resolves a source commit, proves its canonical registry bytes match the imported registry, gates execution on the running unexposed recovery-labeled Polaris container, keeps OAuth and vended credentials out of reports, aggregates bounded per-table failures, rejects malformed observed identifiers, and records elapsed time.

## Residual risk

The recovery label is operator-established rather than cryptographic. The authorized live run must use the exact preserved container and source revision. Hermetic tests cannot prove installed PyIceberg and vended S3 credential interoperability; live read-only validation is required. Existing evidence indicates the first run may correctly report catalog/registry drift.
