"""Resumable exact-identity catalog media batch tests."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb
import pytest
from databox.catalog_media import (
    catalog_media_prerequisites,
    catalog_media_rows,
    ensure_catalog_media_tables,
    inspect_catalog_media,
    inspect_catalog_photo_refresh,
    run_catalog_media_batch,
    run_catalog_photo_refresh,
)
from databox.curated_photo import INATURALIST_V2_TAXA


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "catalog-media.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA birding_agent")
    connection.execute(
        """CREATE TABLE birding_agent.arizona_species_catalog (
        species_code VARCHAR, scientific_name VARCHAR, taxonomic_category VARCHAR,
        taxonomic_order DOUBLE)"""
    )
    connection.execute(
        """INSERT INTO birding_agent.arizona_species_catalog VALUES
        ('alpha1', 'Avis alpha', 'species', 1),
        ('beta1', 'Avis beta', 'species', 2),
        ('hybrid1', 'Avis alpha x Avis beta', 'hybrid', 3)"""
    )
    connection.close()
    return path


def _letters(index: int) -> str:
    value = ""
    current = index
    while True:
        value = chr(ord("a") + current % 26) + value
        current = current // 26 - 1
        if current < 0:
            return value


def _large_database(tmp_path: Path) -> tuple[Path, dict[str, int]]:
    path = tmp_path / "catalog-media-706.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA birding_agent")
    connection.execute(
        """CREATE TABLE birding_agent.arizona_species_catalog (
        species_code VARCHAR, scientific_name VARCHAR, taxonomic_category VARCHAR,
        taxonomic_order DOUBLE)"""
    )
    keys: dict[str, int] = {}
    rows = []
    for index in range(706):
        scientific_name = f"Avis {_letters(index)}"
        keys[scientific_name] = index + 1
        rows.append(
            (
                f"taxon{index:03d}",
                scientific_name,
                "species" if index < 624 else "hybrid",
                float(index),
            )
        )
    connection.executemany(
        "INSERT INTO birding_agent.arizona_species_catalog VALUES (?, ?, ?, ?)", rows
    )
    connection.close()
    return path, keys


def _photo(name: str, key: int) -> dict[str, Any]:
    identifier = f"https://images.example/{key}.jpg"
    return {
        "results": [
            {
                "key": key,
                "species": name,
                "acceptedScientificName": name,
                "countryCode": "US",
                "country": "United States",
                "stateProvince": "Arizona",
                "publishingOrgKey": "archive",
                "media": [
                    {
                        "type": "StillImage",
                        "format": "image/jpeg",
                        "identifier": identifier,
                        "license": "https://creativecommons.org/licenses/by/4.0/",
                        "creator": "Catalog Photographer",
                        "rightsHolder": None,
                    }
                ],
            }
        ]
    }


def _call(name: str, key: int) -> dict[str, Any]:
    genus, species = name.split()
    return {
        "recordings": [
            {
                "id": str(key),
                "gen": genus,
                "sp": species,
                "rec": "Catalog Recordist",
                "cnt": "United States",
                "loc": "Arizona",
                "type": "call",
                "q": "A",
                "url": f"//xeno-canto.org/{key}",
                "file": f"https://xeno-canto.org/{key}/download",
                "lic": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            }
        ]
    }


def _getters(calls: Counter[str]):
    keys = {"Avis alpha": 101, "Avis beta": 102}
    curated = _curated_getter(Counter())

    def photo(endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        if endpoint == INATURALIST_V2_TAXA:
            calls[f"photo:{params['q']}"] += 1
        return curated(endpoint, params)

    def xeno(_endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        query = str(params["query"])
        name = next(item for item in keys if all(part in query for part in item.split()))
        calls[f"xeno:{name}"] += 1
        return _call(name, keys[name] + 1000)

    return photo, xeno


def test_inspect_is_read_only_network_free_and_does_not_create_tables(tmp_path: Path) -> None:
    path = _database(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    connection = duckdb.connect(str(path), read_only=True)
    result = inspect_catalog_media(connection, expected_catalog_count=None)
    connection.close()
    assert result.catalog_count == result.target_taxa_count == 3
    assert result.complete_taxa_count == result.processed_taxa_count == 0
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    connection = duckdb.connect(str(path), read_only=True)
    assert connection.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='birding_catalog_media'"
    ).fetchone() == (0,)
    connection.close()


def test_missing_xeno_key_fails_preflight_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _database(tmp_path)
    monkeypatch.delenv("XENO_CANTO_API_KEY", raising=False)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    assert catalog_media_prerequisites() == {"xeno_canto_api_key_configured": False}
    with pytest.raises(RuntimeError, match="XENO_CANTO_API_KEY is not configured"):
        run_catalog_media_batch(
            str(path),
            mode="apply",
            expected_catalog_count=None,
        )
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    connection = duckdb.connect(str(path), read_only=True)
    assert connection.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='birding_catalog_media'"
    ).fetchone() == (0,)
    connection.close()


def test_interruption_resumes_without_repeating_checkpoint_and_hybrid_has_no_lookup(
    tmp_path: Path,
) -> None:
    path = _database(tmp_path)
    calls: Counter[str] = Counter()
    photo, xeno = _getters(calls)
    seen = 0

    def interrupt(_taxon) -> None:
        nonlocal seen
        seen += 1
        if seen == 2:
            raise RuntimeError("injected interruption")

    with pytest.raises(RuntimeError, match="injected interruption"):
        run_catalog_media_batch(
            str(path),
            mode="apply",
            batch_size=3,
            expected_catalog_count=None,
            curated_photo_getter=photo,
            before_inaturalist_request=lambda: None,
            xeno_getter=xeno,
            xeno_api_key="test",
            after_lookup=interrupt,
        )
    connection = duckdb.connect(str(path), read_only=True)
    assert len(catalog_media_rows(connection, ["alpha1"])) == 2
    assert catalog_media_rows(connection, ["beta1"]) == {}
    connection.close()

    result = run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=3,
        expected_catalog_count=None,
        curated_photo_getter=photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    assert result.complete_taxa_count == 3
    assert result.target_taxa_count == result.processed_taxa_count == 3
    assert result.remaining_taxa_count == 0
    assert calls["photo:Avis alpha"] == calls["xeno:Avis alpha"] == 1
    assert calls["photo:Avis beta"] == calls["xeno:Avis beta"] == 2
    assert not any("hybrid" in key.lower() for key in calls)
    connection = duckdb.connect(str(path), read_only=True)
    hybrid = catalog_media_rows(connection, ["hybrid1"])
    assert {row["status"] for row in hybrid.values()} == {"unavailable"}
    assert all("parent fallback is prohibited" in row["caveats_json"] for row in hybrid.values())
    assert connection.execute(
        """SELECT status, target_taxa_count, processed_taxa_count
        FROM birding_catalog_media.runs"""
    ).fetchall() == [("complete", 3, 3)]
    connection.close()


def test_second_apply_is_zero_work_and_refresh_explicitly_replaces(tmp_path: Path) -> None:
    path = _database(tmp_path)
    calls: Counter[str] = Counter()
    photo, xeno = _getters(calls)
    first = run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=3,
        expected_catalog_count=None,
        curated_photo_getter=photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    assert first.processed_taxa_count == 3
    counts = calls.copy()
    second = run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=3,
        expected_catalog_count=None,
        curated_photo_getter=photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    assert second.processed_taxa_count == second.target_taxa_count == second.lookup_count == 0
    assert calls == counts
    refreshed = run_catalog_media_batch(
        str(path),
        mode="refresh",
        batch_size=3,
        expected_catalog_count=None,
        curated_photo_getter=photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    assert refreshed.processed_taxa_count == 3
    assert refreshed.available_photo_count == refreshed.available_call_count == 2
    assert refreshed.unavailable_photo_count == refreshed.unavailable_call_count == 1
    assert calls["photo:Avis alpha"] == 2


def test_ordinary_refresh_never_reinterprets_curated_photos_as_gbif(
    tmp_path: Path,
) -> None:
    path = _database(tmp_path)
    calls: Counter[str] = Counter()
    photo, xeno = _getters(calls)
    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=3,
        expected_catalog_count=None,
        curated_photo_getter=photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )

    def unavailable_photo(endpoint: str, _params: dict[str, object]) -> dict[str, Any]:
        if endpoint == INATURALIST_V2_TAXA:
            return {"results": []}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    refreshed = run_catalog_media_batch(
        str(path),
        mode="refresh",
        batch_size=3,
        expected_catalog_count=None,
        curated_photo_getter=unavailable_photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    assert refreshed.processed_taxa_count == 3
    connection = duckdb.connect(str(path), read_only=True)
    photos = connection.execute(
        """SELECT species_code, source, status FROM birding_catalog_media.results
        WHERE media_kind='photo' ORDER BY species_code"""
    ).fetchall()
    calls = connection.execute(
        """SELECT species_code, source, status FROM birding_catalog_media.results
        WHERE media_kind='call' ORDER BY species_code"""
    ).fetchall()
    connection.close()
    assert photos == [
        ("alpha1", "curated_photo", "unavailable"),
        ("beta1", "curated_photo", "unavailable"),
        ("hybrid1", "curated_photo", "unavailable"),
    ]
    assert calls == [
        ("alpha1", "xeno_canto", "available"),
        ("beta1", "xeno_canto", "available"),
        ("hybrid1", "xeno_canto", "unavailable"),
    ]


def test_ordinary_apply_repairs_legacy_gbif_photo_with_curated_owner(
    tmp_path: Path,
) -> None:
    path = _database(tmp_path)
    calls: Counter[str] = Counter()
    photo, xeno = _getters(calls)
    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=3,
        expected_catalog_count=None,
        curated_photo_getter=photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    connection = duckdb.connect(str(path))
    connection.execute(
        """UPDATE birding_catalog_media.results SET source='gbif'
        WHERE species_code='alpha1' AND media_kind='photo'"""
    )
    connection.close()

    repaired = run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=1,
        expected_catalog_count=None,
        curated_photo_getter=photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    assert repaired.target_taxa_count == repaired.processed_taxa_count == 1
    connection = duckdb.connect(str(path), read_only=True)
    assert connection.execute(
        """SELECT source, status FROM birding_catalog_media.results
        WHERE species_code='alpha1' AND media_kind='photo'"""
    ).fetchone() == ("inaturalist", "available")
    assert connection.execute(
        """SELECT count(*) FROM birding_catalog_media.results
        WHERE media_kind='photo' AND source='gbif'"""
    ).fetchone() == (0,)
    connection.close()


def test_706_taxon_apply_campaign_resumes_partial_batches_until_complete(
    tmp_path: Path,
) -> None:
    path, keys = _large_database(tmp_path)
    calls: Counter[str] = Counter()
    photo_calls: Counter[str] = Counter()
    photo = _curated_getter(photo_calls, keys)

    def xeno(_endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        query = str(params["query"])
        match = re.search(r'gen:"([A-Za-z]+)" sp:"([A-Za-z]+)"', query)
        assert match is not None
        name = f"{match.group(1)} {match.group(2)}"
        calls["xeno"] += 1
        return _call(name, keys[name] + 1000)

    results = [
        run_catalog_media_batch(
            str(path),
            mode="apply",
            batch_size=250,
            curated_photo_getter=photo,
            before_inaturalist_request=lambda: None,
            xeno_getter=xeno,
            xeno_api_key="test",
        )
        for _ in range(3)
    ]
    assert len({result.run_id for result in results}) == 1
    assert [result.target_taxa_count for result in results] == [706, 706, 706]
    assert [result.processed_taxa_count for result in results] == [250, 500, 706]
    assert [result.remaining_taxa_count for result in results] == [456, 206, 0]
    connection = duckdb.connect(str(path), read_only=True)
    assert connection.execute(
        """SELECT status, target_taxa_count, processed_taxa_count
        FROM birding_catalog_media.runs"""
    ).fetchall() == [("complete", 706, 706)]
    connection.close()
    assert calls == Counter({"xeno": 624})
    assert sum(value for key, value in photo_calls.items() if key.startswith("v2:")) == 624
    assert sum(value for key, value in photo_calls.items() if key.startswith("v1:")) == 624


@pytest.mark.parametrize(
    "corruption",
    ["wrong_source", "malformed_json", "missing_selection", "empty_payload"],
)
def test_ordinary_apply_reprocesses_invalid_complete_rows(tmp_path: Path, corruption: str) -> None:
    path = _database(tmp_path)
    calls: Counter[str] = Counter()
    photo, xeno = _getters(calls)
    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=3,
        expected_catalog_count=None,
        curated_photo_getter=photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    connection = duckdb.connect(str(path))
    if corruption == "wrong_source":
        connection.execute(
            """UPDATE birding_catalog_media.results SET source='xeno_canto'
            WHERE species_code='alpha1' AND media_kind='photo'"""
        )
    elif corruption == "malformed_json":
        connection.execute(
            """UPDATE birding_catalog_media.results SET summary_json='{'
            WHERE species_code='alpha1' AND media_kind='photo'"""
        )
    elif corruption == "missing_selection":
        summary = json.loads(
            connection.execute(
                """SELECT summary_json FROM birding_catalog_media.results
            WHERE species_code='alpha1' AND media_kind='photo'"""
            ).fetchone()[0]
        )
        summary.pop("selection_reason")
        connection.execute(
            """UPDATE birding_catalog_media.results SET summary_json=?
            WHERE species_code='alpha1' AND media_kind='photo'""",
            [json.dumps(summary)],
        )
    else:
        connection.execute(
            """UPDATE birding_catalog_media.results SET payload_json='{}'
            WHERE species_code='alpha1' AND media_kind='photo'"""
        )
    connection.close()
    connection = duckdb.connect(str(path), read_only=True)
    assert inspect_catalog_media(connection, expected_catalog_count=None).target_taxa_count == 1
    connection.close()
    prior_calls = calls.copy()
    result = run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=1,
        expected_catalog_count=None,
        curated_photo_getter=photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    assert result.target_taxa_count == result.processed_taxa_count == 1
    assert result.remaining_taxa_count == 0
    assert calls["photo:Avis alpha"] == prior_calls["photo:Avis alpha"] + 1
    assert calls["xeno:Avis alpha"] == prior_calls["xeno:Avis alpha"] + 1


def test_taxon_refresh_rolls_back_prior_result_on_commit_failure(tmp_path: Path) -> None:
    path = _database(tmp_path)
    calls: Counter[str] = Counter()
    photo, xeno = _getters(calls)
    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=1,
        expected_catalog_count=None,
        curated_photo_getter=photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    connection = duckdb.connect(str(path), read_only=True)
    before = catalog_media_rows(connection, ["alpha1"])
    connection.close()

    def fail(_connection: duckdb.DuckDBPyConnection, _taxon: object) -> None:
        raise RuntimeError("injected commit failure")

    with pytest.raises(RuntimeError, match="injected commit failure"):
        run_catalog_media_batch(
            str(path),
            mode="refresh",
            batch_size=1,
            expected_catalog_count=None,
            curated_photo_getter=photo,
            before_inaturalist_request=lambda: None,
            xeno_getter=xeno,
            xeno_api_key="test",
            before_taxon_commit=fail,
        )
    connection = duckdb.connect(str(path), read_only=True)
    assert catalog_media_rows(connection, ["alpha1"]) == before
    assert connection.execute(
        "SELECT status FROM birding_catalog_media.runs WHERE mode='refresh'"
    ).fetchone() == ("failed",)
    connection.close()


def test_refresh_resumes_one_campaign_across_bounded_invocations(tmp_path: Path) -> None:
    path = _database(tmp_path)
    calls: Counter[str] = Counter()
    photo, xeno = _getters(calls)
    run_ids: list[str | None] = []
    for expected_remaining in (2, 1, 0):
        result = run_catalog_media_batch(
            str(path),
            mode="refresh",
            batch_size=1,
            expected_catalog_count=None,
            curated_photo_getter=photo,
            before_inaturalist_request=lambda: None,
            xeno_getter=xeno,
            xeno_api_key="test",
        )
        run_ids.append(result.run_id)
        assert result.processed_taxa_count == 3 - expected_remaining
        assert result.target_taxa_count == 3
        assert result.remaining_taxa_count == expected_remaining
    assert len(set(run_ids)) == 1
    connection = duckdb.connect(str(path), read_only=True)
    assert connection.execute(
        "SELECT status, processed_taxa_count FROM birding_catalog_media.runs"
    ).fetchall() == [("complete", 3)]
    connection.close()


def test_non_binomial_identity_is_unavailable_without_parent_lookup(tmp_path: Path) -> None:
    path = _database(tmp_path)
    connection = duckdb.connect(str(path))
    connection.execute(
        """UPDATE birding_agent.arizona_species_catalog
        SET scientific_name='Avis alpha subspecies' WHERE species_code='alpha1'"""
    )
    connection.close()
    calls: Counter[str] = Counter()
    photo, xeno = _getters(calls)
    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=1,
        expected_catalog_count=None,
        curated_photo_getter=photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    assert calls == Counter()
    connection = duckdb.connect(str(path), read_only=True)
    rows = catalog_media_rows(connection, ["alpha1"])
    assert {row["status"] for row in rows.values()} == {"unavailable"}
    assert all("fallback is prohibited" in row["caveats_json"] for row in rows.values())
    connection.close()


def test_oversized_selector_metadata_is_persisted_as_unavailable(tmp_path: Path) -> None:
    path = _database(tmp_path)

    curated = _curated_getter(Counter())

    def oversized(endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        payload = curated(endpoint, params)
        if endpoint.startswith("https://api.inaturalist.org/v1/taxa/"):
            payload["results"][0]["taxon_photos"][0]["photo"]["attribution"] = "x" * 20_001
        return payload

    calls: Counter[str] = Counter()
    _, xeno = _getters(calls)
    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=1,
        expected_catalog_count=None,
        curated_photo_getter=oversized,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    connection = duckdb.connect(str(path), read_only=True)
    rows = catalog_media_rows(connection, ["alpha1"])
    assert rows[("alpha1", "photo")]["status"] == "unavailable"
    assert rows[("alpha1", "call")]["status"] == "available"
    connection.close()


def test_unsafe_identity_license_and_urls_persist_typed_unavailable(tmp_path: Path) -> None:
    path = _database(tmp_path)

    curated = _curated_getter(Counter())

    def bad_photo(endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        payload = curated(endpoint, params)
        if endpoint == INATURALIST_V2_TAXA:
            payload["results"][0]["name"] = "Wrong species"
        return payload

    def bad_xeno(_endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        query = str(params["query"])
        name = "Avis alpha" if "alpha" in query else "Avis beta"
        row = _call(name, 800)["recordings"][0]
        row["file"] = "https://evil.example/audio"
        return {"recordings": [row]}

    result = run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=3,
        expected_catalog_count=None,
        curated_photo_getter=bad_photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=bad_xeno,
        xeno_api_key="test",
    )
    assert result.available_photo_count == result.available_call_count == 0
    assert result.unavailable_photo_count == result.unavailable_call_count == 3


def _curated_getter(calls: Counter[str], ids: dict[str, int] | None = None):
    resolved_ids = ids or {"Avis alpha": 301, "Avis beta": 302}
    names_by_id = {taxon_id: name for name, taxon_id in resolved_ids.items()}

    def getter(endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        if endpoint == INATURALIST_V2_TAXA:
            name = str(params["q"])
            calls[f"v2:{name}"] += 1
            return {
                "results": [
                    {
                        "id": resolved_ids[name],
                        "name": name,
                        "rank": "species",
                        "is_active": True,
                    }
                ]
            }
        match = re.fullmatch(r"https://api\.inaturalist\.org/v1/taxa/([0-9]+)", endpoint)
        if match is None or int(match.group(1)) not in names_by_id:
            raise AssertionError(f"unexpected curated endpoint {endpoint}")
        name = names_by_id[int(match.group(1))]
        photo_id = resolved_ids[name] + 1000
        calls[f"v1:{name}"] += 1
        return {
            "results": [
                {
                    "id": resolved_ids[name],
                    "name": name,
                    "rank": "species",
                    "is_active": True,
                    "taxon_photos": [
                        {
                            "photo": {
                                "id": photo_id,
                                "license_code": "cc-by",
                                "attribution": "(c) Curated Fixture, some rights reserved (CC BY)",
                                "url": (
                                    "https://inaturalist-open-data.s3.amazonaws.com/"
                                    f"photos/{photo_id}/square.jpeg"
                                ),
                                "original_dimensions": {"width": 1600, "height": 1200},
                            }
                        }
                    ],
                }
            ]
        }

    return getter


def test_photo_run_outcome_schema_upgrades_existing_table() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE SCHEMA birding_catalog_media")
    connection.execute(
        """CREATE TABLE birding_catalog_media.photo_runs (
            run_id VARCHAR PRIMARY KEY,
            status VARCHAR NOT NULL,
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
        """INSERT INTO birding_catalog_media.photo_runs
        VALUES ('legacy', 'complete', '2026-07-12T00:00:00+00:00', NULL, 1, 1, 1, 1, NULL)"""
    )
    ensure_catalog_media_tables(connection)
    assert connection.execute(
        """SELECT provider_outcomes_json, request_count, duration_ms
        FROM birding_catalog_media.photo_runs"""
    ).fetchone() == ("{}", 0, None)
    connection.close()


def test_curated_photo_dry_run_is_network_free_and_read_only(tmp_path: Path) -> None:
    path = _database(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    connection = duckdb.connect(str(path), read_only=True)
    result = inspect_catalog_photo_refresh(connection, expected_catalog_count=None)
    connection.close()
    assert result.mode == "photo_dry_run"
    assert result.catalog_count == result.target_taxa_count == result.remaining_taxa_count == 3
    assert result.processed_taxa_count == result.lookup_count == 0
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_photo_only_refresh_resumes_and_preserves_calls(tmp_path: Path) -> None:
    path = _database(tmp_path)
    legacy_calls: Counter[str] = Counter()
    photo, xeno = _getters(legacy_calls)
    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=3,
        expected_catalog_count=None,
        curated_photo_getter=photo,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    connection = duckdb.connect(str(path))
    connection.execute(
        """UPDATE birding_catalog_media.results SET source='gbif'
        WHERE media_kind='photo'"""
    )
    connection.close()
    connection = duckdb.connect(str(path), read_only=True)
    calls_before = connection.execute(
        """SELECT species_code, source_record_id, status, summary_json, payload_json,
        caveats_json, lookup_at, run_id FROM birding_catalog_media.results
        WHERE media_kind='call' ORDER BY species_code"""
    ).fetchall()
    connection.close()

    curated_calls: Counter[str] = Counter()
    getter = _curated_getter(curated_calls)
    seen = 0

    def interrupt(_taxon) -> None:
        nonlocal seen
        seen += 1
        if seen == 2:
            raise RuntimeError("photo interruption")

    with pytest.raises(RuntimeError, match="photo interruption"):
        run_catalog_photo_refresh(
            str(path),
            batch_size=3,
            expected_catalog_count=None,
            getter=getter,
            before_inaturalist_request=lambda: None,
            after_lookup=interrupt,
        )
    connection = duckdb.connect(str(path), read_only=True)
    interrupted_photos = connection.execute(
        """SELECT species_code, source FROM birding_catalog_media.results
        WHERE media_kind='photo' ORDER BY species_code"""
    ).fetchall()
    interrupted_run = connection.execute(
        """SELECT status, processed_taxa_count, lookup_count, provider_outcomes_json,
        request_count FROM birding_catalog_media.photo_runs"""
    ).fetchone()
    connection.close()
    assert interrupted_photos == [
        ("alpha1", "inaturalist"),
        ("beta1", "gbif"),
        ("hybrid1", "gbif"),
    ]
    assert interrupted_run is not None
    assert interrupted_run[:3] == ("failed", 1, 2)
    assert json.loads(interrupted_run[3]) == {"inaturalist.available": 1}
    assert interrupted_run[4] == 4  # alpha v2/v1 plus interrupted beta v2/v1

    resumed = run_catalog_photo_refresh(
        str(path),
        batch_size=3,
        expected_catalog_count=None,
        getter=getter,
        before_inaturalist_request=lambda: None,
    )
    assert resumed.mode == "photo_refresh"
    assert resumed.processed_taxa_count == resumed.target_taxa_count == 3
    assert resumed.remaining_taxa_count == 0
    assert curated_calls["v2:Avis alpha"] == curated_calls["v1:Avis alpha"] == 1
    assert curated_calls["v2:Avis beta"] == curated_calls["v1:Avis beta"] == 2
    assert sum(curated_calls.values()) == 6  # iNaturalist v2/v1 per attempt

    connection = duckdb.connect(str(path), read_only=True)
    calls_after = connection.execute(
        """SELECT species_code, source_record_id, status, summary_json, payload_json,
        caveats_json, lookup_at, run_id FROM birding_catalog_media.results
        WHERE media_kind='call' ORDER BY species_code"""
    ).fetchall()
    assert calls_after == calls_before
    photos = connection.execute(
        """SELECT species_code, source, status FROM birding_catalog_media.results
        WHERE media_kind='photo' ORDER BY species_code"""
    ).fetchall()
    assert photos == [
        ("alpha1", "inaturalist", "available"),
        ("beta1", "inaturalist", "available"),
        ("hybrid1", "curated_photo", "unavailable"),
    ]
    completed_run = connection.execute(
        """SELECT status, target_taxa_count, processed_taxa_count, lookup_count,
        provider_outcomes_json, request_count, duration_ms, safe_failure
        FROM birding_catalog_media.photo_runs"""
    ).fetchone()
    assert completed_run is not None
    assert completed_run[:4] == ("complete", 3, 3, 3)
    assert json.loads(completed_run[4]) == {
        "identity.unavailable": 1,
        "inaturalist.available": 2,
    }
    assert completed_run[5] == 6
    assert isinstance(completed_run[6], int) and completed_run[6] >= 0
    assert completed_run[7] is None
    connection.close()


def test_completed_photo_refresh_rerun_is_database_and_network_no_op(
    tmp_path: Path,
) -> None:
    path = _database(tmp_path)
    calls: Counter[str] = Counter()
    first = run_catalog_photo_refresh(
        str(path),
        batch_size=3,
        expected_catalog_count=None,
        getter=_curated_getter(calls),
        before_inaturalist_request=lambda: None,
    )
    connection = duckdb.connect(str(path), read_only=True)
    rows_before = connection.execute(
        "SELECT * FROM birding_catalog_media.results ORDER BY species_code, media_kind"
    ).fetchall()
    runs_before = connection.execute(
        "SELECT * FROM birding_catalog_media.photo_runs ORDER BY started_at"
    ).fetchall()
    connection.close()
    calls_before = calls.copy()

    def unexpected_getter(_endpoint: str, _params: dict[str, object]) -> dict[str, Any]:
        raise AssertionError("completed current identity was queried again")

    second = run_catalog_photo_refresh(
        str(path),
        batch_size=3,
        expected_catalog_count=None,
        getter=unexpected_getter,
        before_inaturalist_request=lambda: None,
    )
    connection = duckdb.connect(str(path), read_only=True)
    assert (
        connection.execute(
            "SELECT * FROM birding_catalog_media.results ORDER BY species_code, media_kind"
        ).fetchall()
        == rows_before
    )
    assert (
        connection.execute(
            "SELECT * FROM birding_catalog_media.photo_runs ORDER BY started_at"
        ).fetchall()
        == runs_before
    )
    connection.close()
    assert calls == calls_before
    assert second.run_id == first.run_id
    assert second.processed_taxa_count == second.complete_taxa_count == 3
    assert second.remaining_taxa_count == 0
    assert second.lookup_count == first.lookup_count == 2


def test_photo_only_refresh_reconciles_prior_campaign_terminal_without_network(
    tmp_path: Path,
) -> None:
    path = _database(tmp_path)
    calls: Counter[str] = Counter()
    first = run_catalog_photo_refresh(
        str(path),
        batch_size=3,
        expected_catalog_count=None,
        getter=_curated_getter(calls),
        before_inaturalist_request=lambda: None,
    )
    assert first.run_id is not None
    connection = duckdb.connect(str(path))
    connection.execute(
        """UPDATE birding_catalog_media.results SET run_id='prior_campaign'
        WHERE species_code='hybrid1' AND media_kind='photo'"""
    )
    connection.execute(
        """UPDATE birding_catalog_media.photo_runs
        SET processed_taxa_count=3, request_count=0,
            provider_outcomes_json='{"inaturalist.available":2}'
        WHERE run_id=?""",
        [first.run_id],
    )
    connection.close()
    calls_before = calls.copy()

    result = run_catalog_photo_refresh(
        str(path),
        batch_size=3,
        expected_catalog_count=None,
        getter=lambda *_: (_ for _ in ()).throw(AssertionError("unexpected provider request")),
        before_inaturalist_request=lambda: None,
    )

    assert calls == calls_before
    assert result.run_id == first.run_id
    assert result.processed_taxa_count == result.complete_taxa_count == 3
    assert result.lookup_count == 2
    assert result.request_count == 4
    connection = duckdb.connect(str(path), read_only=True)
    assert connection.execute(
        """SELECT count(*) FROM birding_catalog_media.results
        WHERE media_kind='photo' AND run_id=?""",
        [first.run_id],
    ).fetchone() == (3,)
    run = connection.execute(
        """SELECT status, processed_taxa_count, lookup_count, request_count,
        provider_outcomes_json FROM birding_catalog_media.photo_runs WHERE run_id=?""",
        [first.run_id],
    ).fetchone()
    connection.close()
    assert run is not None
    assert run[:4] == ("complete", 3, 2, 4)
    assert json.loads(run[4]) == {
        "identity.unavailable": 1,
        "inaturalist.available": 2,
    }


def test_photo_only_retry_targets_provider_failure_then_becomes_no_op(
    tmp_path: Path,
) -> None:
    path = _database(tmp_path)
    calls: Counter[str] = Counter()
    base = _curated_getter(calls)
    failed = False

    def transient(endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        nonlocal failed
        if endpoint == INATURALIST_V2_TAXA and params.get("q") == "Avis alpha" and not failed:
            failed = True
            calls["v2:Avis alpha"] += 1
            raise TimeoutError("temporary")
        return base(endpoint, params)

    first = run_catalog_photo_refresh(
        str(path),
        batch_size=3,
        expected_catalog_count=None,
        getter=transient,
        before_inaturalist_request=lambda: None,
    )
    assert first.remaining_taxa_count == 1
    assert first.request_count == 3
    connection = duckdb.connect(str(path), read_only=True)
    failed_run = connection.execute(
        """SELECT status, processed_taxa_count, lookup_count, request_count,
        provider_outcomes_json, safe_failure, duration_ms
        FROM birding_catalog_media.photo_runs"""
    ).fetchone()
    connection.close()
    assert failed_run is not None
    assert failed_run[:4] == ("failed", 2, 2, 3)
    assert json.loads(failed_run[4]) == {
        "identity.unavailable": 1,
        "inaturalist.available": 1,
        "inaturalist.failed.transport": 1,
    }
    assert failed_run[5] == "retryable_results_remaining"
    assert isinstance(failed_run[6], int)

    second = run_catalog_photo_refresh(
        str(path),
        batch_size=3,
        expected_catalog_count=None,
        getter=base,
        before_inaturalist_request=lambda: None,
    )
    assert second.remaining_taxa_count == 0
    assert second.processed_taxa_count == 3
    assert second.request_count == 5
    calls_before = calls.copy()
    third = run_catalog_photo_refresh(
        str(path),
        batch_size=3,
        expected_catalog_count=None,
        getter=lambda *_: (_ for _ in ()).throw(AssertionError("unexpected retry")),
        before_inaturalist_request=lambda: None,
    )
    assert third.request_count == 5
    assert calls == calls_before
