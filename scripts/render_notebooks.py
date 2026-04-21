"""Execute every notebook under `notebooks/` and render HTML into docs/.

Output layout:
    notebooks/metrics_demo.ipynb → docs/examples/metrics-demo/index.html

Each notebook gets its own directory (slug derived from filename, underscores
→ hyphens, `.ipynb` stripped). The HTML file is named `index.html` so MkDocs
nav entries can point at the directory itself.

Exit: 0 on success, 1 on any execution or conversion failure.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
OUTPUT_ROOT = PROJECT_ROOT / "docs" / "examples"


def slugify(name: str) -> str:
    return name.replace("_", "-").removesuffix(".ipynb")


def render(notebook: Path) -> bool:
    slug = slugify(notebook.name)
    out_dir = OUTPUT_ROOT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"rendering {notebook.relative_to(PROJECT_ROOT)} → {out_dir.relative_to(PROJECT_ROOT)}/")

    cmd = [
        "jupyter",
        "nbconvert",
        "--to",
        "html",
        "--execute",
        "--ExecutePreprocessor.timeout=180",
        "--output",
        "index",
        "--output-dir",
        str(out_dir),
        str(notebook),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return False
    return True


def main() -> int:
    notebooks = sorted(NOTEBOOKS_DIR.glob("*.ipynb"))
    if not notebooks:
        print("no notebooks found under notebooks/", file=sys.stderr)
        return 0

    failures = [nb for nb in notebooks if not render(nb)]
    if failures:
        print(f"\n{len(failures)} notebook(s) failed to render:", file=sys.stderr)
        for nb in failures:
            print(f"  {nb.relative_to(PROJECT_ROOT)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
