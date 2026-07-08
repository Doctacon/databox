"""Verify every registered dlt source follows the ingestion directory layout.

Required components per source `<name>`:

- `packages/databox-sources/databox_sources/<name>/source.py`
- `packages/databox-sources/databox_sources/<name>/config.yaml`
- `packages/databox/databox/orchestration/domains/<name>.py`

SQLMesh CDM models are intentionally not per-source required files. They live
under `transforms/main/models/environmental_observations/` after the `.schema`
CDM workflow has been reviewed.

An experimental / in-flight source can opt out by placing a
`# scaffold-lint: skip=<reason>` line in its `source.py` header (within
the first 10 lines). The source is then reported but not treated as a
failure.

Usage:
    python scripts/check_source_layout.py           # text output, exit 1 on error
    python scripts/check_source_layout.py --json    # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

SOURCES_DIR = Path("packages/databox-sources/databox_sources")
DOMAINS_DIR = Path("packages/databox/databox/orchestration/domains")
SKIP_MARKER = "scaffold-lint: skip="
SKIP_HEADER_LINES = 10


@dataclass
class SourceReport:
    name: str
    missing: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.skipped or not self.missing


def discover_sources(root: Path = SOURCES_DIR) -> list[str]:
    out: list[str] = []
    for child in sorted(root.iterdir()) if root.exists() else []:
        if not child.is_dir() or child.name.startswith("_") or child.name.startswith("."):
            continue
        if (child / "source.py").exists():
            out.append(child.name)
    return out


def _skip_marker(source_py: Path) -> str | None:
    if not source_py.exists():
        return None
    for line in source_py.read_text().splitlines()[:SKIP_HEADER_LINES]:
        idx = line.find(SKIP_MARKER)
        if idx >= 0:
            return line[idx + len(SKIP_MARKER) :].strip().split()[0] or "unspecified"
    return None


def check_source(name: str) -> SourceReport:
    src_pkg = SOURCES_DIR / name
    source_py = src_pkg / "source.py"
    report = SourceReport(name=name)
    marker = _skip_marker(source_py)
    if marker is not None:
        report.skipped = True
        report.skip_reason = marker
        return report

    if not source_py.exists():
        report.missing.append(str(source_py))
    if not (src_pkg / "config.yaml").exists():
        report.missing.append(str(src_pkg / "config.yaml"))

    domain_file = DOMAINS_DIR / f"{name}.py"
    if not domain_file.exists():
        report.missing.append(str(domain_file))

    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    a = p.parse_args(argv)

    sources = discover_sources()
    if not sources:
        print(
            "source-layout-lint error: no sources found under packages/databox-sources/",
            file=sys.stderr,
        )
        return 2

    reports = [check_source(name) for name in sources]
    failing = [r for r in reports if not r.ok]

    if a.json:
        print(json.dumps({"sources": [asdict(r) for r in reports]}, indent=2))
    else:
        for r in reports:
            if r.skipped:
                print(f"  ~ {r.name} (skipped: {r.skip_reason})")
            elif r.ok:
                print(f"  ✓ {r.name}")
            else:
                print(f"  ✗ {r.name}")
                for m in r.missing:
                    print(f"      missing: {m}")
        total = len(reports)
        skipped = sum(1 for r in reports if r.skipped)
        failed = len(failing)
        passed = total - skipped - failed
        print(f"\n{passed} ok · {skipped} skipped · {failed} failing (of {total})")

    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
