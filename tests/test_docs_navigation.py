"""Compatibility contracts for public documentation navigation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docs_home_preserves_legacy_fragment_ids() -> None:
    index = (ROOT / "docs/index.md").read_text(encoding="utf-8")
    for fragment in ("whats-here", "architecture-decisions", "regenerate"):
        assert index.count(f'id="{fragment}"') == 1
