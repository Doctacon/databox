"""Scaffold a new dlt source following `docs/source-layout.md`.

Creates the per-source ingestion tree, adds its canonical registry entry, and
optionally appends an API-key line to `.env.example`. Dagster definitions and CI
discover completed sources from the registry without manual source lists.
The generated skip marker makes the incomplete scaffold visible, but completed
contract and CI validation fail until its inventory, domain, and profile tests
are implemented.

Usage:
    python scripts/new_source.py <name>
    python scripts/new_source.py <name> --shape file
    python scripts/new_source.py <name> --dry-run
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from databox.config.sources import SOURCE_NAME_PATTERN
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "source"
SHAPES = ("rest", "file")

SOURCES_PKG_DIR = ROOT / "packages/databox-sources/databox_sources"
MODELS_DIR = ROOT / "transforms/main/models"
CONTRACTS_DIR = ROOT / "soda/contracts"
DOMAINS_DIR = ROOT / "packages/databox/databox/orchestration/domains"
SOURCES_REGISTRY_PATH = ROOT / "packages/databox/databox/config/sources.py"
ENV_EXAMPLE_PATH = ROOT / ".env.example"


@dataclass
class PlannedFile:
    path: Path
    content: str


def validate_name(name: str) -> None:
    if not SOURCE_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            f"invalid source name {name!r}: must be lowercase snake_case, start with a letter, "
            "and use single underscores only between alphanumeric segments"
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
        DOMAINS_DIR / f"{name}.py": env.get_template("domain.py.j2").render(**ctx),
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


def wire_sources_registry(name: str, verification_profile: str, path: Path | None = None) -> bool:
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
    entry = (
        f'    Source(name="{name}", raw_tables=(), '
        f'verification_profile="{verification_profile}"),\n]\n'
    )
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


def print_next_steps(name: str, verification_profile: str) -> None:
    title = name.title()
    print(f"\nScaffolded source '{name}'. Next steps:\n")
    print(
        f"  1. Fill in `@dlt.resource`s in "
        f"packages/databox-sources/databox_sources/{name}/source.py,"
        f" then remove the `# scaffold-lint: skip=scaffolded` marker."
    )
    print(
        "  2. Run the annotation workflow so `.schema/<cdm-name>/` includes this source: "
        "annotate-sources → create-ontology → generate-cdm."
    )
    print(
        "  3. Extend SQLMesh CDM models under "
        "transforms/main/models/environmental_observations/ when the CDM changes."
    )
    print(
        f"  4. Wire the real assets in packages/databox/databox/orchestration/domains/{name}.py; "
        f"the registry exposes `{title.lower()}.daily_pipeline` / `.schedule` to Definitions."
    )
    if verification_profile == "file_snapshot":
        print(
            "  5. Add the source-specific pinned `config.yaml` manifest plus "
            "test_resources.py, test_schema.py, test_smoke.py, test_idempotency.py, "
            "and test_staged_publish.py."
        )
    else:
        print(
            "  5. Add test_resources.py, test_schema.py, test_smoke.py, and "
            "test_idempotency.py with offline VCR fixtures."
        )
    print(
        "  6. Until those obligations and raw_tables are complete, "
        "`python scripts/check_source_layout.py` and the CI matrix fail. "
        "Remove the skip marker only when they pass.\n"
    )


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
    profile = "http" if args.shape == "rest" else "file_snapshot"
    wire_sources_registry(args.name, profile)
    if args.shape == "rest" and not args.no_auth:
        ensure_env_stub(args.name)

    print_next_steps(args.name, profile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
