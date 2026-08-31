"""Repository contract for Rufous's one-time curated Commons image gap fill."""

from __future__ import annotations

import json
from pathlib import Path

from databox.public_media import SOURCE_COLUMNS, SourceImageRow
from databox.public_wikimedia_media_ingest import (
    MODE,
    PROVIDER,
    canonical_wikimedia_media_json,
)

ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "config" / "rufous-wikimedia-public-media.json"

EXPECTED_SPECIES = {
    "gbif-11003172": "Leucolia violiceps",
    "gbif-2482800": "Empidonax hammondii",
    "gbif-2483531": "Myiarchus tuberculifer",
    "gbif-2487586": "Polioptila melanura",
    "gbif-2487892": "Baeolophus wollweberi",
    "gbif-2489202": "Stelgidopteryx serripennis",
    "gbif-2491677": "Calcarius ornatus",
    "gbif-2491961": "Aimophila ruficeps",
    "gbif-2492031": "Junco phaeonotus",
    "gbif-2492104": "Spizella atrogularis",
    "gbif-2498034": "Anser cygnoides",
    "gbif-2498136": "Anas diazi",
    "gbif-5231139": "Zonotrichia querula",
    "gbif-5231430": "Catherpes mexicanus",
    "gbif-5231693": "Toxostoma crissale",
    "gbif-5231697": "Toxostoma bendirei",
    "gbif-7341576": "Peucaea carpalis",
    "gbif-7341587": "Melozone aberti",
    "gbif-7341622": "Melozone fusca",
    "gbif-8332393": "Spatula clypeata",
    "gbif-9323342": "Trogon elegans",
    "gbif-9353154": "Vireo plumbeus",
    "gbif-9441907": "Aphelocoma wollweberi",
    "gbif-9770031": "Agapornis roseicollis",
}


def test_curated_commons_input_covers_exactly_the_24_unpictured_species() -> None:
    raw = SOURCE.read_bytes()
    payload = json.loads(raw)

    assert raw == canonical_wikimedia_media_json(payload)
    assert payload["schema_version"] == 1
    assert payload["mode"] == MODE
    assert payload["provider"] == PROVIDER
    assert len(payload["items"]) == 24
    assert {
        item["species_code"]: item["scientific_name"] for item in payload["items"]
    } == EXPECTED_SPECIES


def test_every_commons_row_is_one_exact_commercial_file_with_complete_credit() -> None:
    payload = json.loads(SOURCE.read_bytes())
    source_pages: set[str] = set()
    source_images: set[str] = set()
    for raw_item in payload["items"]:
        assert set(raw_item) == set(SOURCE_COLUMNS)
        row = SourceImageRow.from_values({**raw_item, "provider": PROVIDER})
        assert row.source_page_url.startswith("https://commons.wikimedia.org/wiki/File:")
        assert row.source_image_url.startswith("https://upload.wikimedia.org/wikipedia/commons/")
        assert row.license == "Public Domain" or row.license.startswith(
            ("CC0 ", "CC BY ", "CC BY-SA ")
        )
        assert " NC" not in row.license and " ND" not in row.license
        assert row.caption is not None and "live" in row.caption.casefold()
        assert row.creator and row.alt_text
        assert row.source_page_url not in source_pages
        assert row.source_image_url not in source_images
        source_pages.add(row.source_page_url)
        source_images.add(row.source_image_url)
