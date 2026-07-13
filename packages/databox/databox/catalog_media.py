"""Explicit resumable metadata-only media enrichment for the Arizona catalog."""

from __future__ import annotations

import hashlib
import json
import os
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
    exact_media_scientific_name,
    recommendation_media_evidence_is_safe,
)
from databox.curated_photo import (
    CuratedPhotoResult,
    curated_photo_outcome_keys,
    curated_photo_result_is_retryable,
    curated_photo_result_is_safe,
    select_curated_photo,
)

SCHEMA = "birding_catalog_media"
_RESULTS = f"{SCHEMA}.results"
_RUNS = f"{SCHEMA}.runs"
_PHOTO_RUNS = f"{SCHEMA}.photo_runs"
MediaKind = Literal["photo", "call"]
RunMode = Literal["inspect", "apply", "refresh"]
_MAX_PERSISTED_JSON_CHARS = 20_000


@dataclass(frozen=True)
class CatalogTaxon:
    species_code: str
    scientific_name: str | None
    taxonomic_category: str
    identity_hash: str

    @property
    def recommendation_id(self) -> str:
        return self.species_code


@dataclass(frozen=True)
class CatalogMediaRunResult:
    mode: str
    catalog_count: int
    complete_taxa_count: int
    target_taxa_count: int
    processed_taxa_count: int
    lookup_count: int
    available_photo_count: int
    available_call_count: int
    unavailable_photo_count: int
    unavailable_call_count: int
    remaining_taxa_count: int
    run_id: str | None = None
    request_count: int = 0

    def to_dict(self) -> dict[str, str | int | None]:
        return asdict(self)


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


def _table_exists(connection: duckdb.DuckDBPyConnection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema=? AND table_name=?",
            [SCHEMA, table],
        ).fetchone()
        is not None
    )


def catalog_media_identity_hash(species_code: str, scientific_name: str | None) -> str:
    value = f"{species_code}|{scientific_name or ''}"
    return hashlib.sha256(value.encode()).hexdigest()


def _catalog(
    connection: duckdb.DuckDBPyConnection,
    *,
    expected_catalog_count: int | None,
) -> list[CatalogTaxon]:
    rows = connection.execute(
        """SELECT species_code, scientific_name, taxonomic_category
        FROM birding_agent.arizona_species_catalog
        ORDER BY taxonomic_order, species_code"""
    ).fetchall()
    taxa = [
        CatalogTaxon(
            species_code=str(row[0]),
            scientific_name=str(row[1]) if row[1] is not None else None,
            taxonomic_category=str(row[2]),
            identity_hash=catalog_media_identity_hash(
                str(row[0]), str(row[1]) if row[1] is not None else None
            ),
        )
        for row in rows
    ]
    if expected_catalog_count is not None and len(taxa) != expected_catalog_count:
        raise ValueError(f"catalog must contain exactly {expected_catalog_count} taxa")
    if len({taxon.species_code for taxon in taxa}) != len(taxa):
        raise ValueError("catalog species codes must be unique")
    if any(taxon.taxonomic_category not in {"species", "hybrid"} for taxon in taxa):
        raise ValueError("catalog contains unsupported taxonomic category")
    return taxa


def ensure_catalog_media_tables(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS {_RESULTS} (
            species_code VARCHAR NOT NULL,
            media_kind VARCHAR NOT NULL CHECK (media_kind IN ('photo', 'call')),
            scientific_name VARCHAR,
            identity_hash VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            source_record_id VARCHAR,
            status VARCHAR NOT NULL CHECK (status IN ('available', 'unavailable')),
            summary_json VARCHAR NOT NULL,
            payload_json VARCHAR NOT NULL,
            caveats_json VARCHAR NOT NULL,
            lookup_at VARCHAR NOT NULL,
            run_id VARCHAR NOT NULL,
            PRIMARY KEY (species_code, media_kind)
        )"""
    )
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS {_RUNS} (
            run_id VARCHAR PRIMARY KEY,
            mode VARCHAR NOT NULL CHECK (mode IN ('apply', 'refresh')),
            status VARCHAR NOT NULL CHECK (status IN ('running', 'complete', 'failed')),
            started_at VARCHAR NOT NULL,
            completed_at VARCHAR,
            catalog_count BIGINT NOT NULL,
            target_taxa_count BIGINT NOT NULL,
            processed_taxa_count BIGINT NOT NULL,
            lookup_count BIGINT NOT NULL,
            safe_failure VARCHAR
        )"""
    )
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS {_PHOTO_RUNS} (
            run_id VARCHAR PRIMARY KEY,
            status VARCHAR NOT NULL CHECK (status IN ('running', 'complete', 'failed')),
            started_at VARCHAR NOT NULL,
            completed_at VARCHAR,
            catalog_count BIGINT NOT NULL,
            target_taxa_count BIGINT NOT NULL,
            processed_taxa_count BIGINT NOT NULL,
            lookup_count BIGINT NOT NULL,
            safe_failure VARCHAR,
            provider_outcomes_json VARCHAR NOT NULL DEFAULT '{{}}',
            request_count BIGINT NOT NULL DEFAULT 0,
            duration_ms BIGINT
        )"""
    )
    connection.execute(
        f"ALTER TABLE {_PHOTO_RUNS} ADD COLUMN IF NOT EXISTS provider_outcomes_json VARCHAR"
    )
    connection.execute(
        f"ALTER TABLE {_PHOTO_RUNS} ADD COLUMN IF NOT EXISTS request_count BIGINT DEFAULT 0"
    )
    connection.execute(f"ALTER TABLE {_PHOTO_RUNS} ADD COLUMN IF NOT EXISTS duration_ms BIGINT")
    connection.execute(
        f"""UPDATE {_PHOTO_RUNS} SET provider_outcomes_json='{{}}'
        WHERE provider_outcomes_json IS NULL"""
    )
    connection.execute(f"UPDATE {_PHOTO_RUNS} SET request_count=0 WHERE request_count IS NULL")


def curated_photo_result_from_row(
    row: tuple[Any, ...], taxon: CatalogTaxon
) -> CuratedPhotoResult | None:
    try:
        summary = json.loads(row[7])
        payload = json.loads(row[8])
        caveats = json.loads(row[9])
        if (
            not isinstance(summary, dict)
            or not isinstance(payload, dict)
            or not isinstance(caveats, list)
            or any(not isinstance(item, str) for item in caveats)
            or not {"identity", "attempted_sources"} <= set(payload)
            or not set(payload)
            <= {
                "identity",
                "attempted_sources",
                "request_count",
                "failure_class",
                "retryable",
            }
            or not isinstance(payload["identity"], dict)
            or not isinstance(payload["attempted_sources"], list)
            or any(not isinstance(item, str) for item in payload["attempted_sources"])
        ):
            return None
        result = CuratedPhotoResult(
            status=cast(Literal["available", "unavailable"], str(row[6])),
            source=cast(
                Literal["inaturalist", "curated_photo"],
                str(row[4]),
            ),
            source_record_id=str(row[5]) if row[5] is not None else None,
            species_name=summary.get("species_name"),
            display_url=summary.get("display_url"),
            source_url=summary.get("source_url"),
            creator=summary.get("creator"),
            license_code=summary.get("license_code"),
            license_url=summary.get("license_url"),
            original_width=summary.get("original_width"),
            original_height=summary.get("original_height"),
            selection_reason=summary.get("selection_reason"),
            lookup_at=str(row[10]),
            identity=cast(dict[str, str | int | None], payload["identity"]),
            caveats=tuple(caveats),
            attempted_sources=tuple(payload["attempted_sources"]),
            request_count=cast(int, payload.get("request_count", 0)),
            failure_class=cast(str | None, payload.get("failure_class")),
            retryable=cast(bool, payload.get("retryable", False)),
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return result if curated_photo_result_is_safe(result, taxon.scientific_name) else None


def _persisted_evidence(
    row: tuple[Any, ...], taxon: CatalogTaxon
) -> RecommendationMediaEvidence | None:
    code = str(row[0])
    kind = str(row[1])
    scientific_name = str(row[2]) if row[2] is not None else None
    identity_hash = str(row[3])
    if (
        code != taxon.species_code
        or scientific_name != taxon.scientific_name
        or identity_hash != taxon.identity_hash
        or kind not in {"photo", "call"}
    ):
        return None
    if kind == "photo" and str(row[4]) in {"inaturalist", "curated_photo"}:
        curated = curated_photo_result_from_row(row, taxon)
        if curated is None:
            return None
        return RecommendationMediaEvidence(
            recommendation_id=code,
            source=curated.source,
            source_record_id=curated.source_record_id,
            evidence_type="recommendation_photo",
            status=curated.status,
            summary={},
            payload={},
            caveats=list(curated.caveats),
        )
    try:
        summary = json.loads(row[7])
        payload = json.loads(row[8])
        caveats = json.loads(row[9])
        lookup_at = datetime.fromisoformat(str(row[10]))
        if (
            not isinstance(summary, dict)
            or not isinstance(payload, dict)
            or not isinstance(caveats, list)
            or any(not isinstance(item, str) for item in caveats)
            or lookup_at.tzinfo is None
            or any(len(str(value)) > _MAX_PERSISTED_JSON_CHARS for value in row[7:10])
        ):
            return None
        evidence = RecommendationMediaEvidence(
            recommendation_id=code,
            source=cast(Literal["xeno_canto"], str(row[4])),
            source_record_id=str(row[5]) if row[5] is not None else None,
            evidence_type="recommendation_photo" if kind == "photo" else "recommendation_call",
            status=cast(Literal["available", "unavailable"], str(row[6])),
            summary=summary,
            payload=payload,
            caveats=caveats,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return (
        evidence
        if recommendation_media_evidence_is_safe(evidence, taxon.scientific_name or "")
        else None
    )


def _valid_result_rows(
    connection: duckdb.DuckDBPyConnection,
    taxa: list[CatalogTaxon],
    *,
    run_id: str | None = None,
) -> dict[str, list[tuple[Any, ...]]]:
    if not _table_exists(connection, "results"):
        return {}
    query = f"""SELECT species_code, media_kind, scientific_name, identity_hash, source,
        source_record_id, status, summary_json, payload_json, caveats_json, lookup_at, run_id
        FROM {_RESULTS}"""
    params: list[str] = []
    if run_id is not None:
        query += " WHERE run_id=?"
        params.append(run_id)
    by_taxon = {taxon.species_code: taxon for taxon in taxa}
    grouped: dict[str, list[tuple[Any, ...]]] = {}
    for row in connection.execute(query, params).fetchall():
        taxon = by_taxon.get(str(row[0]))
        if taxon is not None and _persisted_evidence(row, taxon) is not None:
            grouped.setdefault(taxon.species_code, []).append(row)
    return grouped


def _terminal_photo_codes(
    connection: duckdb.DuckDBPyConnection,
    taxa: list[CatalogTaxon],
    *,
    run_id: str | None = None,
) -> set[str]:
    by_taxon = {taxon.species_code: taxon for taxon in taxa}
    output: set[str] = set()
    for code, rows in _valid_result_rows(connection, taxa, run_id=run_id).items():
        taxon = by_taxon[code]
        for row in rows:
            if str(row[1]) != "photo":
                continue
            result = curated_photo_result_from_row(row, taxon)
            if result is not None and not curated_photo_result_is_retryable(result):
                output.add(code)
    return output


def _complete_codes(connection: duckdb.DuckDBPyConnection, taxa: list[CatalogTaxon]) -> set[str]:
    grouped = _valid_result_rows(connection, taxa)
    return {
        code
        for code, rows in grouped.items()
        if len(rows) == 2 and {str(row[1]) for row in rows} == {"photo", "call"}
    }


def _complete_codes_for_run(
    connection: duckdb.DuckDBPyConnection,
    taxa: list[CatalogTaxon],
    run_id: str,
) -> set[str]:
    grouped = _valid_result_rows(connection, taxa, run_id=run_id)
    return {
        code
        for code, rows in grouped.items()
        if len(rows) == 2 and {str(row[1]) for row in rows} == {"photo", "call"}
    }


def _coverage(
    connection: duckdb.DuckDBPyConnection, taxa: list[CatalogTaxon]
) -> tuple[int, int, int, int]:
    if not _table_exists(connection, "results"):
        return 0, 0, 0, 0
    valid_rows = _valid_result_rows(connection, taxa)
    counts = {
        ("photo", "available"): 0,
        ("call", "available"): 0,
        ("photo", "unavailable"): 0,
        ("call", "unavailable"): 0,
    }
    for rows in valid_rows.values():
        for row in rows:
            counts[(str(row[1]), str(row[6]))] += 1
    return (
        counts[("photo", "available")],
        counts[("call", "available")],
        counts[("photo", "unavailable")],
        counts[("call", "unavailable")],
    )


def inspect_catalog_media(
    connection: duckdb.DuckDBPyConnection,
    *,
    expected_catalog_count: int | None = 706,
    refresh: bool = False,
) -> CatalogMediaRunResult:
    taxa = _catalog(connection, expected_catalog_count=expected_catalog_count)
    complete = _complete_codes(connection, taxa)
    targets = taxa if refresh else [taxon for taxon in taxa if taxon.species_code not in complete]
    available_photo, available_call, unavailable_photo, unavailable_call = _coverage(
        connection, taxa
    )
    return CatalogMediaRunResult(
        mode="inspect",
        catalog_count=len(taxa),
        complete_taxa_count=len(complete),
        target_taxa_count=len(targets),
        processed_taxa_count=0,
        lookup_count=0,
        available_photo_count=available_photo,
        available_call_count=available_call,
        unavailable_photo_count=unavailable_photo,
        unavailable_call_count=unavailable_call,
        remaining_taxa_count=len(targets),
    )


def _unavailable_for_taxon(
    taxon: CatalogTaxon, kind: MediaKind, caveat: str
) -> RecommendationMediaEvidence:
    if kind == "photo":
        return RecommendationMediaEvidence(
            recommendation_id=taxon.species_code,
            source="curated_photo",
            source_record_id=None,
            evidence_type="recommendation_photo",
            status="unavailable",
            summary={
                "species_name": exact_media_scientific_name(taxon.scientific_name),
                "display_url": None,
                "source_url": None,
                "creator": None,
                "rights_holder": None,
                "publisher": None,
                "format": None,
                "license_text": None,
                "license_code": None,
                "license_url": None,
                "original_width": None,
                "original_height": None,
                "selection_reason": None,
                "provider": None,
            },
            payload={"identity": {}, "attempted_sources": []},
            caveats=[caveat],
        )
    return RecommendationMediaEvidence(
        recommendation_id=taxon.species_code,
        source="xeno_canto",
        source_record_id=None,
        evidence_type="recommendation_call",
        status="unavailable",
        summary={"kind": "call", "status": "unavailable"},
        payload={},
        caveats=[caveat],
    )


def _curated_result_from_evidence(
    taxon: CatalogTaxon, row: RecommendationMediaEvidence
) -> CuratedPhotoResult | None:
    try:
        if (
            row.evidence_type != "recommendation_photo"
            or row.source not in {"inaturalist", "curated_photo"}
            or not {"identity", "attempted_sources"} <= set(row.payload)
            or not set(row.payload)
            <= {
                "identity",
                "attempted_sources",
                "request_count",
                "failure_class",
                "retryable",
            }
            or not isinstance(row.payload["identity"], dict)
            or not isinstance(row.payload["attempted_sources"], list)
            or any(not isinstance(value, str) for value in row.payload["attempted_sources"])
        ):
            return None
        result = CuratedPhotoResult(
            status=row.status,
            source=cast(
                Literal["inaturalist", "curated_photo"],
                row.source,
            ),
            source_record_id=row.source_record_id,
            species_name=row.summary.get("species_name"),
            display_url=row.summary.get("display_url"),
            source_url=row.summary.get("source_url"),
            creator=row.summary.get("creator"),
            license_code=row.summary.get("license_code"),
            license_url=row.summary.get("license_url"),
            original_width=row.summary.get("original_width"),
            original_height=row.summary.get("original_height"),
            selection_reason=row.summary.get("selection_reason"),
            lookup_at=_now(),
            identity=cast(dict[str, str | int | None], row.payload["identity"]),
            caveats=tuple(row.caveats),
            attempted_sources=tuple(row.payload["attempted_sources"]),
            request_count=cast(int, row.payload.get("request_count", 0)),
            failure_class=cast(str | None, row.payload.get("failure_class")),
            retryable=cast(bool, row.payload.get("retryable", False)),
        )
    except (TypeError, ValueError):
        return None
    return result if curated_photo_result_is_safe(result, taxon.scientific_name) else None


def _bounded_catalog_evidence(
    taxon: CatalogTaxon, row: RecommendationMediaEvidence
) -> RecommendationMediaEvidence:
    kind: MediaKind = "photo" if row.evidence_type == "recommendation_photo" else "call"
    try:
        encoded = [
            json.dumps(value, sort_keys=True, separators=(",", ":"))
            for value in (row.summary, row.payload, row.caveats)
        ]
        if (
            row.recommendation_id != taxon.species_code
            or row.status not in {"available", "unavailable"}
            or any(len(value) > _MAX_PERSISTED_JSON_CHARS for value in encoded)
            or len(row.caveats) > 10
            or any(not 0 < len(caveat) <= 1000 for caveat in row.caveats)
        ):
            raise ValueError("catalog media metadata is unsafe")
        if kind == "photo":
            if _curated_result_from_evidence(taxon, row) is None:
                raise ValueError("catalog photo metadata is unsafe")
        elif row.source != "xeno_canto" or not recommendation_media_evidence_is_safe(
            row, taxon.scientific_name or ""
        ):
            raise ValueError("catalog call metadata is unsafe")
    except (TypeError, ValueError):
        return _unavailable_for_taxon(
            taxon, kind, "Selected catalog media metadata failed bounded safety validation"
        )
    return row


def _lookup_taxon(
    taxon: CatalogTaxon,
    *,
    curated_photo_getter: JsonGetter | None,
    before_inaturalist_request: Callable[[], None] | None,
    xeno_getter: JsonGetter | None,
    xeno_api_key: str | None,
) -> tuple[list[RecommendationMediaEvidence], int]:
    if taxon.taxonomic_category != "species":
        caveat = "Hybrid media requires an exact taxon result; parent fallback is prohibited"
        return [
            _unavailable_for_taxon(taxon, "photo", caveat),
            _unavailable_for_taxon(taxon, "call", caveat),
        ], 0
    if exact_media_scientific_name(taxon.scientific_name) is None:
        caveat = "An exact current binomial scientific name is required; fallback is prohibited"
        return [
            _unavailable_for_taxon(taxon, "photo", caveat),
            _unavailable_for_taxon(taxon, "call", caveat),
        ], 0
    batch = enrich_recommendation_media(
        cast(list[RecommendationIdentity], [taxon]),
        curated_photo_getter=curated_photo_getter,
        before_inaturalist_request=before_inaturalist_request,
        xeno_getter=xeno_getter,
        xeno_api_key=xeno_api_key,
    )
    return [_bounded_catalog_evidence(taxon, row) for row in batch.evidence], batch.lookup_count


def _persist_taxon(
    connection: duckdb.DuckDBPyConnection,
    taxon: CatalogTaxon,
    evidence: list[RecommendationMediaEvidence],
    *,
    run_id: str,
    lookup_at: str,
    before_commit: Callable[[duckdb.DuckDBPyConnection, CatalogTaxon], None] | None = None,
) -> None:
    if len(evidence) != 2 or {row.evidence_type for row in evidence} != {
        "recommendation_photo",
        "recommendation_call",
    }:
        raise ValueError("selector must return exactly one photo and one call result")
    connection.execute("BEGIN TRANSACTION")
    try:
        connection.execute(f"DELETE FROM {_RESULTS} WHERE species_code=?", [taxon.species_code])
        for row in evidence:
            kind = "photo" if row.evidence_type == "recommendation_photo" else "call"
            connection.execute(
                f"INSERT INTO {_RESULTS} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    taxon.species_code,
                    kind,
                    taxon.scientific_name,
                    taxon.identity_hash,
                    row.source,
                    row.source_record_id,
                    row.status,
                    json.dumps(row.summary, sort_keys=True, separators=(",", ":")),
                    json.dumps(row.payload, sort_keys=True, separators=(",", ":")),
                    json.dumps(row.caveats, sort_keys=True, separators=(",", ":")),
                    lookup_at,
                    run_id,
                ],
            )
        connection.execute(
            f"UPDATE {_RUNS} SET processed_taxa_count=processed_taxa_count+1 WHERE run_id=?",
            [run_id],
        )
        if before_commit is not None:
            before_commit(connection, taxon)
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise


def catalog_media_prerequisites(*, xeno_api_key: str | None = None) -> dict[str, bool]:
    configured = xeno_api_key if xeno_api_key is not None else os.getenv("XENO_CANTO_API_KEY")
    return {"xeno_canto_api_key_configured": bool(configured and configured.strip())}


def run_catalog_media_batch(
    database_path: str,
    *,
    mode: RunMode,
    batch_size: int = 25,
    expected_catalog_count: int | None = 706,
    curated_photo_getter: JsonGetter | None = None,
    before_inaturalist_request: Callable[[], None] | None = None,
    xeno_getter: JsonGetter | None = None,
    xeno_api_key: str | None = None,
    after_lookup: Callable[[CatalogTaxon], None] | None = None,
    before_taxon_commit: (Callable[[duckdb.DuckDBPyConnection, CatalogTaxon], None] | None) = None,
) -> CatalogMediaRunResult:
    """Inspect or explicitly enrich one bounded sequential batch.

    Results are checkpoints. Completed exact identities are skipped on apply;
    refresh deliberately replaces them. Discovery happens outside each taxon's
    transaction and only metadata returned by the existing selectors persists.
    """

    if mode not in {"inspect", "apply", "refresh"}:
        raise ValueError("mode must be inspect, apply, or refresh")
    if not 1 <= batch_size <= 706:
        raise ValueError("batch_size must be between 1 and 706")
    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError(f"DuckDB does not exist: {path}")
    resolved_xeno_api_key = (
        xeno_api_key if xeno_api_key is not None else os.getenv("XENO_CANTO_API_KEY")
    )
    if (
        mode != "inspect"
        and not catalog_media_prerequisites(xeno_api_key=resolved_xeno_api_key)[
            "xeno_canto_api_key_configured"
        ]
    ):
        raise RuntimeError("XENO_CANTO_API_KEY is not configured")
    connection = duckdb.connect(str(path), read_only=mode == "inspect")
    run_id: str | None = None
    lookup_count = 0
    try:
        if mode == "inspect":
            return inspect_catalog_media(
                connection, expected_catalog_count=expected_catalog_count, refresh=False
            )
        ensure_catalog_media_tables(connection)
        taxa = _catalog(connection, expected_catalog_count=expected_catalog_count)
        complete = _complete_codes(connection, taxa)
        resumable = connection.execute(
            f"""SELECT run_id, target_taxa_count, processed_taxa_count, lookup_count
            FROM {_RUNS} WHERE mode=? AND status IN ('running', 'failed')
            ORDER BY started_at DESC LIMIT 1""",
            [mode],
        ).fetchone()
        if resumable is not None:
            run_id = str(resumable[0])
            durable_target_count = int(resumable[1])
            lookup_count = int(resumable[3])
            connection.execute(
                f"""UPDATE {_RUNS} SET status='running', completed_at=NULL,
                safe_failure=NULL WHERE run_id=?""",
                [run_id],
            )
            if mode == "refresh":
                finished = _complete_codes_for_run(connection, taxa, run_id)
                all_targets = [taxon for taxon in taxa if taxon.species_code not in finished]
            else:
                all_targets = [taxon for taxon in taxa if taxon.species_code not in complete]
        else:
            run_id = f"catalog_media_{uuid.uuid4().hex}"
            all_targets = (
                taxa
                if mode == "refresh"
                else [taxon for taxon in taxa if taxon.species_code not in complete]
            )
            durable_target_count = len(all_targets)
            connection.execute(
                f"INSERT INTO {_RUNS} VALUES (?, ?, 'running', ?, NULL, ?, ?, 0, 0, NULL)",
                [run_id, mode, _now(), len(taxa), durable_target_count],
            )
        targets = all_targets[:batch_size]
        for taxon in targets:
            evidence, lookups = _lookup_taxon(
                taxon,
                curated_photo_getter=curated_photo_getter,
                before_inaturalist_request=before_inaturalist_request,
                xeno_getter=xeno_getter,
                xeno_api_key=resolved_xeno_api_key,
            )
            lookup_count += lookups
            connection.execute(
                f"UPDATE {_RUNS} SET lookup_count=? WHERE run_id=?", [lookup_count, run_id]
            )
            if after_lookup is not None:
                after_lookup(taxon)
            _persist_taxon(
                connection,
                taxon,
                evidence,
                run_id=run_id,
                lookup_at=_now(),
                before_commit=before_taxon_commit,
            )
        complete_after = _complete_codes(connection, taxa)
        if mode == "refresh":
            refreshed_after = _complete_codes_for_run(connection, taxa, run_id)
            remaining = len(taxa) - len(refreshed_after)
        else:
            remaining = len(taxa) - len(complete_after)
        if remaining == 0:
            connection.execute(
                f"UPDATE {_RUNS} SET status='complete', completed_at=? WHERE run_id=?",
                [_now(), run_id],
            )
        durable = connection.execute(
            f"SELECT target_taxa_count, processed_taxa_count FROM {_RUNS} WHERE run_id=?",
            [run_id],
        ).fetchone()
        assert durable is not None
        available_photo, available_call, unavailable_photo, unavailable_call = _coverage(
            connection, taxa
        )
        return CatalogMediaRunResult(
            mode=mode,
            catalog_count=len(taxa),
            complete_taxa_count=len(complete_after),
            target_taxa_count=int(durable[0]),
            processed_taxa_count=int(durable[1]),
            lookup_count=lookup_count,
            available_photo_count=available_photo,
            available_call_count=available_call,
            unavailable_photo_count=unavailable_photo,
            unavailable_call_count=unavailable_call,
            remaining_taxa_count=remaining,
            run_id=run_id,
        )
    except BaseException as exc:
        if run_id is not None:
            try:
                connection.execute(
                    f"""UPDATE {_RUNS} SET status='failed', completed_at=?,
                    safe_failure=? WHERE run_id=?""",
                    [_now(), type(exc).__name__[:64], run_id],
                )
            except duckdb.Error:
                pass
        raise
    finally:
        connection.close()


def inspect_catalog_photo_refresh(
    connection: duckdb.DuckDBPyConnection,
    *,
    expected_catalog_count: int | None = 706,
) -> CatalogMediaRunResult:
    """Plan the complete photo-only refresh without network calls or writes."""

    taxa = _catalog(connection, expected_catalog_count=expected_catalog_count)
    available_photo, available_call, unavailable_photo, unavailable_call = _coverage(
        connection, taxa
    )
    latest_run_id: str | None = None
    if _table_exists(connection, "photo_runs"):
        latest = connection.execute(
            f"SELECT run_id FROM {_PHOTO_RUNS} ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        latest_run_id = str(latest[0]) if latest is not None else None
    campaign_complete = (
        _terminal_photo_codes(connection, taxa, run_id=latest_run_id)
        if latest_run_id is not None
        else set()
    )
    return CatalogMediaRunResult(
        mode="photo_dry_run",
        catalog_count=len(taxa),
        complete_taxa_count=len(campaign_complete),
        target_taxa_count=len(taxa),
        processed_taxa_count=len(campaign_complete),
        lookup_count=0,
        available_photo_count=available_photo,
        available_call_count=available_call,
        unavailable_photo_count=unavailable_photo,
        unavailable_call_count=unavailable_call,
        remaining_taxa_count=len(taxa) - len(campaign_complete),
        run_id=latest_run_id,
    )


def _curated_summary(result: CuratedPhotoResult) -> dict[str, Any]:
    return {
        "species_name": result.species_name,
        "display_url": result.display_url,
        "source_url": result.source_url,
        "creator": result.creator,
        "license_code": result.license_code,
        "license_url": result.license_url,
        "original_width": result.original_width,
        "original_height": result.original_height,
        "selection_reason": result.selection_reason,
    }


def _persist_curated_photo(
    connection: duckdb.DuckDBPyConnection,
    taxon: CatalogTaxon,
    result: CuratedPhotoResult,
    *,
    run_id: str,
) -> None:
    if not curated_photo_result_is_safe(result, taxon.scientific_name):
        raise ValueError("curated catalog photo failed bounded safety validation")
    summary = json.dumps(_curated_summary(result), sort_keys=True, separators=(",", ":"))
    payload = json.dumps(
        {
            "identity": result.identity,
            "attempted_sources": list(result.attempted_sources),
            "request_count": result.request_count,
            "failure_class": result.failure_class,
            "retryable": result.retryable,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    caveats = json.dumps(list(result.caveats), sort_keys=True, separators=(",", ":"))
    if any(len(value) > _MAX_PERSISTED_JSON_CHARS for value in (summary, payload, caveats)):
        raise ValueError("curated catalog photo exceeds persistence bound")
    connection.execute("BEGIN TRANSACTION")
    try:
        connection.execute(
            f"DELETE FROM {_RESULTS} WHERE species_code=? AND media_kind='photo'",
            [taxon.species_code],
        )
        connection.execute(
            f"INSERT INTO {_RESULTS} VALUES (?, 'photo', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                taxon.species_code,
                taxon.scientific_name,
                taxon.identity_hash,
                result.source,
                result.source_record_id,
                result.status,
                summary,
                payload,
                caveats,
                result.lookup_at,
                run_id,
            ],
        )
        outcome_row = connection.execute(
            f"SELECT provider_outcomes_json FROM {_PHOTO_RUNS} WHERE run_id=?",
            [run_id],
        ).fetchone()
        if outcome_row is None:
            raise RuntimeError("curated photo run checkpoint is missing")
        try:
            outcome_counts = json.loads(str(outcome_row[0]))
        except json.JSONDecodeError:
            raise RuntimeError("curated photo run outcomes are malformed") from None
        if (
            not isinstance(outcome_counts, dict)
            or len(outcome_counts) > 20
            or any(
                not isinstance(key, str)
                or not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                for key, value in outcome_counts.items()
            )
        ):
            raise RuntimeError("curated photo run outcomes are malformed")
        for key in curated_photo_outcome_keys(result):
            outcome_counts[key] = outcome_counts.get(key, 0) + 1
        encoded_outcomes = json.dumps(outcome_counts, sort_keys=True, separators=(",", ":"))
        if len(encoded_outcomes) > _MAX_PERSISTED_JSON_CHARS:
            raise RuntimeError("curated photo run outcomes exceed persistence bound")
        connection.execute(
            f"""UPDATE {_PHOTO_RUNS}
            SET processed_taxa_count=processed_taxa_count+?, provider_outcomes_json=?
            WHERE run_id=?""",
            [
                0 if curated_photo_result_is_retryable(result) else 1,
                encoded_outcomes,
                run_id,
            ],
        )
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise


def run_catalog_photo_refresh(
    database_path: str,
    *,
    batch_size: int = 25,
    expected_catalog_count: int | None = 706,
    getter: JsonGetter | None = None,
    before_inaturalist_request: Callable[[], None] | None = None,
    after_lookup: Callable[[CatalogTaxon], None] | None = None,
) -> CatalogMediaRunResult:
    """Run or resume the explicit serialized metadata-only full photo refresh."""

    if not 1 <= batch_size <= 706:
        raise ValueError("batch_size must be between 1 and 706")
    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError(f"DuckDB does not exist: {path}")
    connection = duckdb.connect(str(path))
    run_id: str | None = None
    lookup_count = 0
    try:
        ensure_catalog_media_tables(connection)
        taxa = _catalog(connection, expected_catalog_count=expected_catalog_count)
        latest = connection.execute(
            f"""SELECT run_id, status, processed_taxa_count, lookup_count, request_count,
            provider_outcomes_json FROM {_PHOTO_RUNS} ORDER BY started_at DESC LIMIT 1"""
        ).fetchone()
        if latest is None:
            run_id = f"catalog_photo_{uuid.uuid4().hex}"
            finished: set[str] = set()
            connection.execute(
                f"""INSERT INTO {_PHOTO_RUNS} (
                    run_id, status, started_at, completed_at, catalog_count,
                    target_taxa_count, processed_taxa_count, lookup_count, safe_failure,
                    provider_outcomes_json, request_count, duration_ms
                ) VALUES (?, 'running', ?, NULL, ?, ?, 0, 0, NULL, '{{}}', 0, NULL)""",
                [run_id, _now(), len(taxa), len(taxa)],
            )
        else:
            run_id = str(latest[0])
            finished = _terminal_photo_codes(connection, taxa, run_id=run_id)
            lookup_count = int(latest[3])
            durable_processed = int(latest[2])
            original_request_count = int(latest[4])
            request_count = original_request_count
            outcomes = json.loads(str(latest[5]))
            if not isinstance(outcomes, dict):
                raise RuntimeError("catalog photo refresh outcomes are malformed")
            two_request_outcomes = {
                "inaturalist.available",
                "inaturalist.no_eligible",
            }
            if (
                request_count == 0
                and lookup_count > 0
                and set(outcomes).issubset(two_request_outcomes)
                and sum(int(value) for value in outcomes.values()) == lookup_count
            ):
                request_count = lookup_count * 2
            if len(finished) == len(taxa):
                available_photo, available_call, unavailable_photo, unavailable_call = _coverage(
                    connection, taxa
                )
                if durable_processed != len(finished) or request_count != original_request_count:
                    connection.execute(
                        f"""UPDATE {_PHOTO_RUNS} SET processed_taxa_count=?, request_count=?
                        WHERE run_id=?""",
                        [len(finished), request_count, run_id],
                    )
                return CatalogMediaRunResult(
                    mode="photo_refresh",
                    catalog_count=len(taxa),
                    complete_taxa_count=len(finished),
                    target_taxa_count=len(taxa),
                    processed_taxa_count=len(finished),
                    lookup_count=lookup_count,
                    available_photo_count=available_photo,
                    available_call_count=available_call,
                    unavailable_photo_count=unavailable_photo,
                    unavailable_call_count=unavailable_call,
                    remaining_taxa_count=0,
                    run_id=run_id,
                    request_count=request_count,
                )
            connection.execute(
                f"""UPDATE {_PHOTO_RUNS} SET status='running', completed_at=NULL,
                processed_taxa_count=?, request_count=?, duration_ms=NULL, safe_failure=NULL
                WHERE run_id=?""",
                [len(finished), request_count, run_id],
            )
        all_targets = [taxon for taxon in taxa if taxon.species_code not in finished]
        targets = all_targets[:batch_size]
        saw_retryable = False
        for taxon in targets:
            result = select_curated_photo(
                taxon.scientific_name,
                getter=getter,
                before_inaturalist_request=before_inaturalist_request,
            )
            if (
                taxon.taxonomic_category == "species"
                and exact_media_scientific_name(taxon.scientific_name) is not None
            ):
                lookup_count += 1
            connection.execute(
                f"""UPDATE {_PHOTO_RUNS} SET lookup_count=?,
                request_count=request_count+? WHERE run_id=?""",
                [lookup_count, result.request_count, run_id],
            )
            if after_lookup is not None:
                after_lookup(taxon)
            _persist_curated_photo(connection, taxon, result, run_id=run_id)
            saw_retryable = saw_retryable or curated_photo_result_is_retryable(result)
        finished = _terminal_photo_codes(connection, taxa, run_id=run_id)
        processed = len(finished)
        remaining = len(taxa) - processed
        completed_at = _now()
        started_row = connection.execute(
            f"SELECT started_at FROM {_PHOTO_RUNS} WHERE run_id=?", [run_id]
        ).fetchone()
        if started_row is None:
            raise RuntimeError("catalog photo run is missing")
        if remaining == 0:
            connection.execute(
                f"""UPDATE {_PHOTO_RUNS} SET status='complete', completed_at=?,
                duration_ms=?, safe_failure=NULL WHERE run_id=?""",
                [completed_at, _duration_ms(str(started_row[0]), completed_at), run_id],
            )
        elif saw_retryable:
            connection.execute(
                f"""UPDATE {_PHOTO_RUNS} SET status='failed', completed_at=?, duration_ms=?,
                safe_failure='retryable_results_remaining' WHERE run_id=?""",
                [completed_at, _duration_ms(str(started_row[0]), completed_at), run_id],
            )
        available_photo, available_call, unavailable_photo, unavailable_call = _coverage(
            connection, taxa
        )
        request_row = connection.execute(
            f"SELECT request_count FROM {_PHOTO_RUNS} WHERE run_id=?", [run_id]
        ).fetchone()
        if request_row is None:
            raise RuntimeError("catalog photo run request count is missing")
        return CatalogMediaRunResult(
            mode="photo_refresh",
            catalog_count=len(taxa),
            complete_taxa_count=processed,
            target_taxa_count=len(taxa),
            processed_taxa_count=processed,
            lookup_count=lookup_count,
            available_photo_count=available_photo,
            available_call_count=available_call,
            unavailable_photo_count=unavailable_photo,
            unavailable_call_count=unavailable_call,
            remaining_taxa_count=remaining,
            run_id=run_id,
            request_count=int(request_row[0]),
        )
    except BaseException as exc:
        if run_id is not None:
            try:
                completed_at = _now()
                started = connection.execute(
                    f"SELECT started_at FROM {_PHOTO_RUNS} WHERE run_id=?", [run_id]
                ).fetchone()
                duration = _duration_ms(str(started[0]), completed_at) if started else None
                connection.execute(
                    f"""UPDATE {_PHOTO_RUNS} SET status='failed', completed_at=?,
                    duration_ms=?, safe_failure=? WHERE run_id=?""",
                    [completed_at, duration, type(exc).__name__[:64], run_id],
                )
            except duckdb.Error:
                pass
        raise
    finally:
        connection.close()


def catalog_media_rows(
    connection: duckdb.DuckDBPyConnection,
    species_codes: list[str],
) -> dict[tuple[str, MediaKind], dict[str, Any]]:
    """Read bounded persisted metadata; absent tables return no rows."""

    if not species_codes or not _table_exists(connection, "results"):
        return {}
    placeholders = ",".join("?" for _ in species_codes)
    rows = connection.execute(
        f"""SELECT species_code, media_kind, scientific_name, identity_hash, source,
        source_record_id, status, summary_json, payload_json, caveats_json, lookup_at
        FROM {_RESULTS} WHERE species_code IN ({placeholders})""",
        species_codes,
    ).fetchall()
    grouped: dict[str, list[tuple[Any, ...]]] = {}
    for row in rows:
        grouped.setdefault(str(row[0]), []).append(row)
    output: dict[tuple[str, MediaKind], dict[str, Any]] = {}
    for code, taxon_rows in grouped.items():
        kinds = {str(row[1]) for row in taxon_rows}
        identities = {(row[2], row[3]) for row in taxon_rows}
        if len(taxon_rows) != 2 or kinds != {"photo", "call"} or len(identities) != 1:
            continue
        for row in taxon_rows:
            kind = cast(MediaKind, str(row[1]))
            output[(code, kind)] = {
                "species_code": code,
                "media_kind": kind,
                "scientific_name": str(row[2]) if row[2] is not None else None,
                "identity_hash": str(row[3]),
                "source": str(row[4]),
                "source_record_id": str(row[5]) if row[5] is not None else None,
                "status": str(row[6]),
                "summary_json": str(row[7]),
                "payload_json": str(row[8]),
                "caveats_json": str(row[9]),
                "lookup_at": str(row[10]),
            }
    return output
