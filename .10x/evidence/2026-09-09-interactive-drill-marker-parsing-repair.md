Status: recorded
Created: 2026-09-09
Updated: 2026-09-09

# Interactive drill marker parsing repair

Before live mutation, review found that psql command tags could be mistaken for the `INSERT ... RETURNING` timestamp. Active SQL now uses quiet tuples-only mode, and marker parsing requires exactly one nonblank timezone-aware timestamp row. Empty, command-tagged, multiple, and malformed output fail boundedly. The combined CREATE+INSERT command remains unchanged.

Validation: 69 focused tests passed; Ruff check/format, MyPy, diff check, and scoped secret-pattern scan passed. No live command ran and `uv.lock` was untouched.
