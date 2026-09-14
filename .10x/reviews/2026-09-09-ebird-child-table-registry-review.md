Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Target: 4ce3746..d5fce6f
Verdict: pass

# eBird normalized child-table registry review

## Findings

No unresolved findings. The initial implementation correctly declared and classified the three tables but inferred generated-child status from `__`, which could hide a typo or orphan. Commit `d5fce6f` replaced that heuristic with explicit `Source.normalized_child_tables` ownership.

## Verdict

Pass. The eBird registry declares exactly the three authorized normalized children. Registry validation requires an exhaustive child subset, valid dlt child syntax, and a real top-level parent resource, while rejecting duplicates, absent children, or undeclared `__` tables. Source/resource bidirectional coherence remains protected. The tables are explicitly raw-only in taxonomy and DBML, absent from modeled ontology fields, and still included in recovery validation. No SQLMesh/CDM consumption or noncanonical USFWS/probe policy was added.

## Residual risk

Runtime dlt ingestion was not re-executed; focused implementation evidence reports 148 passing tests and all static/modeling/codegen checks. A live recovery rerun remains separately authorized. Noncanonical USFWS/probe classification remains blocked in `.10x/tickets/done/2026-09-09-classify-noncanonical-restored-catalog-state.md`.
