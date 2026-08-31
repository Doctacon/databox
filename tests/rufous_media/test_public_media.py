from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import databox.public_media as public_media
import duckdb
import httpx
import pytest
from databox.public_media import (
    MAX_DOWNLOAD_BYTES,
    PUBLIC_BASE_URL,
    PublicMediaError,
    normalize_license,
    prepare_public_media,
    validate_source_image_url,
    validate_source_page_url,
)
from databox.public_media_approval import (
    SELECTION_REASON,
    canonical_approval_json,
    empty_approval_ledger,
)
from databox.public_restricted_marks import restricted_usfws_mark_reason
from PIL import Image

_CREATE_TABLE = """
CREATE SCHEMA rufous_public;
CREATE TABLE rufous_public.usfws_commercial_image (
    species_code VARCHAR,
    common_name VARCHAR,
    scientific_name VARCHAR,
    source_page_url VARCHAR,
    source_image_url VARCHAR,
    creator VARCHAR,
    license VARCHAR,
    title VARCHAR,
    caption VARCHAR,
    alt_text VARCHAR,
    source_published_at TIMESTAMPTZ,
    source_width BIGINT,
    source_height BIGINT,
    mime_type VARCHAR,
    discovery_method VARCHAR,
    loaded_at TIMESTAMPTZ
)
"""

_CREATE_INATURALIST_TABLE = """
CREATE TABLE rufous_public.inaturalist_commercial_image (
    species_code VARCHAR,
    common_name VARCHAR,
    scientific_name VARCHAR,
    source_page_url VARCHAR,
    source_image_url VARCHAR,
    creator VARCHAR,
    license VARCHAR,
    title VARCHAR,
    caption VARCHAR,
    alt_text VARCHAR,
    source_published_at TIMESTAMPTZ,
    source_width BIGINT,
    source_height BIGINT,
    mime_type VARCHAR,
    discovery_method VARCHAR,
    loaded_at TIMESTAMPTZ
)
"""

_CREATE_WIKIMEDIA_TABLE = """
CREATE TABLE rufous_public.wikimedia_commercial_image (
    species_code VARCHAR,
    common_name VARCHAR,
    scientific_name VARCHAR,
    source_page_url VARCHAR,
    source_image_url VARCHAR,
    creator VARCHAR,
    license VARCHAR,
    title VARCHAR,
    caption VARCHAR,
    alt_text VARCHAR,
    source_published_at TIMESTAMPTZ,
    source_width BIGINT,
    source_height BIGINT,
    mime_type VARCHAR,
    discovery_method VARCHAR,
    loaded_at TIMESTAMPTZ
)
"""


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "species_code": "rufhum",
        "common_name": "Rufous Hummingbird",
        "scientific_name": "Selasphorus rufus",
        "source_page_url": "https://www.fws.gov/media/rufous-hummingbird",
        "source_image_url": "https://www.fws.gov/sites/default/files/birds/rufous.png",
        "creator": "Peter Pearsall/USFWS",
        "license": "Public Domain",
        "title": "Rufous hummingbird on a branch",
        "caption": "A male Rufous Hummingbird perches on a bare branch.",
        "alt_text": "A small orange Rufous Hummingbird perched on a branch",
        "source_published_at": datetime(2024, 6, 20, tzinfo=UTC),
        "source_width": 900,
        "source_height": 600,
        "mime_type": "image/png",
        "discovery_method": "usfws_species_facet",
        "loaded_at": datetime(2026, 8, 3, 12, 30, tzinfo=UTC),
    }
    row.update(overrides)
    return row


def _inaturalist_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "species_code": "amewig",
        "common_name": "American Wigeon",
        "scientific_name": "Mareca americana",
        "source_page_url": "https://www.inaturalist.org/photos/2498155",
        "source_image_url": (
            "https://inaturalist-open-data.s3.amazonaws.com/photos/2498155/original.jpg"
        ),
        "creator": "Jane Naturalist",
        "license": "CC BY 4.0",
        "title": "American Wigeon on open water",
        "caption": "A live American Wigeon resting on open water.",
        "alt_text": "A live American Wigeon resting on open water",
        "source_published_at": datetime(2024, 7, 1, tzinfo=UTC),
        "source_width": 900,
        "source_height": 600,
        "mime_type": "image/jpeg",
        "discovery_method": "inaturalist_exact_taxon",
        "loaded_at": datetime(2026, 8, 3, 12, 31, tzinfo=UTC),
    }
    row.update(overrides)
    return row


def _wikimedia_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "species_code": "eletrg",
        "common_name": "Elegant Trogon",
        "scientific_name": "Trogon elegans",
        "source_page_url": (
            "https://commons.wikimedia.org/wiki/File:Elegant_Trogon_(Trogon_elegans).jpg"
        ),
        "source_image_url": (
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/"
            "Elegant_Trogon_%28Trogon_elegans%29.jpg/"
            "960px-Elegant_Trogon_%28Trogon_elegans%29.jpg"
        ),
        "creator": "Example Commons Photographer",
        "license": "CC BY-SA 4.0",
        "title": "Elegant Trogon photograph",
        "caption": "A live Elegant Trogon perched on a branch.",
        "alt_text": "Elegant Trogon perched on a branch",
        "source_published_at": datetime(2024, 7, 2, tzinfo=UTC),
        "source_width": 960,
        "source_height": 640,
        "mime_type": "image/jpeg",
        "discovery_method": "wikimedia_commons_curated_file",
        "loaded_at": datetime(2026, 8, 4, 14, tzinfo=UTC),
    }
    row.update(overrides)
    return row


def _database(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "media.duckdb"
    with duckdb.connect(str(path)) as connection:
        connection.execute(_CREATE_TABLE)
        _insert_rows(connection, rows)
    return path


def _mixed_database(
    tmp_path: Path,
    *,
    usfws_rows: list[dict[str, object]],
    inaturalist_rows: list[dict[str, object]],
) -> Path:
    path = tmp_path / "mixed-media.duckdb"
    with duckdb.connect(str(path)) as connection:
        connection.execute(_CREATE_TABLE)
        connection.execute(_CREATE_INATURALIST_TABLE)
        _insert_rows(connection, usfws_rows)
        _insert_rows(
            connection,
            inaturalist_rows,
            table="rufous_public.inaturalist_commercial_image",
        )
    return path


def _insert_rows(
    connection: duckdb.DuckDBPyConnection,
    rows: list[dict[str, object]],
    *,
    table: str = "rufous_public.usfws_commercial_image",
) -> None:
    placeholders = ", ".join("?" for _ in public_media.SOURCE_COLUMNS)
    columns = ", ".join(public_media.SOURCE_COLUMNS)
    for row in rows:
        connection.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            [row[column] for column in public_media.SOURCE_COLUMNS],
        )


def _png(
    width: int = 900,
    height: int = 600,
    color: tuple[int, int, int] = (179, 83, 41),
) -> bytes:
    image = Image.new("RGB", (width, height), color)
    output = BytesIO()
    image.save(output, format="PNG", pnginfo=None)
    return output.getvalue()


def _jpeg(
    width: int = 900,
    height: int = 600,
    color: tuple[int, int, int] = (179, 83, 41),
) -> bytes:
    image = Image.new("RGB", (width, height), color)
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def _webp(width: int = 900, height: int = 600) -> bytes:
    image = Image.new("RGB", (width, height), (179, 83, 41))
    output = BytesIO()
    image.save(output, format="WEBP")
    return output.getvalue()


def _gif(width: int = 900, height: int = 600) -> bytes:
    image = Image.new("RGB", (width, height), (179, 83, 41))
    output = BytesIO()
    image.save(output, format="GIF")
    return output.getvalue()


def _animated_webp(width: int = 900, height: int = 600) -> bytes:
    first = Image.new("RGB", (width, height), (179, 83, 41))
    second = Image.new("RGB", (width, height), (20, 80, 160))
    output = BytesIO()
    first.save(
        output,
        format="WEBP",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
    )
    return output.getvalue()


def _oriented_jpeg() -> bytes:
    image = Image.new("RGB", (40, 20), (12, 90, 130))
    exif = Image.Exif()
    exif[274] = 6
    output = BytesIO()
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


@pytest.mark.parametrize(
    ("raw", "expected", "url"),
    [
        (
            "Public Domain",
            "Public Domain",
            "https://www.fws.gov/notices",
        ),
        ("CC0", "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
        ("CC BY 2.5", "CC BY 2.5", "https://creativecommons.org/licenses/by/2.5/"),
        (
            "CC BY-SA 4.0",
            "CC BY-SA 4.0",
            "https://creativecommons.org/licenses/by-sa/4.0/",
        ),
        (
            "Creative Commons Attribution ShareAlike 3.0",
            "CC BY-SA 3.0",
            "https://creativecommons.org/licenses/by-sa/3.0/",
        ),
        (
            "http://creativecommons.org/licenses/by/1.0/legalcode/",
            "CC BY 1.0",
            "https://creativecommons.org/licenses/by/1.0/",
        ),
    ],
)
def test_license_allowlist_normalizes_commercial_terms(raw: str, expected: str, url: str) -> None:
    assert normalize_license(raw) == (expected, url)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "CC BY",
        "CC BY-NC 4.0",
        "CC BY-ND 4.0",
        "CC0 4.0",
        "All Rights Reserved",
        "Public Domain?",
    ],
)
def test_license_allowlist_fails_closed(raw: object) -> None:
    with pytest.raises(PublicMediaError):
        normalize_license(raw)


@pytest.mark.parametrize(
    ("raw", "expected", "url"),
    [
        (
            "CC0 1.0",
            "CC0 1.0",
            "https://creativecommons.org/publicdomain/zero/1.0/",
        ),
        (
            "CC BY 4.0",
            "CC BY 4.0",
            "https://creativecommons.org/licenses/by/4.0/",
        ),
        (
            "https://creativecommons.org/licenses/by-sa/4.0/",
            "CC BY-SA 4.0",
            "https://creativecommons.org/licenses/by-sa/4.0/",
        ),
    ],
)
def test_inaturalist_license_allowlist_is_strictly_commercial_and_current(
    raw: str,
    expected: str,
    url: str,
) -> None:
    assert normalize_license(raw, provider="inaturalist") == (expected, url)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "Public Domain",
        "CC BY 3.0",
        "CC BY-SA 2.5",
        "CC BY-NC 4.0",
        "CC BY-ND 4.0",
        "CC BY-NC-SA 4.0",
        "All Rights Reserved",
    ],
)
def test_inaturalist_license_allowlist_fails_closed(raw: object) -> None:
    with pytest.raises(PublicMediaError):
        normalize_license(raw, provider="inaturalist")


def test_source_urls_require_exact_safe_fws_origins() -> None:
    assert (
        validate_source_page_url("https://www.fws.gov/media/rufous-hummingbird-5")
        == "https://www.fws.gov/media/rufous-hummingbird-5"
    )
    assert (
        validate_source_image_url(
            "https://www.fws.gov/sites/default/files/birds/rufous%20hummingbird.jpg"
        )
        == "https://www.fws.gov/sites/default/files/birds/rufous%20hummingbird.jpg"
    )
    assert (
        validate_source_image_url(
            "https://www.fws.gov/sites/default/files/styles/max_650x650/public/"
            "birds/rufous.jpg?itok=az_09-Z"
        )
        == "https://www.fws.gov/sites/default/files/styles/max_650x650/public/"
        "birds/rufous.jpg?itok=az_09-Z"
    )

    unsafe_pages = [
        "http://www.fws.gov/media/rufous-hummingbird",
        "https://www.fws.gov.evil.example/media/rufous-hummingbird",
        "https://user@www.fws.gov/media/rufous-hummingbird",
        "https://www.fws.gov/media/Rufous_Hummingbird",
        "https://www.fws.gov/media/rufous-hummingbird?download=1",
        "https://www.fws.gov/media/rufous-\nhummingbird",
    ]
    unsafe_images = [
        "https://evil.example/sites/default/files/rufous.jpg",
        "https://www.fws.gov:443/sites/default/files/rufous.jpg",
        "https://www.fws.gov/sites/default/files/birds/../secret.jpg",
        "https://www.fws.gov/sites/default/files/birds/rufous.svg",
        "https://www.fws.gov/sites/default/files/birds/rufous.jpg?token=secret",
    ]
    for value in unsafe_pages:
        with pytest.raises(PublicMediaError):
            validate_source_page_url(value)
    for value in unsafe_images:
        with pytest.raises(PublicMediaError):
            validate_source_image_url(value)


def test_inaturalist_source_urls_require_one_exact_matching_photo() -> None:
    page_url = "https://www.inaturalist.org/photos/2498155"
    image_url = "https://inaturalist-open-data.s3.amazonaws.com/photos/2498155/original.jpg"
    assert validate_source_page_url(page_url, provider="inaturalist") == page_url
    assert validate_source_image_url(image_url, provider="inaturalist") == image_url

    row = public_media.SourceImageRow.from_values({**_inaturalist_row(), "provider": "inaturalist"})
    assert row.provider == "inaturalist"
    assert row.source_page_url == page_url
    assert row.source_image_url == image_url

    unsafe_pages = [
        "http://www.inaturalist.org/photos/2498155",
        "https://inaturalist.org/photos/2498155",
        "https://www.inaturalist.org/photos/0",
        "https://www.inaturalist.org/photos/2498155/",
        "https://www.inaturalist.org/photos/2498155?download=1",
        "https://www.inaturalist.org/observations/2498155",
        "https://www.inaturalist.org.evil.example/photos/2498155",
    ]
    unsafe_images = [
        "https://inaturalist-open-data.s3.amazonaws.com/photos/2498155/large.jpg",
        "https://inaturalist-open-data.s3.amazonaws.com/photos/2498155/original.svg",
        "https://inaturalist-open-data.s3.amazonaws.com/photos/0/original.jpg",
        "https://inaturalist-open-data.s3.amazonaws.com/photos/2498155/original.jpg?x=1",
        "https://evil.example/photos/2498155/original.jpg",
    ]
    for value in unsafe_pages:
        with pytest.raises(PublicMediaError):
            validate_source_page_url(value, provider="inaturalist")
    for value in unsafe_images:
        with pytest.raises(PublicMediaError):
            validate_source_image_url(value, provider="inaturalist")

    with pytest.raises(PublicMediaError, match="different photos"):
        public_media.SourceImageRow.from_values(
            {
                **_inaturalist_row(
                    source_image_url=(
                        "https://inaturalist-open-data.s3.amazonaws.com/photos/2498156/original.jpg"
                    )
                ),
                "provider": "inaturalist",
            }
        )


def test_unknown_media_provider_fails_closed() -> None:
    with pytest.raises(PublicMediaError, match="provider is not reviewed"):
        public_media.SourceImageRow.from_values(
            {**_inaturalist_row(), "provider": "wikimedia_commons"}
        )
    with pytest.raises(PublicMediaError, match="provider is not reviewed"):
        normalize_license("CC BY 4.0", provider="wikimedia_commons")


def test_wikimedia_provider_uses_exact_commons_files_and_commercial_licenses(
    tmp_path: Path,
) -> None:
    row = public_media.SourceImageRow.from_values({**_wikimedia_row(), "provider": "wikimedia"})
    assert row.provider == "wikimedia"
    assert row.license == "CC BY-SA 4.0"
    assert normalize_license("Public Domain", provider="wikimedia") == (
        "Public Domain",
        "https://commons.wikimedia.org/wiki/Commons:Copyright_tags/General_public_domain",
    )

    for unsafe in (
        "https://commons.wikimedia.org/wiki/Category:Trogon_elegans",
        "https://commons.wikimedia.org/wiki/File:Trogon_elegans.jpg?download=1",
        "https://commons.wikimedia.org/wiki/File:folder%2Fbird.jpg",
        "https://commons.wikimedia.org.evil.example/wiki/File:Trogon_elegans.jpg",
    ):
        with pytest.raises(PublicMediaError):
            validate_source_page_url(unsafe, provider="wikimedia")
    for unsafe in (
        "https://upload.wikimedia.org/wikipedia/commons/a/ab/Trogon_elegans.svg",
        "https://upload.wikimedia.org/wikipedia/commons/a/ab/Trogon_elegans.jpg?x=1",
        (
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/"
            "Trogon_elegans.jpg/960px-Other_bird.jpg"
        ),
        "https://commons.wikimedia.org/wiki/File:Trogon_elegans.jpg",
    ):
        with pytest.raises(PublicMediaError):
            validate_source_image_url(unsafe, provider="wikimedia")
    with pytest.raises(PublicMediaError, match="different files"):
        public_media.SourceImageRow.from_values(
            {
                **_wikimedia_row(
                    source_image_url=(
                        "https://upload.wikimedia.org/wikipedia/commons/a/ab/Other_bird.jpg"
                    )
                ),
                "provider": "wikimedia",
            }
        )

    database = tmp_path / "wikimedia.duckdb"
    with duckdb.connect(str(database)) as connection:
        connection.execute("CREATE SCHEMA rufous_public")
        connection.execute(_CREATE_WIKIMEDIA_TABLE)
        _insert_rows(
            connection,
            [_wikimedia_row()],
            table="rufous_public.wikimedia_commercial_image",
        )
    with _client(
        lambda _request: httpx.Response(
            200,
            headers={"content-type": "image/jpeg"},
            content=_jpeg(width=960, height=640),
        )
    ) as client:
        result = prepare_public_media(
            database,
            tmp_path / "wikimedia-prepared",
            provider="wikimedia",
            client=client,
        )
    item = json.loads(result.manifest_path.read_text())["items"][0]
    assert item["provider"] == "wikimedia"
    assert item["media_id"].startswith("wikimedia-")
    assert item["attribution_id"].startswith("wikimedia-attribution-")


@pytest.mark.parametrize("malformed_escape", ["%", "%2", "%GG"])
def test_wikimedia_file_urls_reject_malformed_percent_escapes(
    malformed_escape: str,
) -> None:
    page_url = f"https://commons.wikimedia.org/wiki/File:Elegant{malformed_escape}_Trogon.jpg"
    image_url = (
        f"https://upload.wikimedia.org/wikipedia/commons/a/ab/Elegant{malformed_escape}_Trogon.jpg"
    )

    with pytest.raises(PublicMediaError, match="malformed escaping"):
        validate_source_page_url(page_url, provider="wikimedia")
    with pytest.raises(PublicMediaError, match="malformed escaping"):
        validate_source_image_url(image_url, provider="wikimedia")


def test_mixed_provider_preparation_preserves_provenance_and_content_addressing(
    tmp_path: Path,
) -> None:
    database = _mixed_database(
        tmp_path,
        usfws_rows=[_row()],
        inaturalist_rows=[_inaturalist_row()],
    )
    usfws_source = _png(color=(179, 83, 41))
    inaturalist_source = _jpeg()
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.host == "www.fws.gov":
            return httpx.Response(
                200,
                headers={"content-type": "image/png"},
                content=usfws_source,
            )
        if request.url.host == "inaturalist-open-data.s3.amazonaws.com":
            return httpx.Response(
                200,
                headers={"content-type": "image/jpeg"},
                content=inaturalist_source,
            )
        raise AssertionError(f"unexpected media origin: {request.url}")

    output = tmp_path / "prepared"
    with _client(handler) as client:
        result = prepare_public_media(database, output, client=client)

    assert result.items == 2
    assert result.species == 2
    assert len(calls) == 2
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    by_provider = {item["provider"]: item for item in manifest["items"]}
    assert set(by_provider) == {"inaturalist", "usfws"}

    inaturalist = by_provider["inaturalist"]
    assert inaturalist["media_id"] == "inaturalist-2498155"
    assert inaturalist["attribution_id"] == "inaturalist-attribution-2498155"
    assert inaturalist["source_page_url"] == "https://www.inaturalist.org/photos/2498155"
    assert inaturalist["source_image_url"] == (
        "https://inaturalist-open-data.s3.amazonaws.com/photos/2498155/original.jpg"
    )
    assert inaturalist["license"] == "CC BY 4.0"
    assert inaturalist["license_url"] == "https://creativecommons.org/licenses/by/4.0/"

    usfws = by_provider["usfws"]
    # Adding another provider must not churn the long-lived USFWS identity
    # contract or invalidate existing immutable releases.
    assert usfws["media_id"] == "usfws-6571ccf424cccd1168ebe3d0"
    assert usfws["attribution_id"].startswith("usfws-attribution-")
    assert usfws["license"] == "Public Domain"
    assert usfws["license_url"] == "https://www.fws.gov/notices"

    for item in by_provider.values():
        expected_path = f"objects/{item['sha256'][:2]}/{item['sha256']}.webp"
        assert item["object_path"] == expected_path
        assert item["url"] == f"{PUBLIC_BASE_URL}/{expected_path}"
        payload = (output / expected_path).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == item["sha256"]
        with Image.open(BytesIO(payload)) as image:
            assert image.format == "WEBP"


def test_inaturalist_scope_never_requires_or_reads_usfws_model(tmp_path: Path) -> None:
    database = tmp_path / "inaturalist-delta.duckdb"
    with duckdb.connect(str(database)) as connection:
        connection.execute("CREATE SCHEMA rufous_public")
        # A malformed table with the production USFWS name proves the scoped
        # reader does not even inspect that provider's schema.
        connection.execute("CREATE TABLE rufous_public.usfws_commercial_image (unexpected VARCHAR)")
        connection.execute(_CREATE_INATURALIST_TABLE)
        _insert_rows(
            connection,
            [_inaturalist_row()],
            table="rufous_public.inaturalist_commercial_image",
        )

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.url.host == "inaturalist-open-data.s3.amazonaws.com"
        return httpx.Response(
            200,
            headers={"content-type": "image/jpeg"},
            content=_jpeg(),
        )

    with _client(handler) as client:
        result = prepare_public_media(
            database,
            tmp_path / "prepared",
            client=client,
            provider="inaturalist",
        )

    assert result.items == 1
    assert len(calls) == 1
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert {item["provider"] for item in manifest["items"]} == {"inaturalist"}

    with pytest.raises(PublicMediaError, match="exact reviewed schema"):
        prepare_public_media(database, tmp_path / "full-release")


def test_inaturalist_approval_scope_downloads_only_selected_pages_and_binds_hashes(
    tmp_path: Path,
) -> None:
    selected_row = _inaturalist_row()
    ignored_row = _inaturalist_row(
        species_code="annhum",
        common_name="Anna's Hummingbird",
        scientific_name="Calypte anna",
        source_page_url="https://www.inaturalist.org/photos/171955255",
        source_image_url=(
            "https://inaturalist-open-data.s3.amazonaws.com/photos/171955255/original.jpg"
        ),
        title="Anna's Hummingbird perched",
        caption="A live Anna's Hummingbird perched on a branch.",
        alt_text="A live Anna's Hummingbird perched on a branch",
    )
    database = _mixed_database(
        tmp_path,
        usfws_rows=[_row()],
        inaturalist_rows=[selected_row, ignored_row],
    )
    selected_source = _jpeg()
    source_row = public_media.SourceImageRow.from_values(
        {**selected_row, "provider": "inaturalist"}
    )
    expected, _payload, _mime = public_media._prepare_image(
        selected_source,
        source_row,
        response_mime_type="image/jpeg",
    )
    ledger = empty_approval_ledger()
    ledger["selections"] = [
        {
            "sha256": expected.sha256,
            "decision": "selected",
            "reason": SELECTION_REASON,
            "reviewed_at": "2026-08-03",
            "reviewed_by": "Test Human",
            "scientific_name": selected_row["scientific_name"],
            "source_page_urls": [selected_row["source_page_url"]],
        }
    ]
    approvals = tmp_path / "approvals.json"
    approvals.write_bytes(canonical_approval_json(ledger))
    calls: list[str] = []

    def selected_handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert str(request.url) == selected_row["source_image_url"]
        return httpx.Response(
            200,
            headers={"content-type": "image/jpeg"},
            content=selected_source,
        )

    with _client(selected_handler) as client:
        result = prepare_public_media(
            database,
            tmp_path / "selected-only",
            client=client,
            provider="inaturalist",
            approval_path=approvals,
        )

    assert calls == [selected_row["source_image_url"]]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["items"]) == 1
    assert manifest["items"][0]["sha256"] == expected.sha256

    def changed_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "image/jpeg"},
            content=_jpeg(color=(20, 80, 160)),
        )

    failed_output = tmp_path / "changed-pixels"
    with _client(changed_handler) as client:
        with pytest.raises(PublicMediaError, match="visual approval failed"):
            prepare_public_media(
                database,
                failed_output,
                client=client,
                provider="inaturalist",
                approval_path=approvals,
            )
    assert not failed_output.exists()


def test_explicit_provider_scope_fails_closed_for_unknown_or_missing_model(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path, [_row()])

    with pytest.raises(PublicMediaError, match="provider is not reviewed"):
        prepare_public_media(database, tmp_path / "unknown", provider="wikimedia_commons")
    with pytest.raises(PublicMediaError, match="inaturalist_commercial_image is missing"):
        prepare_public_media(database, tmp_path / "missing", provider="inaturalist")
    with pytest.raises(PublicMediaError, match="wikimedia_commercial_image is missing"):
        prepare_public_media(database, tmp_path / "missing-wikimedia", provider="wikimedia")


def test_prepare_cli_forwards_explicit_provider_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_prepare(
        database_path: str | Path,
        output_dir: str | Path,
        **kwargs: object,
    ) -> public_media.PreparationResult:
        captured.update(
            database_path=database_path,
            output_dir=output_dir,
            **kwargs,
        )
        output = Path(output_dir)
        return public_media.PreparationResult(output, output / "manifest.json", 1, 1, 1)

    monkeypatch.setattr(public_media, "prepare_public_media", fake_prepare)

    assert (
        public_media.main(
            [
                "--database-path",
                str(tmp_path / "media.duckdb"),
                "--output-dir",
                str(tmp_path / "prepared"),
                "--provider",
                "inaturalist",
                "--approvals",
                str(tmp_path / "approvals.json"),
            ]
        )
        == 0
    )
    assert captured["provider"] == "inaturalist"
    assert captured["approval_path"] == tmp_path / "approvals.json"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        (
            {"title": "U.S. Fish & Wildlife Service LÓGÓ"},
            "service_or_agency_logo_or_seal",
        ),
        (
            {"caption": "Official agency-seal artwork"},
            "service_or_agency_logo_or_seal",
        ),
        (
            {"alt_text": "The 2026 Junior Duck-Stamp artwork"},
            "federal_or_junior_duck_stamp",
        ),
        (
            {
                "source_page_url": (
                    "https://www.fws.gov/media/federal-aid-in-wildlife-restoration-symbol"
                )
            },
            "federal_aid_restoration_symbol",
        ),
        (
            {
                "source_image_url": (
                    "https://www.fws.gov/sites/default/files/"
                    "sport%252Dfish%252Drestoration%252Dsymbol.png"
                )
            },
            "federal_aid_restoration_symbol",
        ),
        (
            {
                "title": "Blue Goose",
                "caption": "National Wildlife Refuge System symbol",
            },
            "blue_goose_refuge_mark",
        ),
    ],
)
def test_restricted_usfws_marks_fail_before_download(
    tmp_path: Path,
    overrides: dict[str, object],
    reason: str,
) -> None:
    database = _database(tmp_path, [_row(**overrides)])
    network_calls = 0

    def forbidden_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal network_calls
        network_calls += 1
        raise AssertionError("restricted marks must fail before network access")

    with _client(forbidden_handler) as client:
        with pytest.raises(PublicMediaError, match=reason):
            prepare_public_media(database, tmp_path / "prepared", client=client)

    assert network_calls == 0


def test_restricted_mark_gate_does_not_confuse_birds_or_animals_with_marks() -> None:
    assert (
        restricted_usfws_mark_reason(
            (
                "Blue Goose in flight",
                "A blue-morph Snow Goose flies above a harbor seal colony.",
                "https://www.fws.gov/media/snow-goose-blue-morph",
            )
        )
        is None
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("creator", "--"),
        ("creator", "Unknown"),
        ("creator", "Rufous Hummingbird"),
        ("creator", "A" * 201),
        ("creator", "Jane <script>"),
        ("title", "Rufous Hummingbird\nportrait"),
        ("caption", "A perched bird\tnear flowers"),
        ("alt_text", "A perched bird\nnear flowers"),
    ],
)
def test_preparation_independently_rejects_weak_credit_and_control_text(
    tmp_path: Path, field: str, value: str
) -> None:
    database = _database(tmp_path, [_row(**{field: value})])

    def forbidden_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("metadata validation must happen before network access")

    with _client(forbidden_handler) as client:
        with pytest.raises(PublicMediaError):
            prepare_public_media(database, tmp_path / "prepared", client=client)


def test_preparation_deduplicates_bytes_but_preserves_distinct_metadata_rows(
    tmp_path: Path,
) -> None:
    database = _database(
        tmp_path,
        [
            _row(),
            _row(
                species_code="acowoo",
                common_name="Acorn Woodpecker",
                scientific_name="Melanerpes formicivorus",
                title="Two birds sharing one USFWS photograph",
            ),
        ],
    )
    image_bytes = _png()
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert "RufousMediaBuilder" in request.headers["user-agent"]
        assert "connor@loughondata.com" in request.headers["user-agent"]
        return httpx.Response(
            200,
            headers={"content-type": "image/png", "content-length": str(len(image_bytes))},
            content=image_bytes,
        )

    output = tmp_path / "prepared"
    with _client(handler) as client:
        result = prepare_public_media(
            database, output, client=client, sleeper=lambda _seconds: None
        )

    assert result.items == 2
    assert result.objects == 1
    assert result.species == 2
    assert len(calls) == 1
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["schema_version"] == 1
    assert manifest["mode"] == "rufous-media-preparation"
    assert manifest["generated_at"] == "2026-08-03T12:30:00Z"
    assert public_media._SHA256.fullmatch(manifest["preparer_fingerprint"])
    assert public_media._SHA256.fullmatch(manifest["cache_identity"])
    assert manifest["counts"] == {
        "items": 2,
        "objects": 1,
        "species": 2,
        "unavailable_items": 0,
        "unavailable_source_objects": 0,
    }
    assert manifest["unavailable_items"] == []
    assert [item["species_code"] for item in manifest["items"]] == ["acowoo", "rufhum"]

    first, second = manifest["items"]
    assert first["sha256"] == second["sha256"]
    assert first["media_id"] != second["media_id"]
    assert first["license"] == "Public Domain"
    assert first["caption"] is not None
    assert first["byte_size"] > 0
    assert isinstance(first["hero_score"], int)
    relative = f"objects/{first['sha256'][:2]}/{first['sha256']}.webp"
    assert first["object_path"] == relative
    assert first["url"] == f"{PUBLIC_BASE_URL}/{relative}"

    object_path = output / relative
    payload = object_path.read_bytes()
    assert len(payload) <= 1024 * 1024
    assert hashlib.sha256(payload).hexdigest() == first["sha256"]
    with Image.open(object_path) as image:
        assert image.format == "WEBP"
        assert image.size == (650, 433)
        assert not image.getexif()


def test_prepared_objects_are_staged_as_processed_without_retaining_payloads(
    tmp_path: Path,
) -> None:
    database = _database(
        tmp_path,
        [
            _row(),
            _row(
                species_code="acowoo",
                common_name="Acorn Woodpecker",
                scientific_name="Melanerpes formicivorus",
                source_page_url="https://www.fws.gov/media/acorn-woodpecker",
                source_image_url="https://www.fws.gov/sites/default/files/birds/acorn.png",
            ),
        ],
    )
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 2:
            stages = list(tmp_path.glob(".prepared.stage-*"))
            assert len(stages) == 1
            assert len(list(stages[0].rglob("*.webp"))) == 1
        color = (20, 80, 160) if request.url.path.endswith("acorn.png") else (179, 83, 41)
        payload = _png(color=color)
        return httpx.Response(200, headers={"content-type": "image/png"}, content=payload)

    with _client(handler) as client:
        result = prepare_public_media(database, tmp_path / "prepared", client=client)

    assert calls == 2
    assert result.objects == 2
    assert "payload" not in public_media.PreparedObject.__dataclass_fields__


def test_preparation_applies_exif_orientation_and_strips_metadata(tmp_path: Path) -> None:
    source = _oriented_jpeg()
    row = _row(
        source_image_url="https://www.fws.gov/sites/default/files/birds/oriented.jpg",
        source_width=40,
        source_height=20,
        mime_type="image/jpeg",
    )
    database = _database(tmp_path, [row])

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=source)

    with _client(handler) as client:
        result = prepare_public_media(database, tmp_path / "prepared", client=client)
    manifest = json.loads(result.manifest_path.read_text())
    item = manifest["items"][0]
    assert (item["width"], item["height"]) == (20, 40)
    with Image.open(result.output_dir / item["object_path"]) as image:
        assert image.size == (20, 40)
        assert not image.getexif()


def test_allowlisted_http_mime_can_differ_from_the_source_hint(tmp_path: Path) -> None:
    image_bytes = _png()
    database = _database(
        tmp_path,
        [
            _row(
                source_image_url=(
                    "https://www.fws.gov/sites/default/files/birds/misleading-extension.jpg"
                ),
                mime_type="image/jpeg",
            )
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept"] == "image/jpeg"
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=image_bytes,
        )

    with _client(handler) as client:
        result = prepare_public_media(database, tmp_path / "prepared", client=client)

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["items"][0]["source_mime_type"] == "image/jpeg"
    assert manifest["items"][0]["decoded_source_mime_type"] == "image/png"
    with Image.open(result.output_dir / manifest["items"][0]["object_path"]) as image:
        assert image.format == "WEBP"


def test_allowlisted_decoded_mime_can_differ_from_model_and_http_hints(
    tmp_path: Path,
) -> None:
    database = _database(
        tmp_path,
        [
            _row(
                source_image_url="https://www.fws.gov/sites/default/files/birds/vireo.png",
                mime_type="image/png",
            )
        ],
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=_jpeg(),
        )

    with _client(handler) as client:
        result = prepare_public_media(database, tmp_path / "prepared", client=client)

    manifest = json.loads(result.manifest_path.read_text())
    item = manifest["items"][0]
    assert item["source_mime_type"] == "image/png"
    assert item["decoded_source_mime_type"] == "image/jpeg"


@pytest.mark.parametrize(
    ("payload_factory", "decoded_mime"),
    [
        (_png, "image/png"),
        (_jpeg, "image/jpeg"),
        (_webp, "image/webp"),
    ],
)
def test_decoded_source_format_allowlist_is_explicit(
    tmp_path: Path,
    payload_factory: Callable[[], bytes],
    decoded_mime: str,
) -> None:
    database = _database(tmp_path, [_row()])

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=payload_factory(),
        )

    with _client(handler) as client:
        result = prepare_public_media(database, tmp_path / "prepared", client=client)

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["items"][0]["decoded_source_mime_type"] == decoded_mime


def test_unsupported_decoded_source_format_fails_closed(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=_gif(),
        )

    with _client(handler) as client:
        with pytest.raises(PublicMediaError, match="unsupported format"):
            prepare_public_media(database, tmp_path / "prepared", client=client)


def test_corrupt_allowlisted_source_format_fails_closed(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=b"not an image",
        )

    with _client(handler) as client:
        with pytest.raises(PublicMediaError, match="safely decoded"):
            prepare_public_media(database, tmp_path / "prepared", client=client)


def test_animated_allowlisted_source_format_fails_closed(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "image/webp"},
            content=_animated_webp(),
        )

    with _client(handler) as client:
        with pytest.raises(PublicMediaError, match="animated source"):
            prepare_public_media(database, tmp_path / "prepared", client=client)


def test_retry_is_bounded_and_can_recover(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    image_bytes = _png()
    calls = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503)
        return httpx.Response(200, headers={"content-type": "image/png"}, content=image_bytes)

    with _client(handler) as client:
        prepare_public_media(
            database,
            tmp_path / "prepared",
            client=client,
            sleeper=sleeps.append,
        )
    assert calls == 3
    assert sleeps == [1.0, 2.0]


@pytest.mark.parametrize("content_type", [None, "application/octet-stream"])
def test_missing_or_unsupported_http_mime_exhausts_bounded_retries(
    tmp_path: Path,
    content_type: str | None,
) -> None:
    database = _database(tmp_path, [_row()])
    calls = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        headers = {"content-type": content_type} if content_type is not None else None
        return httpx.Response(200, headers=headers, content=b"not-an-image")

    with _client(handler) as client:
        result = prepare_public_media(
            database,
            tmp_path / "prepared",
            client=client,
            sleeper=sleeps.append,
        )

    assert calls == 6
    assert sleeps == [1.0, 2.0, 4.0, 8.0, 16.0]
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["counts"] == {
        "items": 0,
        "objects": 0,
        "species": 0,
        "unavailable_items": 1,
        "unavailable_source_objects": 1,
    }
    assert manifest["unavailable_items"][0]["reason"] == (
        "unsupported_http_content_type" if content_type is not None else "missing_http_content_type"
    )


def test_one_unavailable_source_is_audited_once_for_all_semantic_rows(
    tmp_path: Path,
) -> None:
    unavailable_url = "https://www.fws.gov/sites/default/files/birds/unavailable.png"
    database = _database(
        tmp_path,
        [
            _row(),
            _row(
                species_code="acowoo",
                common_name="Acorn Woodpecker",
                scientific_name="Melanerpes formicivorus",
                source_page_url="https://www.fws.gov/media/acorn-woodpecker",
                source_image_url=unavailable_url,
            ),
            _row(
                species_code="yelwar",
                common_name="Yellow Warbler",
                scientific_name="Setophaga petechia",
                source_page_url="https://www.fws.gov/media/yellow-warbler",
                source_image_url=unavailable_url,
            ),
        ],
    )
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("rufous.png"):
            return httpx.Response(
                200,
                headers={"content-type": "image/png"},
                content=_png(),
            )
        return httpx.Response(503)

    with _client(handler) as client:
        result = prepare_public_media(
            database,
            tmp_path / "prepared",
            client=client,
            sleeper=lambda _seconds: None,
        )

    assert calls.count("/sites/default/files/birds/unavailable.png") == 6
    assert calls.count("/sites/default/files/birds/rufous.png") == 1
    assert result.items == 1
    assert result.objects == 1
    assert result.species == 1
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["counts"] == {
        "items": 1,
        "objects": 1,
        "species": 1,
        "unavailable_items": 2,
        "unavailable_source_objects": 1,
    }
    assert [item["species_code"] for item in manifest["unavailable_items"]] == [
        "acowoo",
        "yelwar",
    ]
    assert {item["source_page_url"] for item in manifest["unavailable_items"]} == {
        "https://www.fws.gov/media/acorn-woodpecker",
        "https://www.fws.gov/media/yellow-warbler",
    }
    assert {item["source_image_url"] for item in manifest["unavailable_items"]} == {unavailable_url}
    assert {(item["reason"], item["attempts"]) for item in manifest["unavailable_items"]} == {
        ("retryable_http_503", 6)
    }


def test_truncated_body_is_retried_within_the_same_bound(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    image_bytes = _png()
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                headers={"content-type": "image/png", "content-length": "20"},
                content=b"truncated",
            )
        return httpx.Response(
            200,
            headers={"content-type": "image/png", "content-length": str(len(image_bytes))},
            content=image_bytes,
        )

    with _client(handler) as client:
        prepare_public_media(
            database,
            tmp_path / "prepared",
            client=client,
            sleeper=lambda _seconds: None,
        )
    assert calls == 2


def test_unsafe_redirect_is_rejected_before_following(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"location": "https://evil.example/bird.png"})

    with _client(handler) as client:
        with pytest.raises(PublicMediaError, match="exact HTTPS fws.gov origin"):
            prepare_public_media(database, tmp_path / "prepared", client=client)
    assert calls == 1
    assert not (tmp_path / "prepared").exists()


def test_wikimedia_redirect_cannot_change_reviewed_file_identity(tmp_path: Path) -> None:
    database = tmp_path / "wikimedia-redirect.duckdb"
    with duckdb.connect(str(database)) as connection:
        connection.execute("CREATE SCHEMA rufous_public")
        connection.execute(_CREATE_WIKIMEDIA_TABLE)
        _insert_rows(
            connection,
            [_wikimedia_row()],
            table="rufous_public.wikimedia_commercial_image",
        )
    calls: list[str] = []
    substituted_url = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Other_bird.jpg"

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": substituted_url})

    with _client(handler) as client:
        with pytest.raises(PublicMediaError, match="changed the reviewed file identity"):
            prepare_public_media(
                database,
                tmp_path / "wikimedia-redirect-prepared",
                provider="wikimedia",
                client=client,
            )
    assert calls == [_wikimedia_row()["source_image_url"]]
    assert not (tmp_path / "wikimedia-redirect-prepared").exists()


def test_oversized_download_is_rejected_without_allocating_it(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "image/png",
                "content-length": str(MAX_DOWNLOAD_BYTES + 1),
            },
            content=b"small",
        )

    with _client(handler) as client:
        with pytest.raises(PublicMediaError, match="download-size limit"):
            prepare_public_media(database, tmp_path / "prepared", client=client)
    assert not (tmp_path / "prepared").exists()


def test_decompression_bomb_style_pixel_limit_is_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _png(4, 4)
    database = _database(tmp_path, [_row(source_width=3, source_height=3)])
    monkeypatch.setattr(public_media, "MAX_SOURCE_PIXELS", 10)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=source)

    with _client(handler) as client:
        with pytest.raises(PublicMediaError, match="decoded source image exceeds"):
            prepare_public_media(database, tmp_path / "prepared", client=client)


def test_verified_cache_reuse_needs_no_network_and_is_stable(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    output = tmp_path / "prepared"
    image_bytes = _png()

    def initial_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=image_bytes)

    with _client(initial_handler) as client:
        prepare_public_media(database, output, client=client)
    before = (output / "manifest.json").read_bytes()

    def forbidden_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("verified cache reuse must not access the network")

    with _client(forbidden_handler) as client:
        result = prepare_public_media(database, output, client=client)
    assert result.items == 1
    assert (output / "manifest.json").read_bytes() == before


def test_cache_reuses_good_webp_but_retries_and_recovers_unavailable_source(
    tmp_path: Path,
) -> None:
    unavailable_path = "/sites/default/files/birds/acorn.png"
    database = _database(
        tmp_path,
        [
            _row(),
            _row(
                species_code="acowoo",
                common_name="Acorn Woodpecker",
                scientific_name="Melanerpes formicivorus",
                source_page_url="https://www.fws.gov/media/acorn-woodpecker",
                source_image_url=f"https://www.fws.gov{unavailable_path}",
            ),
        ],
    )
    output = tmp_path / "prepared"

    def initial_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == unavailable_path:
            return httpx.Response(503)
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=_png(),
        )

    with _client(initial_handler) as client:
        first = prepare_public_media(
            database,
            output,
            client=client,
            sleeper=lambda _seconds: None,
        )
    first_manifest = json.loads(first.manifest_path.read_text())
    good_item = first_manifest["items"][0]
    good_payload = (output / good_item["object_path"]).read_bytes()
    assert first_manifest["counts"]["unavailable_source_objects"] == 1

    calls: list[str] = []

    def recovery_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.url.path == unavailable_path
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=_png(color=(20, 80, 160)),
        )

    with _client(recovery_handler) as client:
        second = prepare_public_media(database, output, client=client)

    assert calls == [unavailable_path]
    assert second.items == 2
    assert second.objects == 2
    second_manifest = json.loads(second.manifest_path.read_text())
    assert second_manifest["unavailable_items"] == []
    assert second_manifest["counts"]["unavailable_items"] == 0
    recovered_good = next(
        item for item in second_manifest["items"] if item["species_code"] == "rufhum"
    )
    assert recovered_good["sha256"] == good_item["sha256"]
    assert (output / recovered_good["object_path"]).read_bytes() == good_payload


def test_unavailable_manifest_tampering_is_rejected_by_complete_cache_identity(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path, [_row()])
    output = tmp_path / "prepared"

    def unavailable_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with _client(unavailable_handler) as client:
        result = prepare_public_media(
            database,
            output,
            client=client,
            sleeper=lambda _seconds: None,
        )
    manifest = json.loads(result.manifest_path.read_text())
    manifest["unavailable_items"][0]["reason"] = "retryable_http_502"
    result.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PublicMediaError, match="cache identity"):
        public_media._load_cache(
            output,
            preparer_fingerprint=manifest["preparer_fingerprint"],
        )


def test_decoded_source_mime_tampering_is_rejected_by_cache_identity(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path, [_row()])
    output = tmp_path / "prepared"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=_png(),
        )

    with _client(handler) as client:
        result = prepare_public_media(database, output, client=client)
    manifest = json.loads(result.manifest_path.read_text())
    manifest["items"][0]["decoded_source_mime_type"] = "image/jpeg"
    result.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PublicMediaError, match="cache identity"):
        public_media._load_cache(
            output,
            preparer_fingerprint=manifest["preparer_fingerprint"],
        )


def test_cache_identity_excludes_refresh_timestamps(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    output = tmp_path / "prepared"
    image_bytes = _png()

    def initial_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=image_bytes)

    with _client(initial_handler) as client:
        prepare_public_media(database, output, client=client)
    before = json.loads((output / "manifest.json").read_text())

    with duckdb.connect(str(database)) as connection:
        connection.execute(
            "UPDATE rufous_public.usfws_commercial_image "
            "SET loaded_at = TIMESTAMPTZ '2026-08-04 12:30:00+00'"
        )

    def forbidden_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("loaded_at must not invalidate prepared image bytes")

    with _client(forbidden_handler) as client:
        prepare_public_media(database, output, client=client)
    after = json.loads((output / "manifest.json").read_text())

    assert after["cache_identity"] == before["cache_identity"]
    assert after["generated_at"] == "2026-08-04T12:30:00Z"
    assert after["items"][0]["loaded_at"] == "2026-08-04T12:30:00Z"


def test_restored_cache_reuses_unchanged_rows_when_dataset_grows(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    output = tmp_path / "prepared"
    first_image = _png()

    def initial_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=first_image)

    with _client(initial_handler) as client:
        prepare_public_media(database, output, client=client)

    new_row = _row(
        species_code="acowoo",
        common_name="Acorn Woodpecker",
        scientific_name="Melanerpes formicivorus",
        source_page_url="https://www.fws.gov/media/acorn-woodpecker",
        source_image_url="https://www.fws.gov/sites/default/files/birds/acorn.png",
    )
    with duckdb.connect(str(database)) as connection:
        _insert_rows(connection, [new_row])

    calls: list[str] = []

    def new_only_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.url.path.endswith("acorn.png")
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=_png(color=(20, 80, 160)),
        )

    with _client(new_only_handler) as client:
        result = prepare_public_media(database, output, client=client)

    assert calls == ["/sites/default/files/birds/acorn.png"]
    assert result.items == 2
    assert result.objects == 2


def test_invalid_existing_manifest_is_rejected_without_replacement(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    output = tmp_path / "prepared"
    image_bytes = _png()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=image_bytes)

    with _client(handler) as client:
        prepare_public_media(database, output, client=client)
    (output / "manifest.json").write_text("{not valid JSON", encoding="utf-8")

    def forbidden_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("unsafe output rejection must happen before network access")

    with _client(forbidden_handler) as client:
        with pytest.raises(PublicMediaError, match="valid Rufous media manifest"):
            prepare_public_media(database, output, client=client)

    assert (output / "manifest.json").read_text(encoding="utf-8") == "{not valid JSON"


def test_invalid_existing_object_is_rejected_without_replacement(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    output = tmp_path / "prepared"
    image_bytes = _png()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=image_bytes)

    with _client(handler) as client:
        first = prepare_public_media(database, output, client=client)
    manifest = json.loads(first.manifest_path.read_text())
    (output / manifest["items"][0]["object_path"]).write_bytes(b"corrupt")

    object_path = output / manifest["items"][0]["object_path"]

    def forbidden_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("unsafe output rejection must happen before network access")

    with _client(forbidden_handler) as client:
        with pytest.raises(PublicMediaError, match="changed while reading|hash does not match"):
            prepare_public_media(database, output, client=client)
    assert object_path.read_bytes() == b"corrupt"


def test_nonempty_arbitrary_output_is_never_replaced(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    output = tmp_path / "pictures"
    output.mkdir()
    sentinel = output / "family-photo.txt"
    sentinel.write_text("keep me", encoding="utf-8")

    def forbidden_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("unsafe output rejection must happen before network access")

    with _client(forbidden_handler) as client:
        with pytest.raises(PublicMediaError, match="valid Rufous media manifest"):
            prepare_public_media(database, output, client=client)

    assert sentinel.read_text(encoding="utf-8") == "keep me"
    assert list(output.iterdir()) == [sentinel]


def test_symbolic_link_output_is_rejected_without_touching_its_target(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    target = tmp_path / "pictures"
    target.mkdir()
    sentinel = target / "family-photo.txt"
    sentinel.write_text("keep me", encoding="utf-8")
    output = tmp_path / "prepared"
    output.symlink_to(target, target_is_directory=True)

    def forbidden_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("unsafe output rejection must happen before network access")

    with _client(forbidden_handler) as client:
        with pytest.raises(PublicMediaError, match="symbolic link"):
            prepare_public_media(database, output, client=client)

    assert output.is_symlink()
    assert sentinel.read_text(encoding="utf-8") == "keep me"


def test_empty_existing_output_directory_is_allowed(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    output = tmp_path / "prepared"
    output.mkdir()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=_png())

    with _client(handler) as client:
        result = prepare_public_media(database, output, client=client)

    assert result.items == 1
    assert result.manifest_path.is_file()


def test_valid_output_with_unmanifested_file_is_never_replaced(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    output = tmp_path / "prepared"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=_png())

    with _client(handler) as client:
        prepare_public_media(database, output, client=client)
    extra = output / "unrelated.txt"
    extra.write_text("do not delete", encoding="utf-8")

    with _client(handler) as client:
        with pytest.raises(PublicMediaError, match="exact Rufous manifest"):
            prepare_public_media(database, output, client=client)

    assert extra.read_text(encoding="utf-8") == "do not delete"


def test_failed_media_tree_install_restores_last_good_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, [_row()])
    output = tmp_path / "prepared"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=_png())

    with _client(handler) as client:
        prepare_public_media(database, output, client=client)
    before = {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()
    }
    stage = tmp_path / "replacement-stage"
    shutil.copytree(output, stage)
    expected = public_media._validate_output_target(output)
    real_replace = public_media.os.replace

    def fail_install(source: object, destination: object) -> None:
        if Path(source) == stage and Path(destination) == output:
            raise OSError("simulated interrupted install")
        real_replace(source, destination)

    monkeypatch.setattr(public_media.os, "replace", fail_install)

    with pytest.raises(PublicMediaError, match="atomically publish"):
        public_media._publish_staged_tree(stage, output, expected=expected)

    assert {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()
    } == before
    assert stage.is_dir()
    assert not list(tmp_path.glob(".prepared.backup-*"))


def test_semantic_cache_identity_covers_attribution_and_preparer_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = _row()
    base = public_media.SourceImageRow.from_values(values)
    fingerprint = "a" * 64
    base_identity = public_media._cache_identity([(base, "image/png")], fingerprint)
    changes: list[tuple[str, object]] = [
        ("species_code", "acowoo"),
        ("common_name", "Acorn Woodpecker"),
        ("scientific_name", "Melanerpes formicivorus"),
        ("source_page_url", "https://www.fws.gov/media/acorn-woodpecker"),
        ("source_image_url", "https://www.fws.gov/sites/default/files/birds/acorn.png"),
        ("creator", "Jane Birder/USFWS"),
        ("license", "CC BY 4.0"),
        ("title", "A different reviewed title"),
        ("caption", "A different reviewed caption."),
        ("alt_text", "A different accessible bird description"),
        ("source_published_at", datetime(2024, 6, 21, tzinfo=UTC)),
        ("source_width", 901),
        ("source_height", 601),
        ("mime_type", "image/webp"),
        ("discovery_method", "usfws_exact_scientific_name"),
    ]
    for field, value in changes:
        changed_values = dict(values)
        changed_values[field] = value
        changed = public_media.SourceImageRow.from_values(changed_values)
        assert public_media._cache_identity([(changed, "image/png")], fingerprint) != base_identity

    refreshed_values = dict(values)
    refreshed_values["loaded_at"] = datetime(2026, 8, 4, tzinfo=UTC)
    refreshed = public_media.SourceImageRow.from_values(refreshed_values)
    assert public_media._cache_identity([(refreshed, "image/png")], fingerprint) == base_identity
    assert public_media._cache_identity([(base, "image/jpeg")], fingerprint) != base_identity
    assert public_media._cache_identity([(base, "image/png")], "b" * 64) != base_identity

    original_fingerprint = public_media._preparer_fingerprint()
    expected = hashlib.sha256()
    expected.update(Path(public_media.__file__).read_bytes())
    expected.update(b"\x00rufous-restricted-mark-policy\x00")
    expected.update(Path(public_media.restricted_marks.__file__).read_bytes())
    expected.update(b"\x00rufous-preparer-runtime\x00")
    expected.update(
        public_media._canonical_json_bytes(
            {
                "pillow_version": public_media.PIL.__version__,
                "webp_version": str(
                    getattr(public_media.Image.core, "webp_version", "unavailable")
                ),
            }
        )
    )
    assert original_fingerprint == expected.hexdigest()
    monkeypatch.setattr(public_media.PIL, "__version__", "changed-for-test")
    assert public_media._preparer_fingerprint() != original_fingerprint


def test_eligible_row_and_object_caps_fail_before_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        _row(),
        _row(
            species_code="acowoo",
            common_name="Acorn Woodpecker",
            scientific_name="Melanerpes formicivorus",
            source_page_url="https://www.fws.gov/media/acorn-woodpecker",
            source_image_url="https://www.fws.gov/sites/default/files/birds/acorn.png",
        ),
    ]
    database = _database(tmp_path, rows)

    def forbidden_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("bounded input failures must happen before network access")

    monkeypatch.setattr(public_media, "MAX_ELIGIBLE_ROWS", 1)
    with _client(forbidden_handler) as client:
        with pytest.raises(PublicMediaError, match="reviewed row limit"):
            prepare_public_media(database, tmp_path / "row-cap", client=client)

    monkeypatch.setattr(public_media, "MAX_ELIGIBLE_ROWS", 2)
    monkeypatch.setattr(public_media, "MAX_PREPARED_OBJECTS", 1)
    with _client(forbidden_handler) as client:
        with pytest.raises(PublicMediaError, match="prepared-object candidate limit"):
            prepare_public_media(database, tmp_path / "object-cap", client=client)


def test_total_prepared_byte_cap_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, [_row()])
    image_bytes = _png()
    monkeypatch.setattr(public_media, "MAX_TOTAL_PREPARED_BYTES", 1)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=image_bytes)

    output = tmp_path / "prepared"
    with _client(handler) as client:
        with pytest.raises(PublicMediaError, match="total-byte limit"):
            prepare_public_media(database, output, client=client)
    assert not output.exists()
    assert not list(tmp_path.glob(".prepared.stage-*"))


def test_eleventh_unavailable_source_preserves_the_entire_last_good_output(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path, [_row()])
    output = tmp_path / "prepared"
    image_bytes = _png()

    def good_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=image_bytes)

    with _client(good_handler) as client:
        prepare_public_media(database, output, client=client)
    before_manifest = (output / "manifest.json").read_bytes()
    before_objects = {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*.webp")
    }

    bad_rows = [
        _row(
            source_page_url=f"https://www.fws.gov/media/unavailable-bird-{index}",
            source_image_url=(
                f"https://www.fws.gov/sites/default/files/birds/unavailable-{index}.png"
            ),
        )
        for index in range(11)
    ]
    with duckdb.connect(str(database)) as connection:
        _insert_rows(connection, bad_rows)

    calls = 0

    def failing_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    with _client(failing_handler) as client:
        sleeps: list[float] = []
        with pytest.raises(PublicMediaError, match="source-object limit"):
            prepare_public_media(
                database,
                output,
                client=client,
                sleeper=sleeps.append,
            )
    assert calls == 66
    assert sleeps == [1.0, 2.0, 4.0, 8.0, 16.0] * 11
    assert (output / "manifest.json").read_bytes() == before_manifest
    assert {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*.webp")
    } == before_objects
    assert not list(tmp_path.glob(".prepared.stage-*"))


def test_source_model_schema_must_be_exact(tmp_path: Path) -> None:
    database = _database(tmp_path, [_row()])
    with duckdb.connect(str(database)) as connection:
        connection.execute(
            "ALTER TABLE rufous_public.usfws_commercial_image ADD COLUMN unreviewed VARCHAR"
        )

    def forbidden_handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("schema failure must happen before network access")

    with _client(forbidden_handler) as client:
        with pytest.raises(PublicMediaError, match="exact reviewed schema"):
            prepare_public_media(database, tmp_path / "prepared", client=client)
