"""Export each dashboard chart as high-resolution PNG + SVG and zip them.

The charts are rendered by the dashboard itself (headless Chrome), with a font boost
so ticks, axis titles and labels stay legible when the images are shrunk into a
poster/banner. Output: <repo>/graficos-banner.zip and <repo>/graficos-banner.pdf (override with --output).

Usage:
    poetry run python dashboard/export_charts.py
    poetry run python dashboard/export_charts.py --boost 2.8 --scale 4
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / "dashboard"
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FONTS_LINK = (
    '<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700'
    '&family=Sora:wght@500;600;700&display=block" rel="stylesheet">'
)

# name, chart id, title, width, height, options applied before/after rendering.
JOBS = [
    {"name": "01-serie-anual-por-sexo", "id": "trend-chart", "title": "Série anual de notificações por sexo, 2007–2025", "width": 1300, "height": 820, "xdtick": 3},
    {"name": "02-participacao-feminina-por-ano", "id": "share-chart", "title": "Participação feminina nas notificações por ano", "width": 1200, "height": 760, "xdtick": 3},
    {"name": "03-mapa-calor-relativo-ao-pico", "id": "heatmap-chart", "title": "Intensidade por estado e ano (relativo ao pico de cada estado)", "width": 1700, "height": 780, "xdtick": 2, "cellFont": 24},
    {"name": "04-mapa-calor-casos-absolutos", "id": "heatmap-chart", "title": "Intensidade por estado e ano (casos absolutos)", "width": 1700, "height": 780, "xdtick": 2, "cellFont": 24, "click": ["#heatmap-mode button", 1]},
    {"name": "05-serie-por-estado", "id": "multiples-chart", "title": "Série anual por estado e sexo (escala própria por estado)", "width": 1600, "height": 1250, "columns": 3, "gaps": {"x": 0.08, "y": 0.2}},
    {"name": "06-casos-acumulados-por-estado", "id": "states-chart", "title": "Casos acumulados por estado e sexo, 2007–2025", "width": 1400, "height": 860},
    {"name": "07-grupos-de-agentes-casos", "id": "toxic-chart", "title": "Grupos de agentes tóxicos por sexo (casos)", "width": 1500, "height": 1150},
    {"name": "08-grupos-de-agentes-percentual", "id": "toxic-chart", "title": "Perfil de agentes tóxicos dentro de cada sexo (%)", "width": 1500, "height": 1150, "click": ["#toxic-mode button", 1]},
]

CAPTURE_PAGE = """<!doctype html><meta charset="utf-8">
<iframe id="f" src="/index.html" style="width:1600px;height:1200px;border:0"></iframe>
<pre id="o">running</pre>
<script>
const JOBS = __JOBS__;
const BOOST = __BOOST__;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const out = [];
const f = document.getElementById("f");
f.onload = async () => {
  await sleep(2500);
  const w = f.contentWindow, d = w.document, P = w.Plotly;
  const rerender = async () => { w.readTheme(); w.renderDashboard(); await sleep(900); };
  w.__CHART_FONT_BOOST = BOOST;
  await rerender();
  try {
    for (const job of JOBS) {
      w.__MULTIPLES_COLUMNS = job.columns || 0;
      w.__MULTIPLES_GAPS = job.gaps || null;
      if (job.click) d.querySelectorAll(job.click[0])[job.click[1]].click();
      await rerender();
      const gd = d.getElementById(job.id);
      const layout = JSON.parse(JSON.stringify(gd.layout));
      const titleSize = Math.round(16 * BOOST * 1.15);
      const titleSpace = Math.round(titleSize * 2.6);
      layout.paper_bgcolor = "#ffffff";
      layout.plot_bgcolor = "#ffffff";
      layout.margin = { ...layout.margin, t: (layout.margin?.t || 20) + titleSpace, r: Math.max(layout.margin?.r || 0, 30) };
      layout.title = { text: job.title, x: 0.01, xanchor: "left", y: 1 - 18 / job.height, yanchor: "top", yref: "container",
        font: { family: "Sora, sans-serif", size: titleSize, color: "#102f48" } };
      if (layout.legend) {
        layout.legend = layout.legend.yref === "container"
          ? { ...layout.legend, x: 1, xanchor: "right", y: 1 - (titleSpace - 4) / job.height, yanchor: "top" }
          : { ...layout.legend, y: 1.0, yanchor: "bottom" };
      }
      if (job.xdtick) {
        Object.keys(layout).filter((k) => k.startsWith("xaxis")).forEach((k) => { layout[k].dtick = job.xdtick; });
      }
      if (job.cellFont && layout.annotations) {
        layout.annotations.forEach((a) => { if (a.xref !== "paper") a.font = { ...a.font, size: job.cellFont }; });
      }
      delete layout.width; delete layout.height;
      // Linhas e marcadores mais grossos para impressão.
      const data = JSON.parse(JSON.stringify(gd.data)).map((trace) => {
        if (trace.type === "scatter") {
          if (trace.line) trace.line.width = (trace.line.width || 2) * 1.8;
          if (trace.marker && trace.marker.size) trace.marker.size = trace.marker.size * 1.5;
        }
        return trace;
      });
      const url = await P.toImage({ data, layout }, { format: "svg", width: job.width, height: job.height });
      await fetch("/save", { method: "POST", body: JSON.stringify({ name: job.name + ".svg", data: url }) });
      if (job.click) { d.querySelectorAll(job.click[0])[0].click(); }
      out.push(job.name);
    }
  } catch (e) { out.push("EXC " + String(e) + " " + (e && e.stack)); }
  document.getElementById("o").textContent = "DONE\\n" + out.join("\\n");
};
</script>
"""


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def make_handler(svg_dir: Path, page: str):
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.startswith("/_capture.html"):
                body = page.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

        def do_POST(self) -> None:
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            name = Path(payload["name"]).name
            svg = unquote(payload["data"].split(",", 1)[1])
            # Plotly escreve aspas duplas dentro do atributo style; troca por simples
            # para o SVG continuar válido fora do navegador.
            svg = svg.replace('"Source Sans 3", "Trebuchet MS", sans-serif', "'Source Sans 3', 'Trebuchet MS', sans-serif")
            (svg_dir / name).write_text(svg, encoding="utf-8")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args: object) -> None:
            pass

    return Handler


def svg_size(svg: str) -> tuple[int, int]:
    head = svg[: svg.index(">")]
    width = int(head.split('width="', 1)[1].split('"', 1)[0])
    height = int(head.split('height="', 1)[1].split('"', 1)[0])
    return width, height


def render_charts(jobs: list[dict], out_dir: Path, work: Path, boost: float, scale: int, chrome: str) -> None:
    """Render each job as <name>.svg + <name>.png (scale x) into out_dir."""

    page = CAPTURE_PAGE.replace("__JOBS__", json.dumps(jobs, ensure_ascii=False)).replace("__BOOST__", str(boost))
    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(make_handler(out_dir, page), directory=str(DASHBOARD_DIR)))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        dom = subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--window-size=1700,1300",
             "--virtual-time-budget=60000", "--dump-dom", f"http://127.0.0.1:{port}/_capture.html"],
            capture_output=True, text=True, timeout=240,
        ).stdout
    finally:
        server.shutdown()

    report = dom.split('<pre id="o">', 1)[-1].split("</pre>", 1)[0]
    if "EXC" in report or "DONE" not in report:
        raise SystemExit(f"Falha na captura dos gráficos:\n{report}")

    for svg_path in sorted(out_dir.glob("*.svg")):
        width, height = svg_size(svg_path.read_text(encoding="utf-8"))
        wrapper = work / f"{svg_path.stem}.html"
        wrapper.write_text(
            f'<!doctype html><meta charset="utf-8">{FONTS_LINK}'
            f"<style>html,body{{margin:0;background:#fff}}svg{{display:block}}</style>"
            f"{svg_path.read_text(encoding='utf-8')}",
            encoding="utf-8",
        )
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--force-device-scale-factor={scale}", f"--window-size={width},{height}",
             "--virtual-time-budget=6000", f"--screenshot={out_dir / (svg_path.stem + '.png')}",
             wrapper.as_uri()],
            capture_output=True, timeout=120, check=True,
        )
        print(f"{svg_path.stem}: {width * scale}x{height * scale}px")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--boost", type=float, default=2.4, help="fator de aumento do texto dos gráficos")
    parser.add_argument("--scale", type=int, default=3, help="fator de resolução dos PNGs")
    parser.add_argument("--output", type=Path, default=ROOT / "graficos-banner.zip")
    parser.add_argument("--chrome", default=os.environ.get("CHROME", DEFAULT_CHROME))
    args = parser.parse_args()

    work = Path(tempfile.mkdtemp(prefix="graficos-"))
    out_dir = work / args.output.stem
    out_dir.mkdir()

    try:
        render_charts(JOBS, out_dir, work, args.boost, args.scale, args.chrome)

        with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(out_dir.iterdir()):
                archive.write(file, f"{out_dir.name}/{file.name}")
        print(args.output)

        # PDF vetorial: um gráfico por página, A4 paisagem.
        pages = "".join(
            f'<section class="page">{svg_path.read_text(encoding="utf-8")}</section>'
            for svg_path in sorted(out_dir.glob("*.svg"))
        )
        pdf_html = work / "graficos.html"
        pdf_html.write_text(
            f'<!doctype html><meta charset="utf-8">{FONTS_LINK}<style>'
            "@page{size:A4 landscape;margin:12mm}"
            "html,body{margin:0;background:#fff}"
            ".page{height:calc(210mm - 24mm);display:flex;align-items:center;justify-content:center;"
            "break-after:page}.page:last-child{break-after:auto}"
            ".page svg{max-width:100%;max-height:100%;width:auto;height:auto}"
            f"</style>{pages}",
            encoding="utf-8",
        )
        pdf_path = args.output.with_suffix(".pdf")
        subprocess.run(
            [args.chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             "--virtual-time-budget=8000", f"--print-to-pdf={pdf_path}", pdf_html.as_uri()],
            capture_output=True, timeout=180, check=True,
        )
        print(pdf_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
