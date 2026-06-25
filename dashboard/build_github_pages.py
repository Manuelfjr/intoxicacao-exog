"""Build a clean static folder ready for GitHub Pages deployment."""

from __future__ import annotations

from pathlib import Path
from shutil import copy2, rmtree
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from dashboard.run_local import build_dashboard_files


PUBLIC_FILES = ("index.html", "styles.css", "app.js")


def build_pages_site(root: Path) -> Path:
    """Create a clean static site folder with the dashboard assets only."""

    dashboard_dir = root / "dashboard"
    site_dir = root / "site"

    build_dashboard_files(root)

    if site_dir.exists():
        rmtree(site_dir)

    (site_dir / "assets").mkdir(parents=True, exist_ok=True)
    (site_dir / "data").mkdir(parents=True, exist_ok=True)

    for filename in PUBLIC_FILES:
        copy2(dashboard_dir / filename, site_dir / filename)

    copy2(dashboard_dir / "assets" / "plotly.min.js", site_dir / "assets" / "plotly.min.js")
    copy2(dashboard_dir / "data" / "dashboard_data.json", site_dir / "data" / "dashboard_data.json")

    (site_dir / ".nojekyll").write_text("", encoding="utf-8")

    return site_dir


def main() -> None:
    output_dir = build_pages_site(ROOT)
    print(output_dir)


if __name__ == "__main__":
    main()
