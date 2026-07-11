"""Static and API contracts for the local Rufous product shell."""

from __future__ import annotations

import re
from pathlib import Path

from databox.api import create_app

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "app/src/styles.css").read_text(encoding="utf-8")
APP = (ROOT / "app/src/App.tsx").read_text(encoding="utf-8")


def test_rufous_display_name_and_api_title(tmp_path: Path) -> None:
    visible_sources = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "app/index.html",
            "app/src/App.tsx",
            "app/src/BirdPages.tsx",
            "app/src/MyBirds.tsx",
            "app/src/TargetBird.tsx",
            "docs/commands.md",
        )
    )
    assert "Birding Trip Copilot" not in visible_sources
    assert not re.search(r"\bDatabox\b", visible_sources)
    assert "Rufous" in visible_sources
    assert create_app(database_path=tmp_path / "rufous.duckdb").title == "Rufous"
    # Technical identities are intentionally stable.
    assert '"name": "databox-birding-trip-copilot"' in (ROOT / "app/package.json").read_text(
        encoding="utf-8"
    )
    assert "data/databox.duckdb" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_theme_tokens_components_routes_and_states_are_covered() -> None:
    for token in (
        "--rust-700",
        "--teal-800",
        "--cream-100",
        "--gold-400",
        "--ink",
        "--success",
        "--warning",
        "--error",
        "--step-radius",
    ):
        assert token in CSS
    for selector in (
        ".site-header",
        ".planner-sidebar",
        ".hero-card",
        ".panel",
        ".species-card",
        ".bird-catalog-card",
        ".catalog-profile-media-grid",
        ".collection-list",
        ".target-form",
        ".confirm-dialog",
        ".recommendation-call audio",
        ".loading",
        ".empty",
        ".error",
        ".success",
        ".badge.warning",
        ".status-dot",
    ):
        assert selector in CSS
    for route in ("Trip Planner", "Arizona Birds", "My Birds", "Find This Bird"):
        assert route in APP


def test_accessibility_responsive_and_reduced_motion_contracts() -> None:
    assert ":focus-visible" in CSS
    assert "min-height: 44px" in CSS
    assert "overflow-wrap: anywhere" in CSS
    assert "word-break: break-word" in CSS
    assert "max-height: calc(100vh - 32px)" in CSS
    assert "@media (max-width: 820px)" in CSS
    assert "@media (max-width: 540px)" in CSS
    assert "min-width: 320px" in CSS
    reduced = CSS[CSS.index("@media (prefers-reduced-motion: reduce)") :]
    assert "animation: none" in reduced
    assert "transition-duration: .01ms" in reduced
    assert "body::before { background: none; }" in reduced
    assert "prefers-contrast: more" in CSS
    # Statuses remain distinguishable by explicit glyphs/text, not hue alone.
    for marker in ('content: "▲ "', 'content: "! ERROR"', 'content: "✓ SUCCESS"'):
        assert marker in CSS


def test_original_local_motif_and_no_remote_theme_assets() -> None:
    assert '<svg className="brand-mark"' in APP
    assert "brand-wing" in APP
    scanned = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ("app/index.html", "app/package.json", "app/src/App.tsx", "app/src/styles.css")
    )
    assert "@import" not in CSS
    assert not re.search(r"url\(\s*['\"]?https?://", CSS, re.IGNORECASE)
    assert not re.search(r"<(?:link|script)[^>]+https?://", scanned, re.IGNORECASE)
    forbidden = ("pokemon", "pokédex", "mapbox", "google fonts", "fonts.googleapis")
    assert all(term not in scanned.lower() for term in forbidden)
