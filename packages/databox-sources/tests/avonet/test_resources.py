from __future__ import annotations

import hashlib
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest
import yaml
from databox_sources.avonet import source
from openpyxl import Workbook


class FakeResponse:
    def __init__(self, body: bytes, *, status: int, headers: dict[str, str]) -> None:
        self._body = BytesIO(body)
        self.status = status
        self.headers: Mapping[str, str] = headers

    def read(self, amount: int = -1) -> bytes:
        return self._body.read(amount)

    def close(self) -> None:
        self._body.close()


def _row(name: str = "Accipiter albogularis", avibase_id: str = "AVIBASE-BBB59880") -> list[Any]:
    return [
        name,
        "Accipitridae",
        "Accipitriformes",
        avibase_id,
        5,
        2,
        0,
        3,
        4,
        27.7,
        17.8,
        10.6,
        14.7,
        62,
        235.2,
        81.8,
        159.5,
        33.9,
        169,
        248.8,
        "Dunning",
        "NA",
        "NO",
        "NA",
        "NA",
        "Forest",
        1,
        "NA",
        "Carnivore",
        "Vertivore",
        "Insessorial",
    ]


def workbook_bytes(*rows: list[Any], headers: tuple[str, ...] = source.EXPECTED_HEADERS) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = source.AVONET_WORKSHEET
    worksheet.append(list(headers))
    for row in rows:
        worksheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _signed_redirect(**overrides: str) -> str:
    query = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": "ABCDEFGHIJKLMNOP/20260710/eu-west-1/s3/aws4_request",
        "X-Amz-Date": "20260710T160615Z",
        "X-Amz-Expires": "10",
        "X-Amz-SignedHeaders": "host",
        "X-Amz-Signature": "a" * 64,
    }
    query.update(overrides)
    encoded = "&".join(f"{key}={value}" for key, value in query.items())
    return f"https://s3-eu-west-1.amazonaws.com{source._REDIRECT_PATH}?{encoded}"


def test_config_identity_matches_runtime_contract() -> None:
    config = yaml.safe_load(Path(source.__file__).with_name("config.yaml").read_text())["source"]
    assert config == {
        "name": "avonet",
        "dataset_name": "raw_avonet",
        "internal_staging_schema": "raw_avonet_staging",
        "doi": source.AVONET_DOI,
        "version": source.AVONET_VERSION,
        "license": source.AVONET_LICENSE,
        "source_url": source.AVONET_SOURCE_URL,
        "file_id": source.AVONET_FILE_ID,
        "expected_size_bytes": source.AVONET_EXPECTED_SIZE,
        "expected_md5": source.AVONET_EXPECTED_MD5,
        "worksheet": source.AVONET_WORKSHEET,
        "expected_rows": source.AVONET_EXPECTED_ROWS,
    }


def test_download_requires_exact_one_hop_signed_redirect_length_and_hash(tmp_path: Path) -> None:
    assert source.AVONET_MAX_BYTES == 24 * 1024 * 1024
    body = workbook_bytes(_row())
    calls: list[str] = []

    def http_open(request: Request, timeout: float) -> FakeResponse:
        calls.append(request.full_url)
        if len(calls) == 1:
            assert timeout == source._CONNECT_TIMEOUT_SECONDS
            return FakeResponse(b"", status=302, headers={"Location": _signed_redirect()})
        assert timeout == source._READ_TIMEOUT_SECONDS
        return FakeResponse(body, status=200, headers={"Content-Length": str(len(body))})

    destination = tmp_path / "avonet.xlsx"
    source.download_avonet_workbook(
        destination,
        http_open=http_open,
        expected_size=len(body),
        expected_md5=hashlib.md5(body, usedforsecurity=False).hexdigest(),
    )
    assert destination.read_bytes() == body
    assert calls[0] == source.AVONET_SOURCE_URL
    assert calls[1].startswith(f"https://{source._REDIRECT_HOST}{source._REDIRECT_PATH}?")


def test_download_suppresses_signed_target_from_network_error(tmp_path: Path) -> None:
    signed = _signed_redirect()

    def http_open(request: Request, timeout: float) -> FakeResponse:
        if request.full_url == source.AVONET_SOURCE_URL:
            return FakeResponse(b"", status=302, headers={"Location": signed})
        raise RuntimeError(f"failed URL {request.full_url}")

    with pytest.raises(ValueError, match="storage request failed") as error:
        source.download_avonet_workbook(tmp_path / "avonet.xlsx", http_open=http_open)
    assert signed not in str(error.value)


@pytest.mark.parametrize(
    "redirect",
    [
        "http://s3-eu-west-1.amazonaws.com/pfigshare-u-files/34480856/AVONETSupplementarydataset1.xlsx",
        "https://evil.example/pfigshare-u-files/34480856/AVONETSupplementarydataset1.xlsx",
        "https://user@s3-eu-west-1.amazonaws.com/pfigshare-u-files/34480856/AVONETSupplementarydataset1.xlsx",
        "https://s3-eu-west-1.amazonaws.com:443/pfigshare-u-files/34480856/AVONETSupplementarydataset1.xlsx",
        _signed_redirect(**{"X-Amz-Expires": "61"}),
        _signed_redirect(**{"X-Amz-Algorithm": "other"}),
        _signed_redirect(**{"X-Amz-Signature": "short"}),
        _signed_redirect() + "&unexpected=value",
    ],
)
def test_download_rejects_unapproved_redirects_before_target_fetch(
    tmp_path: Path, redirect: str
) -> None:
    calls = 0

    def http_open(request: Request, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(b"", status=302, headers={"Location": redirect})

    with pytest.raises(ValueError, match="redirect"):
        source.download_avonet_workbook(tmp_path / "avonet.xlsx", http_open=http_open)
    assert calls == 1
    assert not (tmp_path / "avonet.xlsx").exists()


@pytest.mark.parametrize("failure", ["length", "hash", "second_redirect", "cap"])
def test_download_fails_closed_for_invalid_final_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    body = b"fixture"

    def http_open(request: Request, timeout: float) -> FakeResponse:
        if request.full_url == source.AVONET_SOURCE_URL:
            return FakeResponse(b"", status=302, headers={"Location": _signed_redirect()})
        headers = {"Content-Length": str(len(body))}
        status = 200
        if failure == "length":
            headers["Content-Length"] = str(len(body) + 1)
        if failure == "second_redirect":
            status = 302
            headers["Location"] = _signed_redirect()
        return FakeResponse(body, status=status, headers=headers)

    if failure == "cap":
        monkeypatch.setattr(source, "AVONET_MAX_BYTES", len(body) - 1)
    expected_md5 = (
        "0" * 32 if failure == "hash" else hashlib.md5(body, usedforsecurity=False).hexdigest()
    )
    with pytest.raises(ValueError):
        source.download_avonet_workbook(
            tmp_path / "avonet.xlsx",
            http_open=http_open,
            expected_size=len(body),
            expected_md5=expected_md5,
        )


def test_parse_preserves_text_and_normalizes_all_exact_na_fields(tmp_path: Path) -> None:
    row = _row()
    row[21] = "Citation with trailing space "
    row[25] = "NA"
    row[28] = "NA"
    row[29] = "NA"
    path = tmp_path / "avonet.xlsx"
    path.write_bytes(workbook_bytes(row))
    parsed = source.parse_avonet_workbook(path, loaded_at="2026-07-10T00:00:00Z", expected_rows=1)[
        0
    ]
    assert parsed["mass_reference_other"] == "Citation with trailing space "
    assert parsed["habitat"] is None
    assert parsed["trophic_level"] is None
    assert parsed["trophic_niche"] is None


def test_parse_exact_sheet_headers_types_nulls_and_provenance(tmp_path: Path) -> None:
    path = tmp_path / "avonet.xlsx"
    path.write_bytes(workbook_bytes(_row()))
    rows = source.parse_avonet_workbook(path, loaded_at="2026-07-10T00:00:00Z", expected_rows=1)
    assert rows == [
        {
            "source_scientific_name": "Accipiter albogularis",
            "family": "Accipitridae",
            "order_name": "Accipitriformes",
            "avibase_id": "AVIBASE-BBB59880",
            "total_individuals": 5,
            "female_individuals": 2,
            "male_individuals": 0,
            "unknown_sex_individuals": 3,
            "complete_measures": 4,
            "beak_length_culmen_mm": 27.7,
            "beak_length_nares_mm": 17.8,
            "beak_width_mm": 10.6,
            "beak_depth_mm": 14.7,
            "tarsus_length_mm": 62.0,
            "wing_length_mm": 235.2,
            "kipps_distance_mm": 81.8,
            "secondary_length_mm": 159.5,
            "hand_wing_index": 33.9,
            "tail_length_mm": 169.0,
            "mass_g": 248.8,
            "mass_source": "Dunning",
            "mass_reference_other": None,
            "inference": False,
            "traits_inferred": None,
            "reference_species": None,
            "habitat": "Forest",
            "habitat_density_code": 1,
            "migration_code": None,
            "trophic_level": "Carnivore",
            "trophic_niche": "Vertivore",
            "primary_lifestyle": "Insessorial",
            "dataset_doi": source.AVONET_DOI,
            "dataset_version": source.AVONET_VERSION,
            "dataset_license": source.AVONET_LICENSE,
            "source_file_id": source.AVONET_FILE_ID,
            "source_file_md5": source.AVONET_EXPECTED_MD5,
            "source_url": source.AVONET_SOURCE_URL,
            "loaded_at": "2026-07-10T00:00:00Z",
        }
    ]


@pytest.mark.parametrize("mutation", ["header", "type", "duplicate_id", "duplicate_name", "sheet"])
def test_parse_rejects_schema_type_and_grain_drift(tmp_path: Path, mutation: str) -> None:
    headers = source.EXPECTED_HEADERS
    rows = [_row()]
    if mutation == "header":
        headers = (*headers[:-1], "Changed")
    elif mutation == "type":
        rows[0][4] = "5"
    elif mutation == "duplicate_id":
        rows.append(_row("Other species", "AVIBASE-BBB59880"))
    elif mutation == "duplicate_name":
        rows.append(_row("Accipiter albogularis", "AVIBASE-OTHER"))
    path = tmp_path / "avonet.xlsx"
    path.write_bytes(workbook_bytes(*rows, headers=headers))
    if mutation == "sheet":
        workbook = Workbook()
        worksheet = workbook.active
        assert worksheet is not None
        worksheet.title = "Wrong"
        workbook.save(path)
        workbook.close()
    with pytest.raises(ValueError, match="AVONET"):
        source.parse_avonet_workbook(
            path,
            loaded_at="2026-07-10T00:00:00Z",
            expected_rows=len(rows),
        )
