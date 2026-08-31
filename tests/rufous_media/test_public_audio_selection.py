from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from databox.public_audio_release import (
    load_audio_selection,
    load_pinned_audio_manifest,
    verify_selection_matches_manifest,
)
from databox.public_export import PUBLIC_AUDIO_SANITIZATION_NOTICE

ROOT = Path(__file__).resolve().parents[2]
SELECTION = ROOT / "config" / "rufous-public-audio-selection.json"
MANIFEST = ROOT / "config" / "rufous-pinned-public-audio.json"
PHOTO_CATALOG = ROOT / "config" / "rufous-pinned-public-media.json"

EXPECTED_AUDIO_GAPS = {
    "Aechmophorus clarkii",
    "Anas diazi",
    "Anser rossii",
    "Aythya affinis",
    "Aythya valisineria",
    "Bucephala islandica",
    "Buteo regalis",
    "Eugenes fulgens",
    "Lampornis clemenciae",
    "Podiceps nigricollis",
    "Spatula cyanoptera",
}


def test_committed_public_audio_catalog_is_exactly_pinned() -> None:
    selection = load_audio_selection(SELECTION, require_pinned=True)
    manifest = load_pinned_audio_manifest(MANIFEST)

    assert verify_selection_matches_manifest(SELECTION, MANIFEST) == 196
    assert manifest["counts"] == {"items": 196, "objects": 196, "species": 196}
    assert Counter(item["provider"] for item in manifest["items"]) == {
        "xeno_canto": 122,
        "inaturalist": 73,
        "wikimedia": 1,
    }
    assert all(item["expected_sha256"] for item in selection["items"])


def test_audio_catalog_excludes_unlicensed_and_pronunciation_only_gaps() -> None:
    manifest = load_pinned_audio_manifest(MANIFEST)
    photo_catalog = json.loads(PHOTO_CATALOG.read_text(encoding="utf-8"))
    all_species = {item["scientific_name"] for item in photo_catalog["items"]}
    audio_species = {item["scientific_name"] for item in manifest["items"]}

    assert all_species - audio_species == EXPECTED_AUDIO_GAPS
    assert not {
        "File:De-Zwergschneegans.ogg",
        "File:De-Spatelente.ogg",
        "File:Nl-geoorde fuut.ogg",
    } & {item["provider_id"] for item in manifest["items"]}


def test_special_case_recordings_preserve_source_and_modification_provenance() -> None:
    manifest = load_pinned_audio_manifest(MANIFEST)
    by_species = {item["scientific_name"]: item for item in manifest["items"]}

    assert by_species["Trogon elegans"]["provider_id"] == "sound-779267"
    assert by_species["Trogon elegans"]["license"] == "CC BY 4.0"
    assert by_species["Selasphorus rufus"]["provider_id"] == "sound-390696"
    assert by_species["Selasphorus rufus"]["license"] == "CC0 1.0"
    assert by_species["Gymnogyps californianus"]["provider"] == "wikimedia"
    assert all(
        item["modification_notice"] == PUBLIC_AUDIO_SANITIZATION_NOTICE
        for item in manifest["items"]
    )
