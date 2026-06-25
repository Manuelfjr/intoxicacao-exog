"""Build and serve the local dashboard."""

from __future__ import annotations

import os
import socket
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def build_dashboard_files(root: Path) -> tuple[Path, Path]:
    if str(root) not in sys.path:
        sys.path.append(str(root))

    from utils.intoxicacao_analysis import (
        DEFAULT_END_YEAR,
        DEFAULT_START_YEAR,
        build_dashboard_payload,
        build_descriptive_stats,
        build_insight_lines,
        build_overall_by_year,
        build_state_case_totals,
        build_state_summary,
        build_state_year,
        build_top_groups_by_state,
        build_toxic_profile,
        build_year_totals,
        copy_plotly_bundle,
        filter_year_window,
        load_intoxicacao_tidy,
        summarize_year_coverage,
        write_json_report,
    )

    data_path = root / "data" / "raw" / "Dados CFF - Intoxicação exógena .xlsx"
    dashboard_dir = root / "dashboard"
    payload_path = dashboard_dir / "data" / "dashboard_data.json"
    plotly_bundle_path = dashboard_dir / "assets" / "plotly.min.js"

    df_raw = load_intoxicacao_tidy(data_path)
    df = filter_year_window(df_raw, DEFAULT_START_YEAR, DEFAULT_END_YEAR)
    coverage = summarize_year_coverage(df, DEFAULT_START_YEAR, DEFAULT_END_YEAR)
    year_totals = build_year_totals(df, DEFAULT_START_YEAR, DEFAULT_END_YEAR)
    state_summary = build_state_summary(year_totals)
    descriptive_stats = build_descriptive_stats(year_totals)
    overall_by_year = build_overall_by_year(year_totals)
    state_year = build_state_year(year_totals)
    state_case_totals = build_state_case_totals(year_totals)
    toxic_profile = build_toxic_profile(df)
    top_groups_by_state = build_top_groups_by_state(df, top_n=3)
    insight_lines = build_insight_lines(
        year_totals=year_totals,
        state_summary=state_summary,
        toxic_profile=toxic_profile,
        coverage=coverage,
        start_year=DEFAULT_START_YEAR,
        end_year=DEFAULT_END_YEAR,
    )

    payload = build_dashboard_payload(
        df=df,
        coverage=coverage,
        year_totals=year_totals,
        state_summary=state_summary,
        descriptive_stats=descriptive_stats,
        overall_by_year=overall_by_year,
        state_year=state_year,
        state_case_totals=state_case_totals,
        toxic_profile=toxic_profile,
        top_groups_by_state=top_groups_by_state,
        insight_lines=insight_lines,
        start_year=DEFAULT_START_YEAR,
        end_year=DEFAULT_END_YEAR,
    )
    write_json_report(payload_path, payload)
    copy_plotly_bundle(plotly_bundle_path)

    return payload_path, plotly_bundle_path


def find_available_port(host: str, preferred_port: int, max_attempts: int = 20) -> int:
    """Return the first available port starting from the preferred one."""

    for port in range(preferred_port, preferred_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex((host, port)) != 0:
                return port

    raise OSError(
        f"Nao foi encontrada uma porta livre entre {preferred_port} e {preferred_port + max_attempts - 1}."
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    dashboard_dir = root / "dashboard"

    payload_path, plotly_bundle_path = build_dashboard_files(root)

    host = os.environ.get("HOST", "127.0.0.1")
    requested_port = int(os.environ.get("PORT", "8765"))
    port = find_available_port(host, requested_port)

    handler = partial(SimpleHTTPRequestHandler, directory=str(dashboard_dir))
    server = ThreadingHTTPServer((host, port), handler)

    print(f"Dashboard data: {payload_path}")
    print(f"Plotly bundle: {plotly_bundle_path}")
    if port != requested_port:
        print(f"Porta {requested_port} em uso; usando automaticamente a porta {port}.")
    print(f"Serving dashboard at http://{host}:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
