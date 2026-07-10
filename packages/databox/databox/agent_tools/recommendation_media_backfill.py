"""Idempotent local backfill of persisted recommendation photo and call evidence.

This command reuses :func:`enrich_recommendation_media`; it does not implement
media selection, licensing, URL, identity, or geography rules of its own.
Only JSON metadata is requested and persisted. Media bytes are never fetched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

import duckdb

from databox.agent_tools.recommendation_media import (
    JsonGetter,
    RecommendationIdentity,
    RecommendationMediaEvidence,
    enrich_recommendation_media,
)
from databox.config.settings import settings

_MEDIA_TYPES = ("recommendation_photo", "recommendation_call")
# 10x: only v2 rows were produced before the reviewed GBIF compatibility repair.
_DEFECTIVE_GBIF_PHOTO_PREFIX = "media_backfill_v2_"
_CURRENT_BACKFILL_EVIDENCE_PREFIX = "media_backfill_v3_"
_DEFECTIVE_GBIF_PHOTO_CAVEATS = '["No eligible exact-species Arizona GBIF photo was found"]'


@dataclass(frozen=True)
class BackfillRecommendation:
    recommendation_id: str
    trip_plan_id: str
    scientific_name: str | None
    window_start: str
    window_end: str
    missing_photo: bool
    missing_call: bool
    replace_photo: bool
    photo_evidence_id: str | None


@dataclass(frozen=True)
class MediaBackfillResult:
    mode: Literal["dry-run", "apply"]
    plan_count: int
    recommendation_count: int
    target_recommendation_count: int
    missing_photo_count: int
    missing_call_count: int
    duplicate_media_count: int
    inserted_photo_count: int
    inserted_call_count: int
    replaced_photo_count: int
    inserted_available_count: int
    inserted_unavailable_count: int
    lookup_count: int
    remaining_missing_photo_count: int
    remaining_missing_call_count: int


def run_media_backfill(
    database_path: str,
    *,
    apply: bool,
    gbif_getter: JsonGetter | None = None,
    xeno_getter: JsonGetter | None = None,
    xeno_api_key: str | None = None,
) -> MediaBackfillResult:
    """Inspect or backfill missing media evidence in one existing DuckDB.

    Dry-run opens DuckDB read-only and never invokes discovery. Apply uses one
    transaction and DuckDB's single-writer lock, so operators must run it only
    while source refresh and the local API writer are stopped.
    """

    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError(f"DuckDB does not exist: {path}")

    connection = duckdb.connect(str(path), read_only=not apply)
    transaction_open = False
    try:
        if apply:
            connection.execute("BEGIN TRANSACTION")
            transaction_open = True
        targets, plan_count, recommendation_count, duplicates = _inspect(connection)
        missing_photos = sum(target.missing_photo for target in targets)
        missing_calls = sum(target.missing_call for target in targets)

        if not apply:
            return MediaBackfillResult(
                mode="dry-run",
                plan_count=plan_count,
                recommendation_count=recommendation_count,
                target_recommendation_count=len(targets),
                missing_photo_count=missing_photos,
                missing_call_count=missing_calls,
                duplicate_media_count=duplicates,
                inserted_photo_count=0,
                inserted_call_count=0,
                replaced_photo_count=0,
                inserted_available_count=0,
                inserted_unavailable_count=0,
                lookup_count=0,
                remaining_missing_photo_count=missing_photos,
                remaining_missing_call_count=missing_calls,
            )
        if duplicates:
            raise RuntimeError("Duplicate recommendation media evidence must be resolved first")

        media_rows: list[RecommendationMediaEvidence] = []
        lookup_count = 0
        photo_targets = [
            target for target in targets if target.missing_photo or target.replace_photo
        ]
        call_targets = [target for target in targets if target.missing_call]
        if photo_targets:
            photos = enrich_recommendation_media(
                cast(list[RecommendationIdentity], photo_targets),
                gbif_getter=gbif_getter,
                xeno_getter=xeno_getter,
                xeno_api_key=xeno_api_key,
                evidence_types=frozenset({"recommendation_photo"}),
            )
            media_rows.extend(photos.evidence)
            lookup_count += photos.lookup_count
        if call_targets:
            calls = enrich_recommendation_media(
                cast(list[RecommendationIdentity], call_targets),
                gbif_getter=gbif_getter,
                xeno_getter=xeno_getter,
                xeno_api_key=xeno_api_key,
                evidence_types=frozenset({"recommendation_call"}),
            )
            media_rows.extend(calls.evidence)
            lookup_count += calls.lookup_count
        targets_by_id = {target.recommendation_id: target for target in targets}
        inserted: list[RecommendationMediaEvidence] = []
        retrieved_at = datetime.now(UTC).isoformat()
        for row in media_rows:
            target = targets_by_id[row.recommendation_id]
            if row.evidence_type == "recommendation_photo" and not (
                target.missing_photo or target.replace_photo
            ):
                continue
            if row.evidence_type == "recommendation_call" and not target.missing_call:
                continue
            if row.evidence_type == "recommendation_photo" and target.replace_photo:
                connection.execute(
                    "DELETE FROM birding_agent.trip_plan_evidence WHERE evidence_id = ?",
                    [target.photo_evidence_id],
                )
            _insert_media_evidence(connection, target, row, retrieved_at=retrieved_at)
            inserted.append(row)

        remaining_targets, _, _, remaining_duplicates = _inspect(connection)
        remaining_photos = sum(target.missing_photo for target in remaining_targets)
        remaining_calls = sum(target.missing_call for target in remaining_targets)
        if remaining_duplicates or remaining_photos or remaining_calls:
            raise RuntimeError("Media backfill cardinality verification failed")
        connection.execute("COMMIT")
        transaction_open = False
        return MediaBackfillResult(
            mode="apply",
            plan_count=plan_count,
            recommendation_count=recommendation_count,
            target_recommendation_count=len(targets),
            missing_photo_count=missing_photos,
            missing_call_count=missing_calls,
            duplicate_media_count=duplicates,
            inserted_photo_count=sum(
                row.evidence_type == "recommendation_photo" for row in inserted
            ),
            inserted_call_count=sum(row.evidence_type == "recommendation_call" for row in inserted),
            replaced_photo_count=sum(target.replace_photo for target in targets),
            inserted_available_count=sum(row.status == "available" for row in inserted),
            inserted_unavailable_count=sum(row.status == "unavailable" for row in inserted),
            lookup_count=lookup_count,
            remaining_missing_photo_count=0,
            remaining_missing_call_count=0,
        )
    except BaseException:
        if transaction_open:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def _inspect(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[list[BackfillRecommendation], int, int, int]:
    plan_count = _scalar_int(connection, "SELECT count(*) FROM birding_agent.trip_plans")
    recommendation_count = _scalar_int(
        connection, "SELECT count(*) FROM birding_agent.trip_plan_recommendations"
    )
    rows = connection.execute(
        """
        SELECT
            r.recommendation_id,
            r.trip_plan_id,
            r.scientific_name,
            p.window_start,
            p.window_end,
            count(*) FILTER (WHERE e.evidence_type = 'recommendation_photo') AS photo_count,
            count(*) FILTER (WHERE e.evidence_type = 'recommendation_call') AS call_count,
            max(e.evidence_id) FILTER (WHERE e.evidence_type = 'recommendation_photo') AS photo_id,
            max(e.status) FILTER (WHERE e.evidence_type = 'recommendation_photo') AS photo_status,
            max(e.caveats_json) FILTER (
                WHERE e.evidence_type = 'recommendation_photo'
            ) AS photo_caveats
        FROM birding_agent.trip_plan_recommendations AS r
        JOIN birding_agent.trip_plans AS p USING (trip_plan_id)
        LEFT JOIN birding_agent.trip_plan_evidence AS e
          ON e.recommendation_id = r.recommendation_id
         AND e.evidence_type IN ('recommendation_photo', 'recommendation_call')
        GROUP BY ALL
        ORDER BY r.trip_plan_id, min(r.rank_order), r.recommendation_id
        """
    ).fetchall()
    targets: list[BackfillRecommendation] = []
    duplicates = 0
    for row in rows:
        photo_count = int(row[5])
        call_count = int(row[6])
        duplicates += max(photo_count - 1, 0) + max(call_count - 1, 0)
        photo_id = str(row[7]) if row[7] is not None else None
        replace_photo = bool(
            photo_count == 1
            and photo_id
            and photo_id.startswith(_DEFECTIVE_GBIF_PHOTO_PREFIX)
            and row[8] == "unavailable"
            and row[9] == _DEFECTIVE_GBIF_PHOTO_CAVEATS
        )
        if photo_count == 0 or call_count == 0 or replace_photo:
            targets.append(
                BackfillRecommendation(
                    recommendation_id=str(row[0]),
                    trip_plan_id=str(row[1]),
                    scientific_name=str(row[2]) if row[2] is not None else None,
                    window_start=str(row[3]),
                    window_end=str(row[4]),
                    missing_photo=photo_count == 0,
                    missing_call=call_count == 0,
                    replace_photo=replace_photo,
                    photo_evidence_id=photo_id,
                )
            )
    return targets, plan_count, recommendation_count, duplicates


def _scalar_int(connection: duckdb.DuckDBPyConnection, query: str) -> int:
    row = connection.execute(query).fetchone()
    if row is None:
        raise RuntimeError("Expected a scalar DuckDB result")
    return int(row[0])


def _insert_media_evidence(
    connection: duckdb.DuckDBPyConnection,
    target: BackfillRecommendation,
    row: RecommendationMediaEvidence,
    *,
    retrieved_at: str,
) -> None:
    if row.evidence_type not in _MEDIA_TYPES:
        raise ValueError("Unexpected recommendation media evidence type")
    digest = hashlib.sha256(f"{target.recommendation_id}\0{row.evidence_type}".encode()).hexdigest()
    connection.execute(
        """
        INSERT INTO birding_agent.trip_plan_evidence (
            evidence_id,
            trip_plan_id,
            recommendation_id,
            source,
            source_table,
            source_record_id,
            evidence_type,
            status,
            latitude,
            longitude,
            window_start,
            window_end,
            retrieved_at,
            summary_json,
            payload_json,
            caveats_json
        ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?)
        """,
        [
            f"{_CURRENT_BACKFILL_EVIDENCE_PREFIX}{digest}",
            target.trip_plan_id,
            target.recommendation_id,
            row.source,
            row.source_record_id,
            row.evidence_type,
            row.status,
            target.window_start,
            target.window_end,
            retrieved_at,
            json.dumps(row.summary, sort_keys=True),
            json.dumps(row.payload, sort_keys=True),
            json.dumps(row.caveats, sort_keys=True),
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or backfill persisted recommendation media metadata"
    )
    parser.add_argument("--database-path", default=settings.database_path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run", action="store_true", help="Report targets without discovery/writes"
    )
    mode.add_argument(
        "--apply", action="store_true", help="Discover and persist missing media results"
    )
    args = parser.parse_args(argv)
    result = run_media_backfill(args.database_path, apply=args.apply)
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
