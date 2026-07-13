from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import duckdb
from databox.agent_tools.recommendation_media_backfill import _inspect
from databox.catalog_media import _catalog, _valid_result_rows, curated_photo_result_from_row

DB = Path(sys.argv[1])
OUT = Path(sys.argv[2])
MOD = 1 << 256


def vb(v: Any) -> bytes:
    return repr(v).encode("utf-8", "backslashreplace")


def fp(c: duckdb.DuckDBPyConnection, q: str) -> dict[str, Any]:
    cur = c.execute(q)
    cols = [(x[0], str(x[1])) for x in cur.description]
    total = xor = count = 0
    while rows := cur.fetchmany(2048):
        for row in rows:
            n = int.from_bytes(hashlib.sha256(b"\x1f".join(vb(v) for v in row)).digest(), "big")
            total = (total + n) % MOD
            xor ^= n
            count += 1
    return {
        "columns": cols,
        "row_count": count,
        "sha256_multiset_sum": total.to_bytes(32, "big").hex(),
        "sha256_multiset_xor": xor.to_bytes(32, "big").hex(),
    }


with duckdb.connect(str(DB), read_only=True) as c:
    tables = c.execute("SELECT schema_name,table_name FROM duckdb_tables() ORDER BY 1,2").fetchall()
    protected = {}
    excluded = {
        "birding_catalog_media.results",
        "birding_catalog_media.photo_runs",
        "birding_agent.trip_plan_evidence",
    }
    for s, t in tables:
        key = f"{s}.{t}"
        if key not in excluded:
            protected[key] = fp(c, f'SELECT * FROM "{s}"."{t}"')
    protected["birding_catalog_media.results:call"] = fp(
        c, "SELECT * FROM birding_catalog_media.results WHERE media_kind='call'"
    )
    protected["birding_agent.trip_plan_evidence:nonphoto"] = fp(
        c,
        "SELECT * FROM birding_agent.trip_plan_evidence "
        "WHERE evidence_type IS DISTINCT FROM 'recommendation_photo'",
    )
    taxa = _catalog(c, expected_catalog_count=706)
    rows = _valid_result_rows(c, taxa)
    counts = {}
    valid = 0
    for taxon in taxa:
        current = [
            r
            for r in rows.get(taxon.species_code, [])
            if str(r[1]) == "photo" and curated_photo_result_from_row(r, taxon) is not None
        ]
        if len(current) == 1:
            valid += 1
            key = f"{current[0][4]}:{current[0][6]}"
            counts[key] = counts.get(key, 0) + 1
    targets, plans, recs, dups = _inspect(c, replace_all_photos=True)
    planner_counts = {
        f"{a}:{b}": n
        for a, b, n in c.execute(
            "SELECT source,status,count(*) FROM birding_agent.trip_plan_evidence "
            "WHERE evidence_type='recommendation_photo' GROUP BY ALL ORDER BY ALL"
        ).fetchall()
    }
    cols = {r[0] for r in c.execute("DESCRIBE birding_catalog_media.photo_runs").fetchall()}
    outcome = (
        "provider_outcomes_json"
        if "provider_outcomes_json" in cols
        else "'{}' AS provider_outcomes_json"
    )
    result = {
        "catalog_count": len(taxa),
        "catalog_valid_count": valid,
        "catalog_provider_status": counts,
        "planner_plan_count": plans,
        "planner_recommendation_count": recs,
        "planner_invalid_or_missing_count": len(targets),
        "planner_duplicate_count": dups,
        "planner_provider_status": planner_counts,
        "protected_fingerprints": protected,
        "photo_runs": fp(c, "SELECT * FROM birding_catalog_media.photo_runs"),
        "photo_run_values": c.execute(
            "SELECT run_id,status,target_taxa_count,processed_taxa_count,lookup_count,"
            f"{outcome},safe_failure FROM birding_catalog_media.photo_runs "
            "ORDER BY started_at"
        ).fetchall(),
    }
files = {}
for p in sorted(Path("data").rglob("*")):
    if p.is_file() and p.resolve() != DB.resolve() and not p.name.startswith(DB.name + ".wal"):
        h = hashlib.sha256()
        with p.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        files[str(p)] = h.hexdigest()
result["external_file_hashes"] = files
OUT.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
print(
    json.dumps(
        {
            k: result[k]
            for k in (
                "catalog_count",
                "catalog_valid_count",
                "catalog_provider_status",
                "planner_plan_count",
                "planner_recommendation_count",
                "planner_invalid_or_missing_count",
                "planner_duplicate_count",
                "planner_provider_status",
            )
        },
        sort_keys=True,
    )
)
print("protected", len(protected), "external", len(files), "output", OUT)
