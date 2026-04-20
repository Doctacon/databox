---
id: evidence:schema-drift-proof-20260420
kind: evidence
status: active
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-20T00:00:00Z
scope:
  kind: workspace
links:
  ticket: ticket:source-test-harness
---

# Schema-Drift Proof

Proves the source-test-harness catches a schema change in an eBird dlt resource
and surfaces a clean, human-readable diff. Required by `ticket:source-test-harness`
acceptance criteria: *"Introducing a breaking change to a resource schema fails
the snapshot test with a clear diff."*

## Method

1. Added a bogus `drift_column` (type `text`) to the `columns` hint of the
   `recent_observations` `@dlt.resource` in
   `packages/databox-sources/databox_sources/ebird/source.py`.
2. Ran `uv run pytest packages/databox-sources/tests/ebird/test_schema.py --record-mode=none -vv`.
3. Test failed with the diff below.
4. Reverted the source change.
5. Re-ran the full test suite: all 9 pass green.

## Observed Diff

```text
FAILED packages/databox-sources/tests/ebird/test_schema.py::test_ebird_schema_snapshot
  AssertionError: assert [+ received] == [- snapshot]
      ......
          ...
              nullable: true
    +       drift_column:
    +         data_type: text
            exotic_category:
         ...
```

Syrupy renders the diff with ambr-style `+`/`-` markers. The added column is
marked with `+` and appears in the correct table (`recent_observations`).

## Verification After Revert

```text
============================== 9 passed in 2.84s ==============================
```

## Interpretation

The snapshot test catches added columns, dropped columns, or retyped columns.
A reviewer seeing this diff in CI would know immediately whether the change is
intentional. If intentional, re-run the test with `--snapshot-update` to accept
the new schema.
