"""Export a self-contained HTML version of the local dashboard."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from dashboard.run_local import build_dashboard_files


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    dashboard_dir = root / "dashboard"
    output_path = dashboard_dir / "dashboard_standalone.html"

    payload_path, plotly_bundle_path = build_dashboard_files(root)

    html_template = (dashboard_dir / "index.html").read_text(encoding="utf-8")
    css_text = (dashboard_dir / "styles.css").read_text(encoding="utf-8")
    js_text = (dashboard_dir / "app.js").read_text(encoding="utf-8")
    json_text = payload_path.read_text(encoding="utf-8")
    plotly_text = plotly_bundle_path.read_text(encoding="utf-8")

    html_text = (
        html_template.replace(
            '    <link rel="preconnect" href="https://fonts.googleapis.com" />\n',
            "",
        )
        .replace(
            '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n',
            "",
        )
        .replace(
            '    <link\n'
            '      href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&family=Sora:wght@500;600;700&display=swap"\n'
            '      rel="stylesheet"\n'
            '    />\n',
            "",
        )
        .replace(
        '<link rel="stylesheet" href="./styles.css" />',
        f"<style>\n{css_text}\n</style>",
    )
        .replace(
            '<script src="./assets/plotly.min.js"></script>\n    <script src="./app.js"></script>',
            f"    <script>\n{plotly_text}\n</script>\n"
            f"    <script>\nwindow.__DASHBOARD_DATA__ = {json_text};\n</script>\n"
            f"    <script>\n{js_text}\n</script>",
        )
    )

    output_path.write_text(html_text, encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
