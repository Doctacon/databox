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
    inspect_catalog_media,
    run_catalog_media_batch,
)


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

    def gbif(_endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        name = str(params["scientificName"])
        calls[f"gbif:{name}"] += 1
        return _photo(name, keys[name])

    def xeno(_endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        query = str(params["query"])
        name = next(item for item in keys if all(part in query for part in item.split()))
        calls[f"xeno:{name}"] += 1
        return _call(name, keys[name] + 1000)

    return gbif, xeno


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
    gbif, xeno = _getters(calls)
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
            gbif_getter=gbif,
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
        gbif_getter=gbif,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    assert result.complete_taxa_count == 3
    assert result.target_taxa_count == result.processed_taxa_count == 3
    assert result.remaining_taxa_count == 0
    assert calls["gbif:Avis alpha"] == calls["xeno:Avis alpha"] == 1
    assert calls["gbif:Avis beta"] == calls["xeno:Avis beta"] == 2
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
    gbif, xeno = _getters(calls)
    first = run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=3,
        expected_catalog_count=None,
        gbif_getter=gbif,
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
        gbif_getter=gbif,
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
        gbif_getter=gbif,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    assert refreshed.processed_taxa_count == 3
    assert refreshed.available_photo_count == refreshed.available_call_count == 2
    assert refreshed.unavailable_photo_count == refreshed.unavailable_call_count == 1
    assert calls["gbif:Avis alpha"] == 2


def test_706_taxon_apply_campaign_resumes_partial_batches_until_complete(
    tmp_path: Path,
) -> None:
    path, keys = _large_database(tmp_path)
    calls: Counter[str] = Counter()

    def gbif(_endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        name = str(params["scientificName"])
        calls["gbif"] += 1
        return _photo(name, keys[name])

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
            gbif_getter=gbif,
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
    assert calls == Counter({"gbif": 624, "xeno": 624})


@pytest.mark.parametrize(
    "corruption",
    ["wrong_source", "malformed_json", "missing_selection", "empty_payload"],
)
def test_ordinary_apply_reprocesses_invalid_complete_rows(tmp_path: Path, corruption: str) -> None:
    path = _database(tmp_path)
    calls: Counter[str] = Counter()
    gbif, xeno = _getters(calls)
    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=3,
        expected_catalog_count=None,
        gbif_getter=gbif,
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
        gbif_getter=gbif,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    assert result.target_taxa_count == result.processed_taxa_count == 1
    assert result.remaining_taxa_count == 0
    assert calls["gbif:Avis alpha"] == prior_calls["gbif:Avis alpha"] + 1
    assert calls["xeno:Avis alpha"] == prior_calls["xeno:Avis alpha"] + 1


def test_taxon_refresh_rolls_back_prior_result_on_commit_failure(tmp_path: Path) -> None:
    path = _database(tmp_path)
    calls: Counter[str] = Counter()
    gbif, xeno = _getters(calls)
    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=1,
        expected_catalog_count=None,
        gbif_getter=gbif,
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
            gbif_getter=gbif,
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
    gbif, xeno = _getters(calls)
    run_ids: list[str | None] = []
    for expected_remaining in (2, 1, 0):
        result = run_catalog_media_batch(
            str(path),
            mode="refresh",
            batch_size=1,
            expected_catalog_count=None,
            gbif_getter=gbif,
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
    gbif, xeno = _getters(calls)
    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=1,
        expected_catalog_count=None,
        gbif_getter=gbif,
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

    def oversized(_endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        payload = _photo(str(params["scientificName"]), 700)
        payload["results"][0]["media"][0]["creator"] = "x" * 20_001
        return payload

    calls: Counter[str] = Counter()
    _, xeno = _getters(calls)
    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=1,
        expected_catalog_count=None,
        gbif_getter=oversized,
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

    def bad_gbif(_endpoint: str, params: dict[str, object]) -> dict[str, Any]:
        return _photo(str(params["scientificName"]), 900) | {
            "results": [
                {
                    **_photo(str(params["scientificName"]), 900)["results"][0],
                    "acceptedScientificName": "Wrong species",
                }
            ]
        }

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
        gbif_getter=bad_gbif,
        xeno_getter=bad_xeno,
        xeno_api_key="test",
    )
    assert result.available_photo_count == result.available_call_count == 0
    assert result.unavailable_photo_count == result.unavailable_call_count == 3
