"""Utility modules for the tox-older project."""

from .intoxicacao_analysis import (
    DEFAULT_END_YEAR,
    DEFAULT_START_YEAR,
    build_descriptive_stats,
    build_insight_lines,
    build_overall_by_year,
    build_state_summary,
    build_state_year,
    build_top_groups_by_state,
    build_toxic_profile,
    build_year_totals,
    filter_year_window,
    format_insights_markdown,
    load_intoxicacao_tidy,
    save_state_sex_timeseries_charts,
    summarize_year_coverage,
    write_text_report,
)

__all__ = [
    "DEFAULT_END_YEAR",
    "DEFAULT_START_YEAR",
    "build_descriptive_stats",
    "build_insight_lines",
    "build_overall_by_year",
    "build_state_summary",
    "build_state_year",
    "build_top_groups_by_state",
    "build_toxic_profile",
    "build_year_totals",
    "filter_year_window",
    "format_insights_markdown",
    "load_intoxicacao_tidy",
    "save_state_sex_timeseries_charts",
    "summarize_year_coverage",
    "write_text_report",
]
