Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Target: .10x/tickets/done/2026-07-09-add-avonet-bird-traits-source.md
Verdict: pass

# AVONET bird-traits source review

## Target

Pinned AVONET v7 download, parsing, dlt/Quack staging, atomic publication, source schema/ontology/docs, orchestration, and tests governed by `.10x/specs/avonet-bird-traits-source.md` and `.10x/decisions/avonet-atomic-staged-publication.md`.

## Findings

- Exact initial Figshare URL and one signed S3 redirect are manually and finitely validated; automatic/further redirects, unsafe URL fields, invalid signing scope, oversized/wrong-length/wrong-hash responses, and signed-URL disclosure fail closed.
- Only the exact hash-pinned `AVONET2_eBird` worksheet reaches strict 31-column parsing. Row/type/null/bounds and independent Avibase/scientific-name uniqueness are enforced; temporary artifacts are removed.
- Raw schema exposes exactly 38 business/provenance columns plus dlt row metadata with documented units/codebooks/global scope/DOI/version/license.
- AVONET is independently runnable with no schedule, shared parallel-refresh membership, or default platform-health dependency.
- Initial review found production `prepare_dlt_source` changed declared replacement to append. Final architecture loads through Quack only into transient staging, stops Quack, validates the complete physical snapshot, and transactionally publishes final `raw_avonet` business/dlt metadata with rollback and staging cleanup.
- Production tests prove repeated-success idempotency, true changed-snapshot replacement, removal of old rows, prior-snapshot preservation across extraction/load/validation/mid-publish failures, first-run failure behavior, crash-residue cleanup, and absence of staging or persistent `main._dlt*`.
- 105 focused tests and a real temporary 10,661-row production lifecycle passed with Ruff, MyPy, schema/docs drift, strict docs, secret, pre-commit, and diff checks.
- The order-dependent legacy source VCR isolation defect predates this change and is durably owned by `.10x/tickets/2026-07-10-repair-source-vcr-and-schema-snapshot-suite.md`.
- The original accepted source decision is preserved under `decisions/superseded/`; the new active atomic-publication decision owns the changed architecture and all references are coherent.

## Verdict

Pass. No AVONET source blocker remains.

## Residual risk

Figshare may change its exact signed storage redirect contract; this will fail closed and require a reviewed source-compatibility decision rather than broadening hosts automatically.
