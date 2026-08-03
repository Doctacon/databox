"""Offline temporary HTML fixtures for USFWS source tests."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from databox_sources.usfws import source as usfws_module

TARGET = {
    "species_code": "rufhum",
    "common_name": "Rufous Hummingbird",
    "scientific_name": "Selasphorus rufus",
}


def _card(
    slug: str,
    *,
    title: str,
    credit: str,
    href: str | None = None,
) -> str:
    resolved_href = href or f"/media/{slug}"
    return f"""
    <div class="teaser media-image">
      <div class="field field--name-field-media-image field--item">
        <a href="{resolved_href}"><img
          src="/sites/default/files/styles/large_square/public/{slug}.jpg"
          width="480" height="320" alt="{title} in flight" /></a>
      </div>
      <div class="field field--name-name field--item"><a href="{resolved_href}">{title}</a></div>
      <div class="field field--name-field-media-caption field--item">Caption for {title}</div>
      <div class="field field--name-field-mime-type field--item"><span>Image</span></div>
      <div class="field field--name-field-document-publication-date field--item">
        <time datetime="2024-06-21T12:00:00Z">Jun 21, 2024</time>
      </div>
      <div class="field field--name-field-media-credit field--item">{credit}</div>
    </div>
    """


def _detail(
    slug: str,
    *,
    title: str,
    creator: str,
    license_text: str,
    scientific_name: str = "Selasphorus rufus",
) -> str:
    return f"""
    <html><body><main>
      <div class="media-full-content image">
        <div class="photoswipe-gallery field field--name-field-media-image field--item">
          <a href="https://www.fws.gov/sites/default/files/images/{slug}.jpg" class="photoswipe"
             data-pswp-width="1600" data-pswp-height="1000" data-overlay-title="{title}">
            <picture><img width="480" height="300"
              src="/sites/default/files/styles/scale_width_480/public/images/{slug}.jpg"
              alt="Detailed alt text for {title}" /></picture>
          </a>
        </div>
        <div class="dropdown"><ul>
          <li><a href="https://www.fws.gov/sites/default/files/styles/max_650x650/public/images/{slug}.jpg"
            download="usfws-{slug}-medium">Medium (650 x 406)</a></li>
          <li><a href="https://www.fws.gov/sites/default/files/images/{slug}.jpg"
            download="usfws-{slug}">Original (1600 x 1000)</a></li>
        </ul></div>
        <div class="image-credit field">
          <div class="field--label">Photo By/Credit</div><p>{creator}</p>
        </div>
        <div class="date-shot-created field">
          <div class="field--label">Date Shot/Created</div>06/21/2024
        </div>
        <div class="field field--name-field-creative-commons-license field--label-above">
          <div class="field--label">Media Usage Rights/License</div>
          <div class="field--item">{license_text}</div>
        </div>
        <div class="media-type field">Image</div>
        <div class="field field--name-field-media-caption field--item">
          A complete detail caption.
        </div>
        <div class="field field--name-field-species-ref field--label-above">
          <div class="field--items"><div class="field--item">
            <a href="/species/rufous-hummingbird-selasphorus-rufus">
              {scientific_name}
            </a>
          </div>
        </div></div>
        <div class="field field--name-field-subject-tags field--label-above">
          <div class="field--items">
            <div class="field--item">Birds</div><div class="field--item">Pollinators</div>
        </div></div>
      </div>
    </main></body></html>
    """


class _FakeResponse:
    def __init__(self, *, payload: dict[str, Any] | None = None, text: str = "") -> None:
        self.content = (
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
            if payload is not None
            else text.encode("utf-8")
        )
        self.headers = {"Content-Length": str(len(self.content))}

    def raise_for_status(self) -> None:
        return None


@pytest.fixture
def usfws_transport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Install a file-backed transport covering both search paths and rights states."""
    fixture_dir = tmp_path / "usfws-html"
    fixture_dir.mkdir()
    pd_card = _card(
        "rufous-public-domain",
        title="Rufous Hummingbird",
        credit="Alan Example/USFWS",
    )
    nc_card = _card(
        "rufous-noncommercial",
        title="Rufous at flowers",
        credit="Example Photographer",
    )
    unsafe_card = _card(
        "unsafe",
        title="Untrusted result",
        credit="Someone",
        href="https://images.example.invalid/media/unsafe",
    )
    (fixture_dir / "species.json").write_text(
        json.dumps(
            {
                "list": [pd_card],
                "_meta": {
                    "total": 1,
                    "facets": {"species": [{"filter": "Rufous Hummingbird", "count": 1}]},
                },
            }
        )
    )
    (fixture_dir / "common.json").write_text(
        json.dumps(
            {
                "list": [pd_card, nc_card, unsafe_card],
                "_meta": {
                    "total": 3,
                    "facets": {"type": [{"filter": "Image", "count": 3}]},
                },
            }
        )
    )
    (fixture_dir / "scientific.json").write_text(json.dumps({"list": [], "_meta": {"total": 0}}))
    (fixture_dir / "rufous-public-domain.html").write_text(
        _detail(
            "rufous-public-domain",
            title="Rufous Hummingbird",
            creator="Alan Example/USFWS",
            license_text="Public Domain",
        )
    )
    (fixture_dir / "rufous-noncommercial.html").write_text(
        _detail(
            "rufous-noncommercial",
            title="Rufous at flowers",
            creator="Example Photographer",
            license_text="CC BY-NC 4.0",
        )
    )

    calls: list[dict[str, Any]] = []
    lock = threading.Lock()

    def fake_get(url: str, **kwargs: Any) -> _FakeResponse:
        params = kwargs.get("params") or {}
        with lock:
            calls.append({"url": url, "params": dict(params), **kwargs})
        if url in {
            usfws_module.USFWS_IMAGE_SEARCH_URL,
            usfws_module.USFWS_GLOBAL_SEARCH_URL,
        }:
            if "species" in params:
                assert url == usfws_module.USFWS_IMAGE_SEARCH_URL
                path = fixture_dir / "species.json"
            elif params.get("$keywords") == '"Rufous Hummingbird"':
                assert url == usfws_module.USFWS_GLOBAL_SEARCH_URL
                assert params["type"] == '["Image"]'
                path = fixture_dir / "common.json"
            else:
                assert url == usfws_module.USFWS_GLOBAL_SEARCH_URL
                assert params["type"] == '["Image"]'
                assert params.get("$keywords") == '"Selasphorus rufus"'
                path = fixture_dir / "scientific.json"
            return _FakeResponse(payload=json.loads(path.read_text()))
        slug = url.removeprefix(f"{usfws_module.USFWS_BASE_URL}/media/")
        return _FakeResponse(text=(fixture_dir / f"{slug}.html").read_text())

    monkeypatch.setattr(usfws_module, "_http_get", fake_get)
    monkeypatch.setattr(usfws_module.time, "sleep", lambda _: None)
    return calls


@pytest.fixture
def usfws_source_factory(usfws_transport):
    def factory():
        return usfws_module.usfws_source(
            target_species=[TARGET],
            run_id="fixture-run",
            loaded_at="2026-08-03T12:00:00Z",
            detail_workers=2,
        )

    return factory
