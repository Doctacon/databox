"""Scaffold a new dlt source following `docs/source-layout.md`.

Creates the full per-source tree (source package, model dirs with `.gitkeep`,
Soda contract dirs, Dagster domain stub), wires the new domain module into
`definitions.py`, and optionally appends an API-key line to `.env.example`.
The output passes `scripts/check_source_layout.py` on first commit because
the generated `source.py` carries a `scaffold-lint: skip=scaffolded` marker.

Usage:
    python scripts/new_source.py <name>
    python scripts/new_source.py <name> --shape file
    python scripts/new_source.py <name> --shape database --force
    python scripts/new_source.py <name> --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "source"
SHAPES = ("rest", "file", "database")

SOURCES_PKG_DIR = ROOT / "packages/databox-sources/databox_sources"
MODELS_DIR = ROOT / "transforms/main/models"
CONTRACTS_DIR = ROOT / "soda/contracts"
DOMAINS_DIR = ROOT / "packages/databox/databox/orchestration/domains"
DEFINITIONS_PATH = ROOT / "packages/databox/databox/orchestration/definitions.py"
SOURCES_REGISTRY_PATH = ROOT / "packages/databox/databox/config/sources.py"
ENV_EXAMPLE_PATH = ROOT / ".env.example"

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass
class PlannedFile:
    path: Path
    content: str


def validate_name(name: str) -> None:
    if not NAME_PATTERN.match(name):
        raise ValueError(
            f"invalid source name {name!r}: must be lowercase, start with a letter, "
            "and contain only [a-z0-9_]"
        )
    reserved = {"analytics", "_shared", "base", "registry"}
    if name in reserved:
        raise ValueError(f"source name {name!r} is reserved; pick another")


def render(shape: str, name: str, no_auth: bool = False) -> dict[Path, str]:
    """Return the planned file tree for a new source: {relative_path: content}."""
    env = Environment(
        loader=FileSystemLoader([str(TEMPLATES_DIR / "common"), str(TEMPLATES_DIR / shape)]),
        keep_trailing_newline=True,
        undefined=StrictUndefined,
        autoescape=False,
    )
    ctx = {
        "name": name,
        "name_upper": name.upper(),
        "name_title": name.title(),
        "no_auth": no_auth,
    }

    files: dict[Path, str] = {
        SOURCES_PKG_DIR / name / "__init__.py": env.get_template("__init__.py.j2").render(**ctx),
        SOURCES_PKG_DIR / name / "source.py": env.get_template("source.py.j2").render(**ctx),
        SOURCES_PKG_DIR / name / "config.yaml": env.get_template("config.yaml.j2").render(**ctx),
        DOMAINS_DIR / f"{name}.py": env.get_template("domain.py.j2").render(**ctx),
        MODELS_DIR / name / "staging" / ".gitkeep": "",
        MODELS_DIR / name / "marts" / ".gitkeep": "",
        CONTRACTS_DIR / f"{name}_staging" / ".gitkeep": "",
        CONTRACTS_DIR / name / ".gitkeep": "",
    }
    return files


def check_collision(files: dict[Path, str], force: bool) -> list[Path]:
    """Return existing paths. If `force` is False and any exist, caller should abort."""
    existing = [p for p in files if p.exists()]
    if existing and not force:
        return existing
    return []


def write_files(files: dict[Path, str]) -> None:
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def wire_definitions(name: str, path: Path | None = None) -> bool:
    """Add `name` to the domains import line and to the three splat-wiring
    points in `definitions.py`. Idempotent — returns True if anything changed.
    """
    if path is None:
        path = DEFINITIONS_PATH
    text = path.read_text()
    changed = False

    # 1. Import line — alphabetical insertion.
    import_re = re.compile(r"^(from databox\.orchestration\.domains import )(.+)$", re.MULTILINE)
    m = import_re.search(text)
    if m is None:
        raise RuntimeError("could not locate domains import in definitions.py")
    current = sorted({n.strip() for n in m.group(2).split(",") if n.strip()})
    if name not in current:
        merged = sorted([*current, name])
        new_import = f"{m.group(1)}{', '.join(merged)}"
        text = import_re.sub(new_import, text, count=1)
        changed = True

    # 2. Splat anchors — insert before the analytics entry in each list.
    splat_targets = [
        (
            f"        *{name}.sqlmesh_asset_keys,",
            "        *analytics.sqlmesh_asset_keys,",
        ),
        (
            f"        *{name}.asset_checks,",
            "        *analytics.asset_checks,",
        ),
    ]
    for new_line, anchor in splat_targets:
        if new_line in text:
            continue
        if anchor not in text:
            raise RuntimeError(f"could not find anchor {anchor!r} in definitions.py")
        text = text.replace(anchor, f"{new_line}\n{anchor}", 1)
        changed = True

    # 3. dlt_asset_keys splat — insert just before the first sqlmesh_asset_keys line.
    dlt_line = f"        *{name}.dlt_asset_keys,"
    if dlt_line not in text:
        anchor = "        *ebird.sqlmesh_asset_keys,"
        if anchor not in text:
            raise RuntimeError("could not find ebird.sqlmesh_asset_keys anchor")
        text = text.replace(anchor, f"{dlt_line}\n{anchor}", 1)
        changed = True

    if changed:
        path.write_text(text)
    return changed


def wire_sources_registry(name: str, path: Path | None = None) -> bool:
    """Append a `Source(name=...)` entry to the `SOURCES` list in sources.py.

    Idempotent — returns True when the file was modified. The raw_tables tuple
    is left empty; the operator fills it in once the dlt resources are real.
    """
    if path is None:
        path = SOURCES_REGISTRY_PATH
    text = path.read_text()
    if f'Source(name="{name}"' in text or f"Source(name='{name}'" in text:
        return False

    closing = "\n]\n"
    if closing not in text:
        raise RuntimeError("could not locate SOURCES list closing `\\n]\\n` in sources.py")
    entry = f'    Source(name="{name}", raw_tables=()),\n]\n'
    text = text.replace(closing, f"\n{entry}", 1)
    path.write_text(text)
    return True


def ensure_env_stub(name: str, path: Path | None = None) -> bool:
    """Append an `API_KEY_<NAME>=` line to `.env.example` if missing.

    Returns True if the file was modified (or would be, in dry-run)."""
    if path is None:
        path = ENV_EXAMPLE_PATH
    key = f"API_KEY_{name.upper()}="
    if not path.exists():
        return False
    text = path.read_text()
    if key in text:
        return False
    suffix = "\n" if text.endswith("\n") else "\n\n"
    path.write_text(text + f"{suffix}{key}\n")
    return True


def print_next_steps(name: str) -> None:
    title = name.title()
    print(f"\nScaffolded source '{name}'. Next steps:\n")
    print(
        f"  1. Fill in `@dlt.resource`s in "
        f"packages/databox-sources/databox_sources/{name}/source.py,"
        f" then remove the `# scaffold-lint: skip=scaffolded` marker."
    )
    print(
        f"  2. Add staging SQL under transforms/main/models/{name}/staging/"
        f" (at least one `stg_*.sql`)."
    )
    print(
        f"  3. Add a Soda contract under soda/contracts/{name}_staging/ for each staging table,"
        f" then mart contracts under soda/contracts/{name}/."
    )
    print(
        f"  4. Wire the real assets in packages/databox/databox/orchestration/domains/{name}.py"
        f" and `{title.lower()}.daily_pipeline` / `.schedule` into definitions.py."
    )
    print("  5. Run `python scripts/check_source_layout.py` and `task ci` to verify.\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("name", help="source name (lowercase, snake_case)")
    p.add_argument(
        "--shape",
        choices=SHAPES,
        default="rest",
        help="which template set to use (default: rest)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print the planned file tree without writing",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="overwrite files that already exist on disk",
    )
    p.add_argument(
        "--no-auth",
        action="store_true",
        help="emit a REST stub with no API-key guard and skip the .env.example append "
        "(only valid with --shape rest)",
    )
    args = p.parse_args(argv)

    if args.no_auth and args.shape != "rest":
        print("error: --no-auth is only valid with --shape rest", file=sys.stderr)
        return 2

    try:
        validate_name(args.name)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    files = render(args.shape, args.name, no_auth=args.no_auth)

    if args.dry_run:
        print(f"Would create {len(files)} file(s) for source '{args.name}' (shape={args.shape}):")
        for path in sorted(files):
            marker = " (exists)" if path.exists() else ""
            print(f"  {path.relative_to(ROOT)}{marker}")
        print("\n(no files written — pass without --dry-run to scaffold)")
        return 0

    collisions = check_collision(files, force=args.force)
    if collisions:
        print(
            f"error: {len(collisions)} file(s) already exist; pass --force to overwrite:",
            file=sys.stderr,
        )
        for path in collisions:
            print(f"  {path.relative_to(ROOT)}", file=sys.stderr)
        return 1

    write_files(files)
    wire_definitions(args.name)
    wire_sources_registry(args.name)
    if args.shape == "rest" and not args.no_auth:
        ensure_env_stub(args.name)

    print_next_steps(args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
