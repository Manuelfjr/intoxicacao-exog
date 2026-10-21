"""Replace the chart images inside the banner PDF with freshly rendered ones.

Each chart image already placed in the banner is located by its aspect ratio, a new
version is rendered with exactly that ratio (larger fonts, see export_charts.py) and
swapped in place, so position and size on the banner stay the same.

Usage (PyMuPDF is not a project dependency, so run it through uv):
    uv run --no-project --with pymupdf python dashboard/update_banner.py "Banner.pdf"
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_charts import DEFAULT_CHROME, JOBS, ROOT, render_charts  # noqa: E402

# Gráfico do dashboard -> largura de renderização (a altura vem da proporção no banner).
SLOTS = {
    "03-mapa-calor-relativo-ao-pico": 1700,
    "07-grupos-de-agentes-casos": 1500,
    "01-serie-anual-por-sexo": 1300,
}
# Proporções (largura/altura) dos gráficos que estavam no banner.
OLD_RATIOS = {
    "03-mapa-calor-relativo-ao-pico": 3.27,
    "07-grupos-de-agentes-casos": 1.71,
    "01-serie-anual-por-sexo": 1.84,
}


def find_slots(page: pymupdf.Page) -> dict[str, tuple[int, pymupdf.Rect]]:
    slots: dict[str, tuple[int, pymupdf.Rect]] = {}
    for image in page.get_images(full=True):
        xref, width = image[0], image[2]
        if width < 1000:
            continue
        for rect in page.get_image_rects(xref):
            ratio = rect.width / rect.height
            for name, expected in OLD_RATIOS.items():
                if abs(ratio - expected) < 0.03 and name not in slots:
                    slots[name] = (xref, rect)
    missing = set(SLOTS) - set(slots)
    if missing:
        raise SystemExit(f"Gráficos não encontrados no banner: {', '.join(sorted(missing))}")
    return slots


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("banner", type=Path, help="PDF do banner")
    parser.add_argument("--output", type=Path, default=ROOT / "banner-atualizado.pdf")
    parser.add_argument("--boost", type=float, default=2.4)
    parser.add_argument("--scale", type=int, default=3)
    parser.add_argument("--chrome", default=os.environ.get("CHROME", DEFAULT_CHROME))
    args = parser.parse_args()

    document = pymupdf.open(args.banner)
    page = document[0]
    slots = find_slots(page)

    jobs = []
    for job in JOBS:
        if job["name"] in SLOTS:
            _, rect = slots[job["name"]]
            width = SLOTS[job["name"]]
            jobs.append({**job, "width": width, "height": round(width * rect.height / rect.width)})

    work = Path(tempfile.mkdtemp(prefix="banner-"))
    out_dir = work / "charts"
    out_dir.mkdir()
    try:
        render_charts(jobs, out_dir, work, args.boost, args.scale, args.chrome)
        for name, (xref, rect) in slots.items():
            page.replace_image(xref, filename=str(out_dir / f"{name}.png"))
            print(f"{name}: substituído em {[round(v) for v in rect]}")
        document.save(args.output, garbage=3, deflate=True)
        print(args.output)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
