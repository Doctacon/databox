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

SCHEMA = "birding_catalog_media"
_RESULTS = f"{SCHEMA}.results"
_RUNS = f"{SCHEMA}.runs"
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
    mode: RunMode
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

    def to_dict(self) -> dict[str, str | int | None]:
        return asdict(self)


def _now() -> str:
    return datetime.now(UTC).isoformat()


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
            source=cast(Literal["gbif", "xeno_canto"], str(row[4])),
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
    return RecommendationMediaEvidence(
        recommendation_id=taxon.species_code,
        source="gbif" if kind == "photo" else "xeno_canto",
        source_record_id=None,
        evidence_type="recommendation_photo" if kind == "photo" else "recommendation_call",
        status="unavailable",
        summary={"kind": kind, "status": "unavailable"},
        payload={},
        caveats=[caveat],
    )


def _bounded_catalog_evidence(
    taxon: CatalogTaxon, row: RecommendationMediaEvidence
) -> RecommendationMediaEvidence:
    kind: MediaKind = "photo" if row.evidence_type == "recommendation_photo" else "call"
    expected_source = "gbif" if kind == "photo" else "xeno_canto"
    try:
        encoded = [
            json.dumps(value, sort_keys=True, separators=(",", ":"))
            for value in (row.summary, row.payload, row.caveats)
        ]
        if (
            row.recommendation_id != taxon.species_code
            or row.source != expected_source
            or row.status not in {"available", "unavailable"}
            or any(len(value) > _MAX_PERSISTED_JSON_CHARS for value in encoded)
            or len(row.caveats) > 10
            or any(not 0 < len(caveat) <= 1000 for caveat in row.caveats)
            or not recommendation_media_evidence_is_safe(row, taxon.scientific_name or "")
        ):
            raise ValueError("catalog media metadata is unsafe")
    except (TypeError, ValueError):
        return _unavailable_for_taxon(
            taxon, kind, "Selected catalog media metadata failed bounded safety validation"
        )
    return row


def _lookup_taxon(
    taxon: CatalogTaxon,
    *,
    gbif_getter: JsonGetter | None,
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
        gbif_getter=gbif_getter,
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
    gbif_getter: JsonGetter | None = None,
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
                gbif_getter=gbif_getter,
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
