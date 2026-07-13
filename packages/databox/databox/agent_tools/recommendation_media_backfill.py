"""Idempotent local backfill of persisted recommendation photo and call evidence.

This command reuses :func:`enrich_recommendation_media`; it does not implement
media selection, licensing, URL, identity, or geography rules of its own.
Only JSON metadata is requested and persisted. Media bytes are never fetched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import duckdb

from databox.agent_tools.recommendation_media import (
    JsonGetter,
    RecommendationIdentity,
    RecommendationMediaEvidence,
    enrich_recommendation_media,
)
from databox.config.settings import settings
from databox.curated_photo import (
    CuratedPhotoResult,
    curated_photo_outcome_keys,
    curated_photo_result_is_retryable,
    curated_photo_result_is_safe,
)

_MEDIA_TYPES = ("recommendation_photo", "recommendation_call")
# 10x: only v2 rows were produced before the reviewed GBIF compatibility repair.
_DEFECTIVE_GBIF_PHOTO_PREFIX = "media_backfill_v2_"
_CURRENT_BACKFILL_EVIDENCE_PREFIX = "media_backfill_v3_"
_CURATED_PHOTO_EVIDENCE_PREFIX = "curated_photo_backfill_"
_DEFECTIVE_GBIF_PHOTO_CAVEATS = '["No eligible exact-species Arizona GBIF photo was found"]'
_PHOTO_RUNS = "birding_agent.recommendation_photo_runs"
_MAX_RUN_JSON_CHARS = 20_000


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
    request_count: int = 0
    run_id: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _duration_ms(started_at: str, completed_at: str) -> int:
    return max(
        0,
        int(
            (
                datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)
            ).total_seconds()
            * 1000
        ),
    )


def _ensure_photo_runs(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS {_PHOTO_RUNS} (
            run_id VARCHAR PRIMARY KEY,
            status VARCHAR NOT NULL CHECK (status IN ('running', 'complete', 'failed')),
            started_at VARCHAR NOT NULL,
            completed_at VARCHAR,
            target_count BIGINT NOT NULL,
            processed_count BIGINT NOT NULL,
            lookup_count BIGINT NOT NULL,
            request_count BIGINT NOT NULL,
            outcomes_json VARCHAR NOT NULL,
            safe_failure VARCHAR,
            duration_ms BIGINT
        )"""
    )


def run_media_backfill(
    database_path: str,
    *,
    apply: bool,
    xeno_getter: JsonGetter | None = None,
    xeno_api_key: str | None = None,
    curated_photos_only: bool = False,
    curated_photo_getter: JsonGetter | None = None,
    before_inaturalist_request: Callable[[], None] | None = None,
) -> MediaBackfillResult:
    """Inspect or backfill missing media evidence in one existing DuckDB.

    Dry-run opens DuckDB read-only and never invokes discovery. Photo apply
    checkpoints lookup plus persistence per recommendation under DuckDB's
    single-writer lock; operators must run it only while other writers are stopped.
    """

    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError(f"DuckDB does not exist: {path}")

    connection = duckdb.connect(str(path), read_only=not apply)
    transaction_open = False
    run_id: str | None = None
    run_started_at: str | None = None
    try:
        targets, plan_count, recommendation_count, duplicates = _inspect(
            connection, replace_all_photos=curated_photos_only
        )
        missing_photos = sum(target.missing_photo for target in targets)
        missing_calls = (
            sum(target.missing_call for target in targets) if not curated_photos_only else 0
        )

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
                request_count=0,
            )
        if duplicates:
            raise RuntimeError("Duplicate recommendation media evidence must be resolved first")

        lookup_count = 0
        request_count = 0
        if curated_photos_only and targets:
            _ensure_photo_runs(connection)
            resumable = connection.execute(
                f"""SELECT run_id, started_at, processed_count, lookup_count, request_count
                FROM {_PHOTO_RUNS} WHERE status IN ('running', 'failed')
                ORDER BY started_at DESC LIMIT 1"""
            ).fetchone()
            if resumable is None:
                run_id = f"recommendation_photo_{uuid.uuid4().hex}"
                run_started_at = _now()
                connection.execute(
                    f"""INSERT INTO {_PHOTO_RUNS} VALUES (
                    ?, 'running', ?, NULL, ?, 0, 0, 0, '{{}}', NULL, NULL)""",
                    [run_id, run_started_at, len(targets)],
                )
            else:
                run_id = str(resumable[0])
                run_started_at = str(resumable[1])
                lookup_count = int(resumable[3])
                request_count = int(resumable[4])
                connection.execute(
                    f"""UPDATE {_PHOTO_RUNS} SET status='running', completed_at=NULL,
                    safe_failure=NULL, duration_ms=NULL WHERE run_id=?""",
                    [run_id],
                )
        photo_targets = [
            target for target in targets if target.missing_photo or target.replace_photo
        ]
        call_targets = (
            [] if curated_photos_only else [target for target in targets if target.missing_call]
        )
        inserted: list[RecommendationMediaEvidence] = []
        retrieved_at = datetime.now(UTC).isoformat()

        for target in photo_targets:
            photos = enrich_recommendation_media(
                cast(list[RecommendationIdentity], [target]),
                curated_photo_getter=curated_photo_getter,
                before_inaturalist_request=before_inaturalist_request,
                evidence_types=frozenset({"recommendation_photo"}),
            )
            if len(photos.evidence) != 1:
                raise RuntimeError("Photo lookup did not return exactly one result")
            row = photos.evidence[0]
            lookup_count += photos.lookup_count
            request_count += photos.request_count
            if run_id is not None:
                connection.execute(
                    f"""UPDATE {_PHOTO_RUNS} SET lookup_count=lookup_count+?,
                    request_count=request_count+? WHERE run_id=?""",
                    [photos.lookup_count, photos.request_count, run_id],
                )
            connection.execute("BEGIN TRANSACTION")
            transaction_open = True
            try:
                if target.replace_photo:
                    connection.execute(
                        "DELETE FROM birding_agent.trip_plan_evidence WHERE evidence_id = ?",
                        [target.photo_evidence_id],
                    )
                _insert_media_evidence(
                    connection,
                    target,
                    row,
                    retrieved_at=retrieved_at,
                    evidence_prefix=(
                        _CURATED_PHOTO_EVIDENCE_PREFIX
                        if curated_photos_only
                        else _CURRENT_BACKFILL_EVIDENCE_PREFIX
                    ),
                )
                if run_id is not None:
                    result = _curated_result_from_media(row, target.scientific_name, retrieved_at)
                    if result is None:
                        raise RuntimeError("Persisted curated photo run result is invalid")
                    outcome_row = connection.execute(
                        f"SELECT outcomes_json FROM {_PHOTO_RUNS} WHERE run_id=?", [run_id]
                    ).fetchone()
                    outcomes = json.loads(str(outcome_row[0])) if outcome_row else None
                    if not isinstance(outcomes, dict):
                        raise RuntimeError("Recommendation photo run outcomes are malformed")
                    for key in curated_photo_outcome_keys(result):
                        outcomes[key] = int(outcomes.get(key, 0)) + 1
                    encoded = json.dumps(outcomes, sort_keys=True, separators=(",", ":"))
                    if len(encoded) > _MAX_RUN_JSON_CHARS:
                        raise RuntimeError("Recommendation photo run outcomes exceed bounds")
                    connection.execute(
                        f"""UPDATE {_PHOTO_RUNS} SET processed_count=processed_count+?,
                        outcomes_json=? WHERE run_id=?""",
                        [
                            0 if curated_photo_result_is_retryable(result) else 1,
                            encoded,
                            run_id,
                        ],
                    )
                connection.execute("COMMIT")
                transaction_open = False
                inserted.append(row)
            except BaseException:
                if transaction_open:
                    connection.execute("ROLLBACK")
                    transaction_open = False
                raise

        if call_targets:
            calls = enrich_recommendation_media(
                cast(list[RecommendationIdentity], call_targets),
                xeno_getter=xeno_getter,
                xeno_api_key=xeno_api_key,
                evidence_types=frozenset({"recommendation_call"}),
            )
            lookup_count += calls.lookup_count
            request_count += calls.request_count
            connection.execute("BEGIN TRANSACTION")
            transaction_open = True
            try:
                targets_by_id = {target.recommendation_id: target for target in call_targets}
                for row in calls.evidence:
                    target = targets_by_id[row.recommendation_id]
                    _insert_media_evidence(
                        connection,
                        target,
                        row,
                        retrieved_at=retrieved_at,
                    )
                    inserted.append(row)
                connection.execute("COMMIT")
                transaction_open = False
            except BaseException:
                if transaction_open:
                    connection.execute("ROLLBACK")
                    transaction_open = False
                raise

        remaining_targets, _, _, remaining_duplicates = _inspect(
            connection, replace_all_photos=curated_photos_only
        )
        remaining_photos = sum(
            target.missing_photo or target.replace_photo for target in remaining_targets
        )
        remaining_calls = (
            sum(target.missing_call for target in remaining_targets)
            if not curated_photos_only
            else 0
        )
        if remaining_duplicates or remaining_calls:
            raise RuntimeError("Media backfill cardinality verification failed")
        if remaining_photos and not curated_photos_only:
            raise RuntimeError("Media backfill cardinality verification failed")
        if run_id is not None and run_started_at is not None:
            completed_at = _now()
            connection.execute(
                f"""UPDATE {_PHOTO_RUNS} SET status=?, completed_at=?, duration_ms=?,
                safe_failure=? WHERE run_id=?""",
                [
                    "failed" if remaining_photos else "complete",
                    completed_at,
                    _duration_ms(run_started_at, completed_at),
                    "retryable_results_remaining" if remaining_photos else None,
                    run_id,
                ],
            )
        if transaction_open:
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
            remaining_missing_photo_count=remaining_photos,
            remaining_missing_call_count=0,
            request_count=request_count,
            run_id=run_id,
        )
    except BaseException as exc:
        if transaction_open:
            connection.execute("ROLLBACK")
        if run_id is not None and run_started_at is not None:
            try:
                completed_at = _now()
                connection.execute(
                    f"""UPDATE {_PHOTO_RUNS} SET status='failed', completed_at=?, duration_ms=?,
                    safe_failure=? WHERE run_id=?""",
                    [
                        completed_at,
                        _duration_ms(run_started_at, completed_at),
                        type(exc).__name__[:64],
                        run_id,
                    ],
                )
            except duckdb.Error:
                pass
        raise
    finally:
        connection.close()


def _inspect(
    connection: duckdb.DuckDBPyConnection,
    *,
    replace_all_photos: bool = False,
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
            max(e.source) FILTER (WHERE e.evidence_type = 'recommendation_photo') AS photo_source,
            max(e.caveats_json) FILTER (
                WHERE e.evidence_type = 'recommendation_photo'
            ) AS photo_caveats,
            max(e.summary_json) FILTER (
                WHERE e.evidence_type = 'recommendation_photo'
            ) AS photo_summary,
            max(e.payload_json) FILTER (
                WHERE e.evidence_type = 'recommendation_photo'
            ) AS photo_payload,
            max(e.source_record_id) FILTER (
                WHERE e.evidence_type = 'recommendation_photo'
            ) AS photo_source_record_id,
            max(e.retrieved_at) FILTER (
                WHERE e.evidence_type = 'recommendation_photo'
            ) AS photo_retrieved_at
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
            and row[10] == _DEFECTIVE_GBIF_PHOTO_CAVEATS
        )
        if replace_all_photos and photo_count == 1:
            persisted = _persisted_curated_photo_result(
                status=str(row[8]),
                source=str(row[9]),
                source_record_id=str(row[13]) if row[13] is not None else None,
                scientific_name=str(row[2]) if row[2] is not None else None,
                retrieved_at=str(row[14]) if row[14] is not None else "",
                summary_json=str(row[11]) if row[11] is not None else "{}",
                payload_json=str(row[12]) if row[12] is not None else "{}",
                caveats_json=str(row[10]) if row[10] is not None else "[]",
            )
            replace_photo = persisted is None or curated_photo_result_is_retryable(persisted)
        if photo_count == 0 or (call_count == 0 and not replace_all_photos) or replace_photo:
            targets.append(
                BackfillRecommendation(
                    recommendation_id=str(row[0]),
                    trip_plan_id=str(row[1]),
                    scientific_name=str(row[2]) if row[2] is not None else None,
                    window_start=str(row[3]),
                    window_end=str(row[4]),
                    missing_photo=photo_count == 0,
                    missing_call=call_count == 0 and not replace_all_photos,
                    replace_photo=replace_photo,
                    photo_evidence_id=photo_id,
                )
            )
    return targets, plan_count, recommendation_count, duplicates


def _persisted_curated_photo_result(
    *,
    status: str,
    source: str,
    source_record_id: str | None,
    scientific_name: str | None,
    retrieved_at: str,
    summary_json: str,
    payload_json: str,
    caveats_json: str,
) -> CuratedPhotoResult | None:
    try:
        summary = json.loads(summary_json)
        payload = json.loads(payload_json)
        caveats = json.loads(caveats_json)
        if (
            not isinstance(summary, dict)
            or not isinstance(payload, dict)
            or not isinstance(caveats, list)
        ):
            return None
        result = CuratedPhotoResult(
            status=cast(Any, status),
            source=cast(Any, source),
            source_record_id=source_record_id,
            species_name=cast(str | None, summary.get("species_name")),
            display_url=cast(str | None, summary.get("display_url")),
            source_url=cast(str | None, summary.get("source_url")),
            creator=cast(str | None, summary.get("creator")),
            license_code=cast(str | None, summary.get("license_code")),
            license_url=cast(str | None, summary.get("license_url")),
            original_width=cast(int | None, summary.get("original_width")),
            original_height=cast(int | None, summary.get("original_height")),
            selection_reason=cast(str | None, summary.get("selection_reason")),
            lookup_at=retrieved_at,
            identity=cast(dict[str, str | int | None], payload.get("identity", {})),
            caveats=tuple(str(item) for item in caveats),
            attempted_sources=tuple(cast(list[str], payload.get("attempted_sources", []))),
            request_count=cast(int, payload.get("request_count", 0)),
            failure_class=cast(str | None, payload.get("failure_class")),
            retryable=cast(bool, payload.get("retryable", False)),
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return result if curated_photo_result_is_safe(result, scientific_name) else None


def _curated_result_from_media(
    row: RecommendationMediaEvidence,
    scientific_name: str | None,
    retrieved_at: str,
) -> CuratedPhotoResult | None:
    return _persisted_curated_photo_result(
        status=row.status,
        source=row.source,
        source_record_id=row.source_record_id,
        scientific_name=scientific_name,
        retrieved_at=retrieved_at,
        summary_json=json.dumps(row.summary),
        payload_json=json.dumps(row.payload),
        caveats_json=json.dumps(row.caveats),
    )


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
    evidence_prefix: str = _CURRENT_BACKFILL_EVIDENCE_PREFIX,
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
            f"{evidence_prefix}{digest}",
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
    mode.add_argument(
        "--curated-photos",
        action="store_true",
        help="Replace saved recommendation photos only with curated metadata",
    )
    args = parser.parse_args(argv)
    result = run_media_backfill(
        args.database_path,
        apply=args.apply or args.curated_photos,
        curated_photos_only=args.curated_photos,
    )
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
