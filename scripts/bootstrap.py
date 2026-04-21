"""Rewrite repo identity in-place from `scaffold.yaml`.

Reads the current identity from `scaffold.yaml`, accepts overrides on the CLI,
computes the set of literal-string substitutions needed to transition the
committed files from the current identity to the new one, applies them across
every `bootstrap.includes` pattern, and writes the new values back to
`scaffold.yaml`.

Design notes:

- Committed files always hold *rendered* values (not Jinja-style tokens). That
  keeps syntax highlighting, linting, and IDE tooling working in every file.
- `scaffold.yaml` is the ledger: it remembers what the current values are, so a
  later `task init --name X` knows what to replace.
- Replacements are ordered *specific → general*: `Doctacon/databox` must be
  substituted before `Doctacon` alone, so composite tokens don't fracture.
- The bare lowercase slug (`databox`) is intentionally NOT replaced — it is
  also the Python package name. Only composite tokens that cannot collide with
  Python identifiers (`{slug}-workspace`, full URLs, the capitalized brand)
  are substituted.

Usage:
    python scripts/bootstrap.py                              # no-op dry-run
    python scripts/bootstrap.py --name Weatherbox ...        # apply
    python scripts/bootstrap.py --check                      # non-zero on drift
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD_PATH = ROOT / "scaffold.yaml"


@dataclass
class Identity:
    name: str
    slug: str
    description: str
    copyright_holder: str
    org: str
    repo: str
    site_url: str

    @classmethod
    def from_mapping(cls, data: dict) -> Identity:
        return cls(
            name=data["project"]["name"],
            slug=data["project"]["slug"],
            description=data["project"]["description"],
            copyright_holder=data["project"]["copyright_holder"],
            org=data["github"]["org"],
            repo=data["github"]["repo"],
            site_url=data["docs"]["site_url"],
        )


def load_scaffold(path: Path = SCAFFOLD_PATH) -> dict:
    return yaml.safe_load(path.read_text())


def overlay(data: dict, **overrides: str | None) -> dict:
    """Return a new scaffold dict with CLI overrides applied."""
    out = yaml.safe_load(yaml.safe_dump(data))  # deep copy via round-trip
    if overrides.get("name"):
        out["project"]["name"] = overrides["name"]
    if overrides.get("slug"):
        out["project"]["slug"] = overrides["slug"]
    if overrides.get("description"):
        out["project"]["description"] = overrides["description"]
    if overrides.get("copyright_holder"):
        out["project"]["copyright_holder"] = overrides["copyright_holder"]
    if overrides.get("org"):
        out["github"]["org"] = overrides["org"]
    if overrides.get("repo"):
        out["github"]["repo"] = overrides["repo"]
    if overrides.get("site_url"):
        out["docs"]["site_url"] = overrides["site_url"]
    return out


def compute_substitutions(old: Identity, new: Identity) -> list[tuple[str, str]]:
    """Return (old_str, new_str) pairs, ordered specific→general."""
    subs: list[tuple[str, str]] = []
    # Full site URL — most specific, must go first.
    if old.site_url != new.site_url:
        subs.append((old.site_url, new.site_url))
    # Composite GitHub path — catches both github.com/Doctacon/databox and
    # bare "Doctacon/databox" repo_name references.
    old_path = f"{old.org}/{old.repo}"
    new_path = f"{new.org}/{new.repo}"
    if old_path != new_path:
        subs.append((old_path, new_path))
    # Pages-style hostname (lowercase org).
    old_pages = f"{old.org.lower()}.github.io/{old.repo}"
    new_pages = f"{new.org.lower()}.github.io/{new.repo}"
    if old_pages != new_pages:
        subs.append((old_pages, new_pages))
    # Workspace name token (safe — does not collide with Python `databox`).
    old_ws = f"{old.slug}-workspace"
    new_ws = f"{new.slug}-workspace"
    if old_ws != new_ws:
        subs.append((old_ws, new_ws))
    # Capitalized brand — README heading, mkdocs site_name, site_description.
    if old.name != new.name:
        subs.append((old.name, new.name))
    # Project description string (site_description, pyproject description).
    if old.description != new.description:
        subs.append((old.description, new.description))
    # LICENSE copyright holder line.
    if old.copyright_holder != new.copyright_holder:
        subs.append((old.copyright_holder, new.copyright_holder))
    return subs


def resolve_includes(patterns: list[str], root: Path = ROOT) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for pat in patterns:
        for p in sorted(root.glob(pat)):
            if p.is_file() and p not in seen:
                out.append(p)
                seen.add(p)
    return out


def apply_substitutions(files: list[Path], subs: list[tuple[str, str]]) -> list[tuple[Path, int]]:
    """Apply substitutions in order. Returns list of (file, hits) for files that changed."""
    changed: list[tuple[Path, int]] = []
    for path in files:
        text = path.read_text()
        new_text = text
        total = 0
        for old, new in subs:
            if old and old in new_text:
                total += new_text.count(old)
                new_text = new_text.replace(old, new)
        if new_text != text:
            path.write_text(new_text)
            changed.append((path, total))
    return changed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Rewrite repo identity in-place from scaffold.yaml.")
    p.add_argument("--name", help="new project brand name (e.g. Weatherbox)")
    p.add_argument("--slug", help="new project slug (lowercase, e.g. weatherbox)")
    p.add_argument("--description", help="new project description")
    p.add_argument("--copyright-holder", dest="copyright_holder", help="new copyright holder")
    p.add_argument("--org", help="new GitHub org")
    p.add_argument("--repo", help="new GitHub repo name")
    p.add_argument("--site-url", dest="site_url", help="new docs site URL")
    p.add_argument("--check", action="store_true", help="exit 1 if rewrites would occur")
    args = p.parse_args(argv)

    data = load_scaffold()
    old = Identity.from_mapping(data)
    new_data = overlay(
        data,
        name=args.name,
        slug=args.slug,
        description=args.description,
        copyright_holder=args.copyright_holder,
        org=args.org,
        repo=args.repo,
        site_url=args.site_url,
    )
    new = Identity.from_mapping(new_data)

    subs = compute_substitutions(old, new)
    if not subs:
        print("scaffold: identity unchanged, nothing to do")
        return 0

    includes = data["bootstrap"]["includes"]
    files = resolve_includes(includes)
    if not files:
        print("scaffold: no files matched bootstrap.includes", file=sys.stderr)
        return 2

    if args.check:
        # Dry-run: report any file that would change.
        would_change = []
        for path in files:
            text = path.read_text()
            for old_s, _ in subs:
                if old_s and old_s in text:
                    would_change.append(path)
                    break
        if would_change:
            print("scaffold: drift detected in:", file=sys.stderr)
            for p in would_change:
                print(f"  - {p.relative_to(ROOT)}", file=sys.stderr)
            return 1
        return 0

    changed = apply_substitutions(files, subs)
    SCAFFOLD_PATH.write_text(yaml.safe_dump(new_data, sort_keys=False))

    print(f"scaffold: applied {len(subs)} substitution(s) across {len(changed)} file(s)")
    for path, hits in changed:
        print(f"  {path.relative_to(ROOT)}: {hits} replacement(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
