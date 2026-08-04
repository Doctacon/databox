"""Fail-closed tests for the manual, immutable Rufous audio release path."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import databox.public_audio_release as public_audio_release_module
import httpx
import pytest
from databox.public_audio_release import (
    DEFAULT_AUDIO_PREFIX,
    SANITIZATION_TRANSFORMATION,
    DownloadedAudio,
    PublicAudioError,
    _default_fetch_audio,
    _finalize_public_mp3,
    _probe_audio,
    _sanitize_audio_stream,
    _strip_mp3_metadata,
    _validate_public_audio_structure,
    _verify_audio_equivalence,
    acquire_reviewed_audio,
    canonical_audio_manifest_json,
    canonical_audio_selection_json,
    ensure_pinned_audio,
    load_audio_selection,
    load_pinned_audio_manifest,
    publish_prepared_audio,
    sanitize_prepared_audio,
    scan_prepared_audio,
    verify_pinned_audio_store,
    verify_selection_matches_manifest,
)
from databox.public_export import PUBLIC_AUDIO_SANITIZATION_NOTICE
from databox.public_release import IMMUTABLE_CACHE_CONTROL, LocalReleaseStore


def _mp3(seed: bytes = b"rufous") -> bytes:
    body = (seed * (414 // len(seed) + 1))[:413]
    return b"\xff\xfb\x90\x00" + body


def _fixture_ffmpeg() -> str:
    return os.environ.get("RUFOUS_AUDIO_FIXTURE_FFMPEG", "ffmpeg")


def _fake_sanitizer(payload: bytes, source_mime: str, output_mime: str) -> bytes:
    if source_mime == "audio/webm":
        assert output_mime == "audio/ogg"
        return b"OggS" + payload[4:] + b"sanitized"
    assert source_mime == output_mime
    if source_mime == "audio/mpeg":
        return payload[:-1] + bytes([payload[-1] ^ 0x01])
    return payload + b"sanitized"


def _accept_equivalent(
    _source_payload: bytes,
    _source_mime: str,
    _sanitized_payload: bytes,
    _sanitized_mime: str,
) -> None:
    return None


def _selection_item(
    *,
    expected_sha256: str | None = None,
    expected_bytes: int | None = None,
    duration_seconds: float | None = None,
    expected_mime_type: str | None = "audio/mpeg",
) -> dict[str, object]:
    return {
        "species_code": "gbif-2476855",
        "common_name": "Rufous Hummingbird",
        "scientific_name": "Selasphorus rufus",
        "provider": "xeno_canto",
        "provider_id": "XC123",
        "source_url": "https://xeno-canto.org/123",
        "creator": "Test Recordist",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "original_url": "https://xeno-canto.org/123/download",
        "expected_sha256": expected_sha256,
        "expected_bytes": expected_bytes,
        "expected_mime_type": expected_mime_type,
        "duration_seconds": duration_seconds,
        "vocalization_type": "call",
        "modification_notice": PUBLIC_AUDIO_SANITIZATION_NOTICE,
        "transformation": SANITIZATION_TRANSFORMATION,
    }


def _write_selection(
    path: Path,
    item: dict[str, object],
) -> Path:
    return _write_selection_items(path, [item])


def _write_selection_items(
    path: Path,
    items: list[dict[str, object]],
) -> Path:
    payload = {
        "schema_version": 1,
        "mode": "rufous-audio-selection",
        "reviewed_at": "2026-08-04T12:00:00Z",
        "reviewed_by": "Test Human",
        "items": items,
    }
    path.write_bytes(canonical_audio_selection_json(payload))
    return path


def _second_selection_item(*, recording_id: int = 124) -> dict[str, object]:
    item = _selection_item()
    item.update(
        {
            "species_code": "gbif-2476856",
            "common_name": "Anna's Hummingbird",
            "scientific_name": "Calypte anna",
            "provider_id": f"XC{recording_id}",
            "source_url": f"https://xeno-canto.org/{recording_id}",
            "original_url": f"https://xeno-canto.org/{recording_id}/download",
        }
    )
    return item


def _fetch(payload: bytes, *, content_type: str = "audio/mpeg"):
    def fetch(url: str, maximum: int) -> DownloadedAudio:
        assert maximum >= len(payload)
        return DownloadedAudio(payload, content_type, url)

    return fetch


def test_capture_measures_and_pins_one_reviewed_object_then_reuses_it(
    tmp_path: Path,
) -> None:
    payload = _mp3()
    draft = _write_selection(tmp_path / "draft.json", _selection_item())
    output = tmp_path / "prepared"
    pinned_selection = tmp_path / "selection.json"

    result = acquire_reviewed_audio(
        draft,
        output,
        capture_unpinned=True,
        pinned_selection_output=pinned_selection,
        generated_at="2026-08-04T13:00:00Z",
        fetcher=_fetch(payload),
        sanitizer=_fake_sanitizer,
        equivalence_checker=_accept_equivalent,
        probe=lambda _payload, _mime: 12.345,
    )

    sanitized = _fake_sanitizer(payload, "audio/mpeg", "audio/mpeg")
    digest = hashlib.sha256(sanitized).hexdigest()
    manifest = load_pinned_audio_manifest(output / "manifest.json")
    pinned = load_audio_selection(pinned_selection, require_pinned=True)
    assert result.downloaded_objects == 1
    assert manifest["counts"] == {"items": 1, "objects": 1, "species": 1}
    assert manifest["items"][0]["sha256"] == digest
    assert manifest["items"][0]["duration_seconds"] == 12.345
    assert manifest["items"][0]["url"].endswith(f"/{digest[:2]}/{digest}.mp3")
    assert pinned["items"][0]["expected_sha256"] == digest
    assert pinned["items"][0]["expected_bytes"] == len(sanitized)
    assert pinned["items"][0]["duration_seconds"] == 12.345
    assert verify_selection_matches_manifest(pinned_selection, output / "manifest.json") == 1

    def unexpected_fetch(_url: str, _maximum: int) -> DownloadedAudio:
        raise AssertionError("a cached reviewed object must not be downloaded again")

    second = acquire_reviewed_audio(
        draft,
        output,
        capture_unpinned=True,
        pinned_selection_output=pinned_selection,
        fetcher=unexpected_fetch,
        sanitizer=_fake_sanitizer,
        equivalence_checker=_accept_equivalent,
        probe=lambda _payload, _mime: 12.345,
    )
    assert second.downloaded_objects == 0
    assert second.reused_objects == 1
    assert load_pinned_audio_manifest(output / "manifest.json")["generated_at"] == (
        "2026-08-04T13:00:00Z"
    )


def test_mid_batch_failure_checkpoints_completed_rows_and_resumes_without_refetch(
    tmp_path: Path,
) -> None:
    first_payload = _mp3(b"first")
    second_payload = _mp3(b"second")
    selection = _write_selection_items(
        tmp_path / "selection.json",
        [_selection_item(), _second_selection_item()],
    )
    output = tmp_path / "prepared"
    first_calls: list[str] = []

    def failing_fetch(url: str, maximum: int) -> DownloadedAudio:
        first_calls.append(url)
        if url.endswith("/124/download"):
            raise PublicAudioError("simulated later-row source failure")
        return _fetch(first_payload)(url, maximum)

    with pytest.raises(PublicAudioError, match="later-row"):
        acquire_reviewed_audio(
            selection,
            output,
            capture_unpinned=True,
            fetcher=failing_fetch,
            sanitizer=_fake_sanitizer,
            equivalence_checker=_accept_equivalent,
            probe=lambda _payload, _mime: 2.0,
        )

    assert first_calls == [
        "https://xeno-canto.org/123/download",
        "https://xeno-canto.org/124/download",
    ]
    assert (output / "capture-checkpoint.json").is_file()
    assert not (output / "manifest.json").exists()

    # Replacing only the failed row is safe: it never entered the checkpoint.
    _write_selection_items(
        selection,
        [_selection_item(), _second_selection_item(recording_id=125)],
    )
    resumed_calls: list[str] = []

    def resumed_fetch(url: str, maximum: int) -> DownloadedAudio:
        if url.endswith("/123/download"):
            raise AssertionError("completed checkpoint row must not be fetched again")
        resumed_calls.append(url)
        return _fetch(second_payload)(url, maximum)

    result = acquire_reviewed_audio(
        selection,
        output,
        capture_unpinned=True,
        fetcher=resumed_fetch,
        sanitizer=_fake_sanitizer,
        equivalence_checker=_accept_equivalent,
        probe=lambda _payload, _mime: 2.0,
    )

    assert result.downloaded_objects == 1
    assert result.reused_objects == 1
    assert resumed_calls == ["https://xeno-canto.org/125/download"]
    assert load_pinned_audio_manifest(output / "manifest.json")["counts"]["items"] == 2
    assert not (output / "capture-checkpoint.json").exists()


def test_resume_rejects_tampered_checkpoint_identity_before_fetch(tmp_path: Path) -> None:
    selection = _write_selection_items(
        tmp_path / "selection.json",
        [_selection_item(), _second_selection_item()],
    )
    output = tmp_path / "prepared"

    with pytest.raises(PublicAudioError, match="stop"):
        acquire_reviewed_audio(
            selection,
            output,
            capture_unpinned=True,
            fetcher=lambda url, maximum: (
                _fetch(_mp3())(url, maximum)
                if url.endswith("/123/download")
                else (_ for _ in ()).throw(PublicAudioError("stop"))
            ),
            sanitizer=_fake_sanitizer,
            equivalence_checker=_accept_equivalent,
            probe=lambda _payload, _mime: 2.0,
        )
    checkpoint_path = output / "capture-checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["items"][0]["identity"]["provider_id"] = "XC999"
    checkpoint_path.write_bytes(canonical_audio_manifest_json(checkpoint))

    with pytest.raises(PublicAudioError, match="stale or tampered"):
        acquire_reviewed_audio(
            selection,
            output,
            capture_unpinned=True,
            fetcher=lambda _url, _maximum: pytest.fail("must reject before fetch"),
            sanitizer=_fake_sanitizer,
            equivalence_checker=_accept_equivalent,
            probe=lambda _payload, _mime: 2.0,
        )


def test_pinned_acquisition_rejects_changed_upstream_bytes(tmp_path: Path) -> None:
    expected_source = _mp3(b"expected")
    expected = _fake_sanitizer(expected_source, "audio/mpeg", "audio/mpeg")
    changed = _mp3(b"changed")
    selection = _write_selection(
        tmp_path / "selection.json",
        _selection_item(
            expected_sha256=hashlib.sha256(expected).hexdigest(),
            expected_bytes=len(expected),
            duration_seconds=4.5,
        ),
    )

    with pytest.raises(PublicAudioError, match="differ from the committed pin"):
        acquire_reviewed_audio(
            selection,
            tmp_path / "prepared",
            fetcher=_fetch(changed),
            sanitizer=_fake_sanitizer,
            equivalence_checker=_accept_equivalent,
            probe=lambda _payload, _mime: 4.5,
        )

    assert not (tmp_path / "prepared" / "manifest.json").exists()


def test_selection_rejects_noncommercial_license_before_fetch(tmp_path: Path) -> None:
    item = _selection_item()
    item["license"] = "CC BY-NC 4.0"
    item["license_url"] = "https://creativecommons.org/licenses/by-nc/4.0/"
    selection = _write_selection(tmp_path / "selection.json", item)

    with pytest.raises(PublicAudioError, match="forbidden license"):
        acquire_reviewed_audio(
            selection,
            tmp_path / "prepared",
            capture_unpinned=True,
            fetcher=lambda _url, _maximum: pytest.fail("must fail before network"),
        )


def test_magic_and_response_mime_must_both_match(tmp_path: Path) -> None:
    selection = _write_selection(tmp_path / "selection.json", _selection_item())

    with pytest.raises(PublicAudioError, match="MIME"):
        acquire_reviewed_audio(
            selection,
            tmp_path / "prepared",
            capture_unpinned=True,
            fetcher=_fetch(b"not-an-mp3", content_type="audio/mpeg"),
            sanitizer=_fake_sanitizer,
            equivalence_checker=_accept_equivalent,
            probe=lambda _payload, _mime: 1.0,
        )


def test_first_capture_detects_and_pins_allowed_mime(tmp_path: Path) -> None:
    wav = b"RIFF" + (64).to_bytes(4, "little") + b"WAVE" + b"data" * 16
    selection = _write_selection(
        tmp_path / "selection.json",
        _selection_item(expected_mime_type=None),
    )
    pinned = tmp_path / "pinned.json"

    acquire_reviewed_audio(
        selection,
        tmp_path / "prepared",
        capture_unpinned=True,
        pinned_selection_output=pinned,
        fetcher=_fetch(wav, content_type="audio/x-wav"),
        sanitizer=_fake_sanitizer,
        equivalence_checker=_accept_equivalent,
        probe=lambda _payload, _mime: 2.0,
    )

    manifest = load_pinned_audio_manifest(tmp_path / "prepared" / "manifest.json")
    reviewed = load_audio_selection(pinned, require_pinned=True)
    assert manifest["items"][0]["mime_type"] == "audio/wav"
    assert manifest["items"][0]["url"].endswith(".wav")
    assert reviewed["items"][0]["expected_mime_type"] == "audio/wav"


def test_capture_supports_disclosed_audio_only_condor_extraction(tmp_path: Path) -> None:
    source = b"\x1aE\xdf\xa3" + b"webm" * 100
    extracted = b"OggS" + b"opus" * 100
    item = {
        "species_code": "gbif-2481786",
        "common_name": "California Condor",
        "scientific_name": "Gymnogyps californianus",
        "provider": "wikimedia",
        "provider_id": "File:California_condor.webm",
        "source_url": "https://commons.wikimedia.org/wiki/File:California_condor.webm",
        "creator": "U.S. Fish and Wildlife Service",
        "license": "Public Domain",
        "license_url": (
            "https://commons.wikimedia.org/wiki/Commons:Copyright_tags/General_public_domain"
        ),
        "original_url": (
            "https://upload.wikimedia.org/wikipedia/commons/a/ab/California_condor.webm"
        ),
        "expected_sha256": None,
        "expected_bytes": None,
        "expected_mime_type": "audio/ogg",
        "duration_seconds": None,
        "vocalization_type": "chick call and adult response",
        "modification_notice": PUBLIC_AUDIO_SANITIZATION_NOTICE,
        "transformation": SANITIZATION_TRANSFORMATION,
    }
    selection = _write_selection(tmp_path / "selection.json", item)
    transformed: list[bytes] = []

    result = acquire_reviewed_audio(
        selection,
        tmp_path / "prepared",
        capture_unpinned=True,
        fetcher=_fetch(source, content_type="video/webm"),
        sanitizer=lambda payload, source_mime, output_mime: (
            transformed.append(payload) or extracted
        ),
        equivalence_checker=_accept_equivalent,
        probe=lambda _payload, _mime: 7.25,
    )

    manifest = load_pinned_audio_manifest(tmp_path / "prepared" / "manifest.json")
    assert result.downloaded_objects == 1
    assert transformed == [source]
    assert manifest["items"][0]["mime_type"] == "audio/ogg"
    assert manifest["items"][0]["modification_notice"] == PUBLIC_AUDIO_SANITIZATION_NOTICE


def test_ffprobe_rejects_corrupt_magic_valid_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "databox.public_audio_release.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=b"", stderr=b"bad"),
    )

    with pytest.raises(PublicAudioError, match="could not be decoded"):
        _probe_audio(_mp3(), "audio/mpeg")


def test_public_webm_is_rejected_before_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "databox.public_audio_release.subprocess.run",
        lambda *args, **kwargs: pytest.fail("public WebM must fail before ffprobe"),
    )

    with pytest.raises(PublicAudioError, match="cannot be probed safely"):
        _probe_audio(b"\x1aE\xdf\xa3payload", "audio/webm")


def test_ffprobe_rejects_container_without_audio_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = json.dumps(
        {
            "streams": [{"codec_type": "video"}],
            "chapters": [],
            "programs": [],
            "format": {"duration": "4.0", "nb_streams": 1, "nb_programs": 0},
        }
    ).encode()
    monkeypatch.setattr(
        "databox.public_audio_release.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output, stderr=b""),
    )

    with pytest.raises(PublicAudioError, match="exactly one audio stream"):
        _probe_audio(_mp3(), "audio/mpeg")


def test_ffprobe_rejects_overlong_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    output = json.dumps(
        {
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "mp3",
                    "sample_rate": "44100",
                    "channels": 1,
                }
            ],
            "chapters": [],
            "programs": [],
            "format": {
                "duration": "3600.001",
                "nb_streams": 1,
                "nb_programs": 0,
                "format_name": "mp3",
            },
        }
    ).encode()
    monkeypatch.setattr(
        "databox.public_audio_release.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output, stderr=b""),
    )

    with pytest.raises(PublicAudioError, match="duration exceeds"):
        _probe_audio(_mp3(), "audio/mpeg")


def test_ffprobe_rejects_any_source_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    output = json.dumps(
        {
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "mp3",
                    "sample_rate": "44100",
                    "channels": 1,
                    "tags": {"comment": "GPS device"},
                }
            ],
            "chapters": [],
            "programs": [],
            "format": {
                "duration": "4.0",
                "nb_streams": 1,
                "nb_programs": 0,
                "format_name": "mp3",
            },
        }
    ).encode()
    monkeypatch.setattr(
        "databox.public_audio_release.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output, stderr=b""),
    )

    with pytest.raises(PublicAudioError, match="disallowed source metadata"):
        _probe_audio(_mp3(), "audio/mpeg")


def test_ffprobe_allows_only_exact_technical_mp3_replay_gain_side_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = {
        "streams": [
            {
                "codec_type": "audio",
                "codec_name": "mp3",
                "sample_rate": "44100",
                "channels": 2,
                "tags": {"encoder": "Lavf"},
                "side_data_list": [{"side_data_type": "Replay Gain"}],
            }
        ],
        "chapters": [],
        "programs": [],
        "format": {
            "duration": "18.233469",
            "nb_streams": 1,
            "nb_programs": 0,
            "format_name": "mp3",
        },
    }
    monkeypatch.setattr(
        "databox.public_audio_release.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps(result).encode(), stderr=b""
        ),
    )

    assert _probe_audio(_mp3(), "audio/mpeg") == 18.233

    result["streams"][0]["side_data_list"] = [
        {"side_data_type": "Replay Gain", "track_gain": "1.0"}
    ]
    with pytest.raises(PublicAudioError, match="disallowed stream side data"):
        _probe_audio(_mp3(), "audio/mpeg")


def test_mp3_fallback_strips_real_edge_id3_wrapper_and_preserves_xing_frames(
    tmp_path: Path,
) -> None:
    frames_path = tmp_path / "frames.mp3"
    completed = subprocess.run(
        [
            _fixture_ffmpeg(),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1100:duration=1.031",
            "-c:a",
            "libmp3lame",
            "-id3v2_version",
            "0",
            "-write_xing",
            "1",
            "-f",
            "mp3",
            str(frames_path),
        ],
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0
    frames = frames_path.read_bytes()
    assert frames.startswith(b"\xff")
    # Exact 55-byte ID3v2 wrapper shape seen on the Red-naped Sapsucker source.
    id3_wrapper = bytes.fromhex(
        "4944330400400000002d0000000c0120050b2a75375c5458585800000017000000"
        "536f667477617265004c61766635382e34352e313030"
    )
    source = id3_wrapper + frames

    stripped = _strip_mp3_metadata(source)

    assert stripped == frames
    _verify_audio_equivalence(source, "audio/mpeg", stripped, "audio/mpeg")
    assert _probe_audio(stripped, "audio/mpeg") > 1.0


@pytest.mark.parametrize(
    "malformed",
    [
        b"ID3\x04\x00\x00\x80\x00\x00\x01" + _mp3(),
        b"ID3\x04\x00\x00\x00\x00\x7f\x7f" + _mp3(),
        b"ID3\x04\x00\x00\x00\x00\x00\x01x" + _mp3() + b"not-a-frame",
    ],
)
def test_mp3_fallback_rejects_malformed_id3_sizes_or_frame_boundaries(
    malformed: bytes,
) -> None:
    with pytest.raises(PublicAudioError, match="ID3v2|frame sequence"):
        _strip_mp3_metadata(malformed)


def test_mp3_fallback_strips_only_validated_trailing_id3v1_and_apev2() -> None:
    # One complete MPEG-1 Layer III, 128 kbps, 44.1 kHz frame.
    frame = b"\xff\xfb\x90\x00" + b"\0" * 413
    ape_footer = (
        b"APETAGEX"
        + (2_000).to_bytes(4, "little")
        + (32).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + b"\0" * 8
    )
    wrapped = frame + ape_footer + b"TAG" + b"\0" * 125

    assert _strip_mp3_metadata(wrapped) == frame

    malformed_footer = bytearray(ape_footer)
    malformed_footer[12:16] = (len(frame) + 1_000).to_bytes(4, "little")
    with pytest.raises(PublicAudioError, match="APEv2"):
        _strip_mp3_metadata(frame + bytes(malformed_footer))


def test_xc450919_ape_coordinates_are_removed_before_exact_mp3_eof() -> None:
    frame = b"\xff\xfb\x90\x00" + b"\0" * 413
    coordinate_comment = (
        b"XC450919 Anderson Township (39.0764, -84.336), United States; Zoom H4N Pro"
    )
    item = (
        len(coordinate_comment).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + b"COMMENT\0"
        + coordinate_comment
    )
    tag_size = len(item) + 32

    def ape_block(flags: int) -> bytes:
        return (
            b"APETAGEX"
            + (2_000).to_bytes(4, "little")
            + tag_size.to_bytes(4, "little")
            + (1).to_bytes(4, "little")
            + flags.to_bytes(4, "little")
            + b"\0" * 8
        )

    # Mirrors XC450919: the APE header begins inside the nominal final frame.
    raw = frame[:-98] + ape_block(0xA0000000) + item + ape_block(0x80000000)
    assert b"APETAGEX" in raw
    assert b"XC450919" in raw
    assert b"39.0764, -84.336" in raw

    sanitized = _finalize_public_mp3(raw)

    assert len(sanitized) == len(frame)
    assert b"APETAGEX" not in sanitized
    assert b"XC450919" not in sanitized
    assert b"39.0764, -84.336" not in sanitized
    _validate_public_audio_structure(sanitized, "audio/mpeg")


def test_strict_public_probe_rejects_opaque_bytes_after_final_mp3_frame() -> None:
    frame = b"\xff\xfb\x90\x00" + b"\0" * 413

    with pytest.raises(PublicAudioError, match="frame sequence"):
        _probe_audio(frame + b"opaque location metadata", "audio/mpeg")


def test_raw_container_validators_reject_wav_and_m4a_metadata_structures() -> None:
    fmt = (
        (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + (8_000).to_bytes(4, "little")
        + (16_000).to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
    )
    chunks = b"fmt " + len(fmt).to_bytes(4, "little") + fmt + b"data\x02\0\0\0\0\0"
    wav = b"RIFF" + (len(chunks) + 4).to_bytes(4, "little") + b"WAVE" + chunks
    _validate_public_audio_structure(wav, "audio/wav")
    list_chunk = b"LIST\x04\0\0\0GPS!"
    wav_with_metadata = (
        b"RIFF"
        + (len(chunks) + len(list_chunk) + 4).to_bytes(4, "little")
        + b"WAVE"
        + chunks
        + list_chunk
    )
    with pytest.raises(PublicAudioError, match="forbidden or malformed chunk"):
        _validate_public_audio_structure(wav_with_metadata, "audio/wav")

    ftyp = (8).to_bytes(4, "big") + b"ftyp"
    mdat = (8).to_bytes(4, "big") + b"mdat"
    moov = (8).to_bytes(4, "big") + b"moov"
    _validate_public_audio_structure(ftyp + moov + mdat, "audio/mp4")
    udta = (16).to_bytes(4, "big") + b"udta" + b"GPS DATA"
    moov_with_metadata = (8 + len(udta)).to_bytes(4, "big") + b"moov" + udta
    with pytest.raises(PublicAudioError, match="forbidden metadata atom"):
        _validate_public_audio_structure(ftyp + moov_with_metadata + mdat, "audio/mp4")


def test_only_exact_lame_encoder_marker_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    result = {
        "streams": [
            {
                "codec_type": "audio",
                "codec_name": "mp3",
                "sample_rate": "44100",
                "channels": 2,
                "tags": {"encoder": "LAME3.99"},
            }
        ],
        "chapters": [],
        "programs": [],
        "format": {
            "duration": "7.152",
            "nb_streams": 1,
            "nb_programs": 0,
            "format_name": "mp3",
        },
    }
    monkeypatch.setattr(
        "databox.public_audio_release.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps(result).encode(), stderr=b""
        ),
    )

    with pytest.raises(PublicAudioError, match="disallowed source metadata"):
        _probe_audio(_mp3(), "audio/mpeg")

    result["streams"][0]["tags"] = {"encoder": "LAME3.100"}
    assert _probe_audio(_mp3(), "audio/mpeg") == 7.152


@pytest.mark.parametrize(
    ("codec_name", "sample_rate"),
    [("flac", "44100"), ("mp3", "999999")],
)
def test_ffprobe_rejects_codec_or_stream_shape_outside_public_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    codec_name: str,
    sample_rate: str,
) -> None:
    output = json.dumps(
        {
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": codec_name,
                    "sample_rate": sample_rate,
                    "channels": 1,
                }
            ],
            "chapters": [],
            "programs": [],
            "format": {
                "duration": "4.0",
                "nb_streams": 1,
                "nb_programs": 0,
                "format_name": "mp3",
            },
        }
    ).encode()
    monkeypatch.setattr(
        "databox.public_audio_release.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output, stderr=b""),
    )

    with pytest.raises(PublicAudioError, match="outside the public allowlist"):
        _probe_audio(_mp3(), "audio/mpeg")


def test_real_sanitizer_strips_gps_device_comment_and_creation_metadata(
    tmp_path: Path,
) -> None:
    source = tmp_path / "private-source.m4a"
    completed = subprocess.run(
        [
            _fixture_ffmpeg(),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=1",
            "-metadata",
            "location=+33.4484-112.0740/",
            "-metadata",
            "comment=DEVICE_SERIAL_123",
            "-metadata",
            "creation_time=2026-01-02T03:04:05Z",
            "-metadata",
            "title=GPS_PRIVATE",
            "-c:a",
            "aac",
            str(source),
        ],
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0
    source_payload = source.read_bytes()
    source_metadata = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)],
        check=True,
        capture_output=True,
        timeout=30,
    ).stdout
    assert all(
        marker in source_metadata
        for marker in (
            b"DEVICE_SERIAL_123",
            b"GPS_PRIVATE",
            b"2026-01-02",
            b"+33.4484-112.0740",
        )
    )

    first = _sanitize_audio_stream(source_payload, "audio/mp4", "audio/mp4")
    second = _sanitize_audio_stream(source_payload, "audio/mp4", "audio/mp4")

    assert first == second
    assert first != source_payload
    assert all(
        marker not in first
        for marker in (
            b"DEVICE_SERIAL_123",
            b"GPS_PRIVATE",
            b"2026-01-02",
            b"+33.4484-112.0740",
        )
    )
    assert _probe_audio(first, "audio/mp4") == 1.0
    _verify_audio_equivalence(source_payload, "audio/mp4", first, "audio/mp4")


def test_webm_to_ogg_remux_preserves_decoded_pcm_and_end_padding(tmp_path: Path) -> None:
    source = tmp_path / "source.webm"
    completed = subprocess.run(
        [
            _fixture_ffmpeg(),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=900:duration=1.013",
            "-c:a",
            "libopus",
            str(source),
        ],
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0
    source_payload = source.read_bytes()

    sanitized = _sanitize_audio_stream(source_payload, "audio/webm", "audio/ogg")

    _verify_audio_equivalence(source_payload, "audio/webm", sanitized, "audio/ogg")
    assert _probe_audio(sanitized, "audio/ogg") > 1.0
    corrupted = sanitized[:-1] + bytes([sanitized[-1] ^ 0x01])
    with pytest.raises(PublicAudioError, match="CRC is invalid"):
        _validate_public_audio_structure(corrupted, "audio/ogg")


def test_http_redirect_is_rejected_before_any_off_allowlist_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host != "xeno-canto.org":
            pytest.fail("the rejected redirect target must never receive a request")
        return httpx.Response(302, headers={"Location": "https://attacker.example/audio.mp3"})

    real_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        public_audio_release_module.httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    with pytest.raises(PublicAudioError, match="outside the fetch allowlist"):
        _default_fetch_audio("https://xeno-canto.org/123/download", 1024)

    assert requested == ["https://xeno-canto.org/123/download"]


def test_pinned_acquisition_rejects_measured_duration_mismatch(tmp_path: Path) -> None:
    payload = _mp3()
    expected = _fake_sanitizer(payload, "audio/mpeg", "audio/mpeg")
    selection = _write_selection(
        tmp_path / "selection.json",
        _selection_item(
            expected_sha256=hashlib.sha256(expected).hexdigest(),
            expected_bytes=len(expected),
            duration_seconds=10.0,
        ),
    )

    with pytest.raises(PublicAudioError, match="duration differs"):
        acquire_reviewed_audio(
            selection,
            tmp_path / "prepared",
            fetcher=_fetch(payload),
            sanitizer=_fake_sanitizer,
            equivalence_checker=_accept_equivalent,
            probe=lambda _payload, _mime: 10.251,
        )


def _captured_fixture(tmp_path: Path) -> tuple[Path, Path, bytes]:
    payload = _mp3()
    draft = _write_selection(tmp_path / "draft.json", _selection_item())
    prepared = tmp_path / "prepared"
    pinned = tmp_path / "pinned-selection.json"
    acquire_reviewed_audio(
        draft,
        prepared,
        capture_unpinned=True,
        pinned_selection_output=pinned,
        generated_at="2026-08-04T13:00:00Z",
        fetcher=_fetch(payload),
        sanitizer=_fake_sanitizer,
        equivalence_checker=_accept_equivalent,
        probe=lambda _payload, _mime: 3.5,
    )
    return prepared, pinned, payload


def test_sanitize_prepared_repins_exact_legacy_bytes_without_provider_contact(
    tmp_path: Path,
) -> None:
    source_payload = _mp3(b"legacy")
    legacy_item = _selection_item(
        expected_sha256=hashlib.sha256(source_payload).hexdigest(),
        expected_bytes=len(source_payload),
        duration_seconds=6.0,
    )
    legacy_item["modification_notice"] = "Unmodified original recording."
    legacy_item["transformation"] = "none"
    legacy_selection = _write_selection(tmp_path / "legacy-selection.json", legacy_item)
    legacy_prepared = tmp_path / "legacy-prepared"
    old_public_item = public_audio_release_module._public_item(
        legacy_item,
        sha256=hashlib.sha256(source_payload).hexdigest(),
        size=len(source_payload),
    )
    legacy_manifest = {
        "schema_version": 1,
        "generated_at": "2026-08-04T12:30:00Z",
        "counts": {"items": 1, "objects": 1, "species": 1},
        "items": [old_public_item],
    }
    (legacy_prepared / "objects" / old_public_item["sha256"][:2]).mkdir(parents=True)
    old_path = (
        legacy_prepared
        / "objects"
        / old_public_item["sha256"][:2]
        / f"{old_public_item['sha256']}.mp3"
    )
    old_path.write_bytes(source_payload)
    (legacy_prepared / "manifest.json").write_bytes(canonical_audio_manifest_json(legacy_manifest))
    sanitized_prepared = tmp_path / "sanitized-prepared"
    sanitized_selection = tmp_path / "sanitized-selection.json"

    result = sanitize_prepared_audio(
        legacy_selection,
        legacy_prepared,
        sanitized_prepared,
        sanitized_selection,
        generated_at="2026-08-04T14:00:00Z",
        sanitizer=_fake_sanitizer,
        equivalence_checker=_accept_equivalent,
        probe=lambda _payload, _mime: 6.0,
    )

    selection = load_audio_selection(sanitized_selection, require_pinned=True)
    manifest = load_pinned_audio_manifest(sanitized_prepared / "manifest.json")
    assert result.status == "sanitized"
    assert result.downloaded_objects == 0
    assert selection["items"][0]["transformation"] == SANITIZATION_TRANSFORMATION
    assert selection["items"][0]["modification_notice"] == PUBLIC_AUDIO_SANITIZATION_NOTICE
    assert manifest["items"][0]["sha256"] != old_public_item["sha256"]
    assert (
        verify_selection_matches_manifest(sanitized_selection, sanitized_prepared / "manifest.json")
        == 1
    )


def test_ensure_r2_fetches_only_missing_objects_and_then_is_a_noop(tmp_path: Path) -> None:
    prepared, selection, payload = _captured_fixture(tmp_path)
    store = LocalReleaseStore(tmp_path / "r2")
    calls: list[str] = []

    def fetch(url: str, maximum: int) -> DownloadedAudio:
        calls.append(url)
        return _fetch(payload)(url, maximum)

    first = ensure_pinned_audio(
        selection,
        prepared / "manifest.json",
        store,
        fetcher=fetch,
        sanitizer=_fake_sanitizer,
        equivalence_checker=_accept_equivalent,
        probe=lambda _payload, _mime: 3.5,
    )
    assert first.uploaded_objects == 1
    assert calls == ["https://xeno-canto.org/123/download"]
    item = load_pinned_audio_manifest(prepared / "manifest.json")["items"][0]
    key = f"{DEFAULT_AUDIO_PREFIX}/{item['sha256'][:2]}/{item['sha256']}.mp3"
    head = store.head_object(key)
    assert head is not None
    assert head.cache_control == IMMUTABLE_CACHE_CONTROL
    assert head.metadata == {
        "sha256": item["sha256"],
        "role": "audio",
        "schema": "rufous-audio-v1",
        "duration-seconds": "3.5",
    }

    second = ensure_pinned_audio(
        selection,
        prepared / "manifest.json",
        store,
        fetcher=lambda _url, _maximum: pytest.fail("existing R2 object must skip source"),
    )
    assert second.uploaded_objects == 0
    assert second.reused_objects == 1


def test_dry_run_heads_r2_but_does_not_contact_missing_source(tmp_path: Path) -> None:
    prepared, selection, _ = _captured_fixture(tmp_path)

    result = ensure_pinned_audio(
        selection,
        prepared / "manifest.json",
        LocalReleaseStore(tmp_path / "r2"),
        dry_run=True,
        fetcher=lambda _url, _maximum: pytest.fail("dry-run must not contact source"),
    )

    assert result.status == "dry-run"
    assert result.uploaded_objects == 0


def test_verify_r2_fails_on_missing_and_never_contacts_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, selection, payload = _captured_fixture(tmp_path)
    store = LocalReleaseStore(tmp_path / "r2")
    monkeypatch.setattr(
        public_audio_release_module,
        "_default_fetch_audio",
        lambda _url, _maximum: pytest.fail("verify-r2 must never contact a provider"),
    )

    with pytest.raises(PublicAudioError, match="missing from R2"):
        verify_pinned_audio_store(selection, prepared / "manifest.json", store)

    ensure_pinned_audio(
        selection,
        prepared / "manifest.json",
        store,
        fetcher=_fetch(payload),
        sanitizer=_fake_sanitizer,
        equivalence_checker=_accept_equivalent,
        probe=lambda _payload, _mime: 3.5,
    )
    result = verify_pinned_audio_store(selection, prepared / "manifest.json", store)
    assert result.status == "verified"
    assert result.uploaded_objects == 0
    assert result.reused_objects == 1


def test_local_publish_and_scan_use_only_committed_prepared_bytes(tmp_path: Path) -> None:
    prepared, selection, _ = _captured_fixture(tmp_path)
    store = LocalReleaseStore(tmp_path / "published")

    objects = scan_prepared_audio(prepared, probe=lambda _payload, _mime: 3.5)
    first = publish_prepared_audio(
        prepared,
        selection,
        store,
        probe=lambda _payload, _mime: 3.5,
    )
    second = publish_prepared_audio(
        prepared,
        selection,
        store,
        probe=lambda _payload, _mime: 3.5,
    )

    assert len(objects) == 1
    assert first.uploaded_objects == 1
    assert second.uploaded_objects == 0
    assert second.reused_objects == 1


def test_preverified_publish_rechecks_pins_without_media_parsing(tmp_path: Path) -> None:
    prepared, selection, _ = _captured_fixture(tmp_path)
    store = LocalReleaseStore(tmp_path / "published")

    result = publish_prepared_audio(
        prepared,
        selection,
        store,
        preverified=True,
        probe=lambda _payload, _mime: pytest.fail(
            "credentialed upload must not invoke a media parser"
        ),
    )

    assert result.uploaded_objects == 1


def test_preverified_publish_rejects_artifact_byte_tampering(tmp_path: Path) -> None:
    prepared, selection, _ = _captured_fixture(tmp_path)
    item = load_pinned_audio_manifest(prepared / "manifest.json")["items"][0]
    object_path = prepared / "objects" / item["sha256"][:2] / f"{item['sha256']}.mp3"
    object_path.write_bytes(object_path.read_bytes() + b"tampered")

    with pytest.raises(PublicAudioError, match="bytes do not match the pin"):
        publish_prepared_audio(
            prepared,
            selection,
            LocalReleaseStore(tmp_path / "published"),
            preverified=True,
        )


def test_pin_and_selection_binding_rejects_manifest_tampering(tmp_path: Path) -> None:
    prepared, selection, _ = _captured_fixture(tmp_path)
    manifest_path = prepared / "manifest.json"
    manifest = load_pinned_audio_manifest(manifest_path)
    manifest["items"][0]["creator"] = "Someone Else"
    manifest_path.write_bytes(canonical_audio_manifest_json(manifest))

    with pytest.raises(PublicAudioError, match="differs from its reviewed selection"):
        verify_selection_matches_manifest(selection, manifest_path)
