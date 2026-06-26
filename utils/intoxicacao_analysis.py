"""Utilities for the initial analysis of exogenous intoxication data."""

from __future__ import annotations

import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from shutil import copyfile
from zipfile import ZipFile

import pandas as pd

DEFAULT_START_YEAR = 2007
DEFAULT_END_YEAR = 2025

STATE_NAMES = {
    "AC": "Acre",
    "DF": "Distrito Federal",
    "PB": "Paraiba",
    "SC": "Santa Catarina",
    "SP": "Sao Paulo",
}

SEX_NAMES = {
    "F": "Feminino",
    "M": "Masculino",
}

DISPLAY_STATE_NAMES = {
    "Acre": "Acre",
    "Distrito Federal": "Distrito Federal",
    "Paraiba": "Paraíba",
    "Santa Catarina": "Santa Catarina",
    "Sao Paulo": "São Paulo",
}

DISPLAY_TOXIC_GROUP_NAMES = {
    "Cosmético_higiene pessoal": "Cosmético e higiene pessoal",
}

DEFAULT_SEX_PALETTE = {
    "Masculino": "#5B7FA3",
    "Feminino": "#C06A6A",
}

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

TIDY_COLUMNS = [
    "state_code",
    "state",
    "sex",
    "sex_label",
    "year",
    "toxic_group",
    "count",
    "total_year",
]

YEAR_TOTAL_COLUMNS = [
    "state",
    "state_code",
    "sex",
    "sex_label",
    "year",
    "total_year",
    "is_zero_filled",
]


def _read_shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []

    shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    shared_strings: list[str] = []

    for item in shared_root:
        parts = [
            text.text or ""
            for text in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        ]
        shared_strings.append("".join(parts))

    return shared_strings


def _column_index(cell_ref: str) -> int:
    column_label = re.match(r"([A-Z]+)", cell_ref).group(1)
    index = 0

    for char in column_label:
        index = index * 26 + (ord(char) - 64)

    return index


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str | None:
    cell_type = cell.attrib.get("t")
    value_node = cell.find("main:v", NS)

    if value_node is not None:
        value = value_node.text
        if cell_type == "s":
            return shared_strings[int(value)]
        return value

    inline_node = cell.find("main:is", NS)
    if inline_node is not None:
        parts = [
            text.text or ""
            for text in inline_node.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        ]
        return "".join(parts)

    return None


def _to_number(value: str | None) -> float:
    if value in (None, "", "-"):
        return 0.0

    return float(str(value).replace(",", "."))


def _slugify_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")


def _display_state_name(value: str) -> str:
    return DISPLAY_STATE_NAMES.get(value, value)


def _display_toxic_group_name(value: str) -> str:
    return DISPLAY_TOXIC_GROUP_NAMES.get(value, value)


def load_intoxicacao_tidy(data_path: Path) -> pd.DataFrame:
    """Load the workbook and return a tidy dataframe with observed rows only."""

    records: list[dict[str, object]] = []

    with ZipFile(data_path) as zf:
        shared_strings = _read_shared_strings(zf)
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        relations = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))

        relation_map = {relation.attrib["Id"]: relation.attrib["Target"] for relation in relations}

        for sheet in workbook.find("main:sheets", NS):
            sheet_name = sheet.attrib["name"]
            if " - " not in sheet_name:
                continue

            state_code, sex = [part.strip() for part in sheet_name.split(" - ")]
            relation_id = sheet.attrib[
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            ]
            sheet_path = "xl/" + relation_map[relation_id]
            sheet_root = ET.fromstring(zf.read(sheet_path))
            rows = sheet_root.find("main:sheetData", NS).findall("main:row", NS)

            parsed_rows = [
                {
                    _column_index(cell.attrib["r"]): _cell_value(cell, shared_strings)
                    for cell in row.findall("main:c", NS)
                }
                for row in rows
            ]

            header = parsed_rows[0]
            year_col = min(header)
            total_col = max(header)

            for row in parsed_rows[1:]:
                year_raw = row.get(year_col)
                if year_raw is None:
                    continue

                year_text = str(year_raw).strip()
                if year_text.lower() == "total":
                    continue

                year = int(float(year_text))
                total_year = _to_number(row.get(total_col))

                for col_idx, toxic_group in header.items():
                    if col_idx in (year_col, total_col):
                        continue

                    records.append(
                        {
                            "state_code": state_code,
                            "state": STATE_NAMES.get(state_code, state_code),
                            "sex": sex,
                            "sex_label": SEX_NAMES.get(sex, sex),
                            "year": year,
                            "toxic_group": toxic_group,
                            "count": _to_number(row.get(col_idx)),
                            "total_year": total_year,
                        }
                    )

    if not records:
        return pd.DataFrame(columns=TIDY_COLUMNS)

    df = pd.DataFrame(records)
    return df.sort_values(["state", "sex", "year", "toxic_group"]).reset_index(drop=True)


def filter_year_window(
    df: pd.DataFrame,
    start_year: int = DEFAULT_START_YEAR,
    end_year: int = DEFAULT_END_YEAR,
) -> pd.DataFrame:
    """Keep only rows inside the selected analysis window."""

    filtered = df.loc[df["year"].between(start_year, end_year)].copy()
    return filtered.sort_values(["state", "sex", "year", "toxic_group"]).reset_index(drop=True)


def summarize_year_coverage(
    df: pd.DataFrame,
    start_year: int = DEFAULT_START_YEAR,
    end_year: int = DEFAULT_END_YEAR,
) -> pd.DataFrame:
    """Summarize observed years and the years that will be zero-filled."""

    expected_years = list(range(start_year, end_year + 1))
    pairs = (
        df[["state", "state_code", "sex", "sex_label"]]
        .drop_duplicates()
        .sort_values(["state", "sex"])
        .reset_index(drop=True)
    )

    records: list[dict[str, object]] = []

    for pair in pairs.itertuples(index=False):
        observed = sorted(
            df.loc[
                (df["state"] == pair.state)
                & (df["state_code"] == pair.state_code)
                & (df["sex"] == pair.sex)
                & (df["sex_label"] == pair.sex_label),
                "year",
            ].drop_duplicates()
        )
        missing = [year for year in expected_years if year not in observed]

        records.append(
            {
                "state": pair.state,
                "state_code": pair.state_code,
                "sex_label": pair.sex_label,
                "observed_years": len(observed),
                "filled_zero_years": len(missing),
                "missing_year_list": ", ".join(str(year) for year in missing) if missing else "-",
            }
        )

    coverage = pd.DataFrame(records)
    return coverage.sort_values(
        ["filled_zero_years", "state", "sex_label"],
        ascending=[False, True, True],
    ).reset_index(drop=True)


def build_year_totals(
    df: pd.DataFrame,
    start_year: int = DEFAULT_START_YEAR,
    end_year: int = DEFAULT_END_YEAR,
) -> pd.DataFrame:
    """Aggregate totals by state, sex and year and fill absent years with zero."""

    filtered = filter_year_window(df, start_year=start_year, end_year=end_year)

    if filtered.empty:
        return pd.DataFrame(columns=YEAR_TOTAL_COLUMNS)

    observed = (
        filtered.groupby(["state", "state_code", "sex", "sex_label", "year"], as_index=False)
        .agg(total_year=("total_year", "max"), summed_groups=("count", "sum"))
        .assign(diff=lambda frame: frame["summed_groups"] - frame["total_year"])
    )

    max_diff = observed["diff"].abs().max()
    if max_diff > 1e-9:
        raise ValueError(
            "There are inconsistencies between the sum of toxic groups and the annual total. "
            f"Maximum difference: {max_diff}"
        )

    pairs = (
        filtered[["state", "state_code", "sex", "sex_label"]]
        .drop_duplicates()
        .sort_values(["state", "sex"])
        .assign(_key=1)
    )
    years = pd.DataFrame({"year": list(range(start_year, end_year + 1)), "_key": 1})

    full_grid = pairs.merge(years, on="_key", how="inner").drop(columns="_key")
    completed = full_grid.merge(
        observed[["state", "state_code", "sex", "sex_label", "year", "total_year"]],
        on=["state", "state_code", "sex", "sex_label", "year"],
        how="left",
    )

    completed["is_zero_filled"] = completed["total_year"].isna()
    completed["total_year"] = completed["total_year"].fillna(0.0).astype(float)

    return completed.sort_values(["state", "sex", "year"]).reset_index(drop=True)


def build_state_summary(year_totals: pd.DataFrame) -> pd.DataFrame:
    """Create a state summary table using the completed annual series."""

    state_sex_totals = (
        year_totals.groupby(["state", "sex_label"], as_index=False)["total_year"]
        .sum()
    )

    summary = (
        state_sex_totals.pivot(index="state", columns="sex_label", values="total_year")
        .fillna(0.0)
        .assign(Total=lambda frame: frame.sum(axis=1))
        .sort_values("Total", ascending=False)
    )

    summary["Percentual feminino"] = (summary.get("Feminino", 0.0) / summary["Total"] * 100).round(1)
    return summary


def build_descriptive_stats(year_totals: pd.DataFrame) -> pd.DataFrame:
    """Create descriptive statistics by state and sex using the completed series."""

    descriptive_stats = (
        year_totals.groupby(["state", "sex_label"], as_index=False)
        .agg(
            years_in_series=("year", "nunique"),
            non_zero_years=("total_year", lambda series: int((series > 0).sum())),
            total_cases=("total_year", "sum"),
            mean_cases=("total_year", "mean"),
            median_cases=("total_year", "median"),
            min_cases=("total_year", "min"),
            max_cases=("total_year", "max"),
            std_cases=("total_year", "std"),
        )
        .sort_values(["total_cases", "state"], ascending=[False, True])
        .reset_index(drop=True)
    )

    descriptive_stats["std_cases"] = descriptive_stats["std_cases"].fillna(0.0)
    return descriptive_stats


def build_overall_by_year(year_totals: pd.DataFrame) -> pd.DataFrame:
    """Aggregate completed annual totals by year and sex."""

    return (
        year_totals.groupby(["year", "sex_label"], as_index=False)["total_year"]
        .sum()
        .sort_values(["year", "sex_label"])
        .reset_index(drop=True)
    )


def build_state_year(year_totals: pd.DataFrame) -> pd.DataFrame:
    """Aggregate completed annual totals by state and year."""

    return (
        year_totals.groupby(["state", "year"], as_index=False)["total_year"]
        .sum()
        .sort_values(["state", "year"])
        .reset_index(drop=True)
    )


def build_toxic_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize toxic groups by sex."""

    profile = (
        df.groupby(["sex_label", "toxic_group"], as_index=False)["count"]
        .sum()
        .sort_values(["sex_label", "count"], ascending=[True, False])
        .reset_index(drop=True)
    )

    profile["share_within_sex"] = (
        profile["count"] / profile.groupby("sex_label")["count"].transform("sum")
    )
    return profile


def build_top_groups_by_state(df: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """Return the leading toxic groups by state and sex."""

    grouped = (
        df.groupby(["state", "sex_label", "toxic_group"], as_index=False)["count"]
        .sum()
        .sort_values(["state", "sex_label", "count"], ascending=[True, True, False])
    )

    grouped["share_within_state_sex"] = (
        grouped["count"] / grouped.groupby(["state", "sex_label"])["count"].transform("sum")
    )

    top_groups = grouped.groupby(["state", "sex_label"]).head(top_n).copy()
    top_groups["share_within_state_sex"] = (top_groups["share_within_state_sex"] * 100).round(1)

    return top_groups.reset_index(drop=True)


def save_overall_analysis_charts(
    overall_by_year: pd.DataFrame,
    state_year: pd.DataFrame,
    output_dir: Path,
    sex_palette: dict[str, str] | None = None,
    sex_hue_order: list[str] | None = None,
    dpi: int = 180,
) -> dict[str, Path]:
    """Save the overall line chart, heatmap, and combined overview panel."""

    import matplotlib.pyplot as plt
    import seaborn as sns

    output_dir.mkdir(parents=True, exist_ok=True)

    palette = sex_palette or DEFAULT_SEX_PALETTE
    hue_order = sex_hue_order or ["Masculino", "Feminino"]
    saved_paths: dict[str, Path] = {}

    line_fig, line_ax = plt.subplots(figsize=(11, 6))
    sns.lineplot(
        data=overall_by_year,
        x="year",
        y="total_year",
        hue="sex_label",
        hue_order=hue_order,
        marker="o",
        palette=palette,
        ax=line_ax,
    )
    line_ax.set_title("Notificações anuais por sexo")
    line_ax.set_xlabel("Ano")
    line_ax.set_ylabel("Notificações")
    line_ax.legend(title="Sexo")
    line_fig.tight_layout()

    line_path = output_dir / "notificacoes_anuais_por_sexo.png"
    line_fig.savefig(line_path, dpi=dpi, bbox_inches="tight")
    plt.close(line_fig)
    saved_paths["line_chart"] = line_path

    heatmap_data = (
        state_year.assign(state=lambda frame: frame["state"].map(_display_state_name))
        .pivot(index="state", columns="year", values="total_year")
        .fillna(0.0)
    )
    heatmap_norm = (heatmap_data.T / heatmap_data.max(axis=1)).T.fillna(0.0)

    heatmap_fig, heatmap_ax = plt.subplots(figsize=(11, 6))
    sns.heatmap(heatmap_norm, cmap="YlOrRd", linewidths=0.3, ax=heatmap_ax)
    heatmap_ax.set_title("Intensidade anual por estado")
    heatmap_ax.set_xlabel("Ano")
    heatmap_ax.set_ylabel("Estado")
    heatmap_fig.tight_layout()

    heatmap_path = output_dir / "intensidade_anual_por_estado.png"
    heatmap_fig.savefig(heatmap_path, dpi=dpi, bbox_inches="tight")
    plt.close(heatmap_fig)
    saved_paths["heatmap_chart"] = heatmap_path

    overview_fig, overview_axes = plt.subplots(1, 2, figsize=(18, 6))
    sns.lineplot(
        data=overall_by_year,
        x="year",
        y="total_year",
        hue="sex_label",
        hue_order=hue_order,
        marker="o",
        palette=palette,
        ax=overview_axes[0],
    )
    overview_axes[0].set_title("Notificações anuais por sexo")
    overview_axes[0].set_xlabel("Ano")
    overview_axes[0].set_ylabel("Notificações")
    overview_axes[0].legend(title="Sexo")

    sns.heatmap(heatmap_norm, cmap="YlOrRd", linewidths=0.3, ax=overview_axes[1])
    overview_axes[1].set_title("Intensidade anual por estado")
    overview_axes[1].set_xlabel("Ano")
    overview_axes[1].set_ylabel("Estado")

    overview_fig.tight_layout()

    overview_path = output_dir / "painel_visao_geral.png"
    overview_fig.savefig(overview_path, dpi=dpi, bbox_inches="tight")
    plt.close(overview_fig)
    saved_paths["overview_panel"] = overview_path

    return saved_paths


def save_top_toxic_chart(
    top_toxic: pd.DataFrame,
    output_dir: Path,
    sex_palette: dict[str, str] | None = None,
    sex_hue_order: list[str] | None = None,
    dpi: int = 180,
) -> Path:
    """Save the top toxic groups bar chart."""

    import matplotlib.pyplot as plt
    import seaborn as sns

    output_dir.mkdir(parents=True, exist_ok=True)

    palette = sex_palette or DEFAULT_SEX_PALETTE
    hue_order = sex_hue_order or ["Masculino", "Feminino"]

    fig, ax = plt.subplots(figsize=(12, 7))
    sns.barplot(
        data=top_toxic,
        x="count",
        y="toxic_group",
        hue="sex_label",
        hue_order=hue_order,
        palette=palette,
        ax=ax,
    )
    ax.set_title("Principais grupos tóxicos por sexo")
    ax.set_xlabel("Notificações acumuladas")
    ax.set_ylabel("Grupo do agente tóxico")
    fig.tight_layout()

    output_path = output_dir / "principais_grupos_toxicos_por_sexo.png"
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    return output_path


def build_state_case_totals(year_totals: pd.DataFrame) -> pd.DataFrame:
    """Aggregate total cases by state, with and without sex stratification."""

    total = (
        year_totals.groupby("state", as_index=False)["total_year"]
        .sum()
        .assign(chart_group="Total")
    )

    by_sex = (
        year_totals.groupby(["sex_label", "state"], as_index=False)["total_year"]
        .sum()
        .rename(columns={"sex_label": "chart_group"})
    )

    combined = pd.concat([total, by_sex], ignore_index=True)
    return combined.sort_values(["chart_group", "total_year", "state"], ascending=[True, False, True]).reset_index(
        drop=True
    )


def save_state_sex_timeseries_charts(
    year_totals: pd.DataFrame,
    output_dir: Path,
    start_year: int = DEFAULT_START_YEAR,
    end_year: int = DEFAULT_END_YEAR,
    dpi: int = 180,
) -> list[Path]:
    """Save one large horizontal annual chart per state and return the file paths."""

    import matplotlib.pyplot as plt
    import seaborn as sns

    output_dir.mkdir(parents=True, exist_ok=True)

    state_info = (
        year_totals[["state", "state_code"]]
        .drop_duplicates()
        .sort_values("state")
        .reset_index(drop=True)
    )
    years = list(range(start_year, end_year + 1))
    palette = DEFAULT_SEX_PALETTE
    saved_paths: list[Path] = []

    for row in state_info.itertuples(index=False):
        state_frame = (
            year_totals.loc[year_totals["state"] == row.state]
            .sort_values(["sex_label", "year"])
            .copy()
        )

        fig, ax = plt.subplots(figsize=(16, 5.5))
        sns.lineplot(
            data=state_frame,
            x="year",
            y="total_year",
            hue="sex_label",
            hue_order=["Masculino", "Feminino"],
            marker="o",
            linewidth=2.5,
            markersize=8,
            palette=palette,
            ax=ax,
        )

        ax.set_title(f"{_display_state_name(row.state)} - trajetória anual por sexo")
        ax.set_xlabel("Ano")
        ax.set_ylabel("Notificações")
        ax.set_xlim(start_year, end_year)
        ax.set_xticks(years)
        ax.tick_params(axis="x", rotation=45)
        ax.legend(title="Sexo", loc="upper left", ncol=2)
        ax.grid(True, alpha=0.3)

        fig.tight_layout()

        filename = f"trajetoria_anual_{row.state_code.lower()}_{_slugify_text(row.state)}.png"
        output_path = output_dir / filename
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)

        saved_paths.append(output_path)

    return saved_paths


def save_state_share_pie_charts(
    year_totals: pd.DataFrame,
    output_dir: Path,
    dpi: int = 180,
) -> dict[str, Path]:
    """Save one pie chart for total cases and one for each sex."""

    import matplotlib.pyplot as plt
    import seaborn as sns

    output_dir.mkdir(parents=True, exist_ok=True)

    state_case_totals = build_state_case_totals(year_totals)
    overall_order = (
        state_case_totals.loc[state_case_totals["chart_group"] == "Total"]
        .sort_values("total_year", ascending=False)["state"]
        .tolist()
    )
    state_palette = dict(zip(overall_order, sns.color_palette("muted", n_colors=len(overall_order)).as_hex()))

    chart_specs = [
        ("Total", "distribuicao_estados_total.png", "Distribuição total de casos por estado"),
        ("Feminino", "distribuicao_estados_feminino.png", "Distribuição de casos femininos por estado"),
        ("Masculino", "distribuicao_estados_masculino.png", "Distribuição de casos masculinos por estado"),
    ]
    saved_paths: dict[str, Path] = {}

    for chart_group, filename, title in chart_specs:
        chart_frame = (
            state_case_totals.loc[state_case_totals["chart_group"] == chart_group, ["state", "total_year"]]
            .sort_values("total_year", ascending=False)
            .reset_index(drop=True)
        )

        values = chart_frame["total_year"].tolist()
        raw_labels = chart_frame["state"].tolist()
        labels = [_display_state_name(state) for state in raw_labels]
        colors = [state_palette[state] for state in raw_labels]
        total = sum(values)

        def _format_pct(pct: float) -> str:
            absolute = pct / 100 * total
            return f"{pct:.1f}%\n({absolute:,.0f})"

        fig, ax = plt.subplots(figsize=(10, 10))
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            colors=colors,
            autopct=_format_pct,
            startangle=90,
            counterclock=False,
            wedgeprops={"edgecolor": "white", "linewidth": 1.2},
            textprops={"fontsize": 11},
            pctdistance=0.72,
            labeldistance=1.05,
        )

        for autotext in autotexts:
            autotext.set_fontsize(10)
            autotext.set_color("#2F2F2F")

        ax.set_title(title)
        ax.axis("equal")
        fig.tight_layout()

        output_path = output_dir / filename
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)

        saved_paths[chart_group] = output_path

    return saved_paths


def build_dashboard_payload(
    df: pd.DataFrame,
    coverage: pd.DataFrame,
    year_totals: pd.DataFrame,
    state_summary: pd.DataFrame,
    descriptive_stats: pd.DataFrame,
    overall_by_year: pd.DataFrame,
    state_year: pd.DataFrame,
    state_case_totals: pd.DataFrame,
    toxic_profile: pd.DataFrame,
    top_groups_by_state: pd.DataFrame,
    insight_lines: list[str],
    start_year: int = DEFAULT_START_YEAR,
    end_year: int = DEFAULT_END_YEAR,
) -> dict[str, object]:
    """Build a JSON-serializable payload for the dashboard frontend."""

    total_cases = float(year_totals["total_year"].sum())
    latest_year = int(year_totals["year"].max())
    latest_total = float(year_totals.loc[year_totals["year"] == latest_year, "total_year"].sum())
    total_by_sex = year_totals.groupby("sex_label", as_index=False)["total_year"].sum()
    sex_totals = {row["sex_label"]: float(row["total_year"]) for row in total_by_sex.to_dict("records")}

    dominant_state = state_summary.index[0]
    dominant_state_total = float(state_summary.iloc[0]["Total"])
    zero_filled_pairs = int((coverage["filled_zero_years"] > 0).sum())

    return {
        "metadata": {
            "title": "Dashboard de intoxicação exógena em idosos",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "start_year": start_year,
            "end_year": end_year,
            "states": sorted(year_totals["state"].unique().tolist()),
            "sexes": ["Masculino", "Feminino"],
            "years": list(range(start_year, end_year + 1)),
        },
        "summary": {
            "total_cases": total_cases,
            "latest_year": latest_year,
            "latest_total": latest_total,
            "female_share": float(sex_totals.get("Feminino", 0.0) / total_cases * 100) if total_cases else 0.0,
            "male_share": float(sex_totals.get("Masculino", 0.0) / total_cases * 100) if total_cases else 0.0,
            "dominant_state": dominant_state,
            "dominant_state_total": dominant_state_total,
            "zero_filled_pairs": zero_filled_pairs,
        },
        "tables": {
            "coverage": coverage.to_dict("records"),
            "year_totals": year_totals.to_dict("records"),
            "state_summary": state_summary.reset_index().rename_axis(columns=None).to_dict("records"),
            "descriptive_stats": descriptive_stats.to_dict("records"),
            "overall_by_year": overall_by_year.to_dict("records"),
            "state_year": state_year.to_dict("records"),
            "state_case_totals": state_case_totals.to_dict("records"),
            "toxic_profile": toxic_profile.to_dict("records"),
            "top_groups_by_state": top_groups_by_state.to_dict("records"),
            "tidy_counts": df.to_dict("records"),
        },
        "insights": insight_lines,
    }


def write_json_report(output_path: Path, payload: dict[str, object]) -> Path:
    """Write a JSON report to disk and return the written path."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def copy_plotly_bundle(output_path: Path) -> Path:
    """Copy the local Plotly JavaScript bundle to the frontend assets directory."""

    import plotly

    source_path = Path(plotly.__file__).resolve().parent / "package_data" / "plotly.min.js"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    copyfile(source_path, output_path)
    return output_path


def build_insight_lines(
    year_totals: pd.DataFrame,
    state_summary: pd.DataFrame,
    toxic_profile: pd.DataFrame,
    coverage: pd.DataFrame,
    start_year: int = DEFAULT_START_YEAR,
    end_year: int = DEFAULT_END_YEAR,
) -> list[str]:
    """Build a compact list of human-readable insights."""

    overall_total = int(year_totals["total_year"].sum())
    sex_totals = year_totals.groupby("sex_label", as_index=False)["total_year"].sum()
    sex_totals_map = sex_totals.set_index("sex_label")["total_year"]
    female_share = sex_totals_map.get("Feminino", 0.0) / overall_total * 100

    top_state = state_summary.index[0]
    top_state_total = int(state_summary.iloc[0]["Total"])
    top_state_share = top_state_total / overall_total * 100

    overall_by_year = build_overall_by_year(year_totals)
    latest_year = int(overall_by_year["year"].max())
    latest_totals = (
        overall_by_year.loc[overall_by_year["year"] == latest_year]
        .set_index("sex_label")["total_year"]
    )

    medication_share = (
        toxic_profile.loc[toxic_profile["toxic_group"] == "Medicamento"]
        .set_index("sex_label")["share_within_sex"]
        .mul(100)
    )

    zero_filled = coverage.loc[coverage["filled_zero_years"] > 0].copy()
    zero_fill_detail = "; ".join(
        f"{row.state_code}/{row.sex_label}: {int(row.filled_zero_years)} anos"
        for row in zero_filled.itertuples(index=False)
    )

    ufs = ", ".join(sorted(_display_state_name(state) for state in year_totals["state"].unique()))
    lines = [
        f"A análise considera somente o intervalo {start_year}-{end_year}; registros fora dessa janela, como 1991, foram descartados.",
        f"A base consolidada cobre {year_totals['state'].nunique()} UFs ({ufs}) e soma {overall_total:,} notificações no período.",
        f"Mulheres concentram {female_share:.1f}% das notificações, considerando a série anual completada com zeros quando necessário.",
        f"{_display_state_name(top_state)} responde por {top_state_share:.1f}% do total observado ({top_state_total:,} notificações somando os dois sexos).",
        (
            f"O último ano da série, {latest_year}, registra "
            f"{int(latest_totals.get('Feminino', 0)):,} notificações femininas e "
            f"{int(latest_totals.get('Masculino', 0)):,} masculinas."
        ),
        (
            f"Medicamento lidera em ambos os sexos: "
            f"{medication_share.get('Feminino', 0):.1f}% entre mulheres e "
            f"{medication_share.get('Masculino', 0):.1f}% entre homens."
        ),
    ]

    if zero_fill_detail:
        lines.append(
            f"Anos ausentes foram preenchidos com zero para manter a série completa de {start_year} a {end_year}: {zero_fill_detail}."
        )

    return lines


def format_insights_markdown(lines: list[str], title: str) -> str:
    """Format insight lines as a markdown report."""

    bullet_lines = "\n".join(f"- {line}" for line in lines)
    return f"# {title}\n\n{bullet_lines}\n"


def write_text_report(output_path: Path, content: str) -> Path:
    """Write a text report to disk and return the written path."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


__all__ = [
    "DEFAULT_END_YEAR",
    "DEFAULT_SEX_PALETTE",
    "DEFAULT_START_YEAR",
    "build_dashboard_payload",
    "build_descriptive_stats",
    "build_insight_lines",
    "build_overall_by_year",
    "build_state_case_totals",
    "build_state_summary",
    "build_state_year",
    "build_top_groups_by_state",
    "build_toxic_profile",
    "build_year_totals",
    "copy_plotly_bundle",
    "filter_year_window",
    "format_insights_markdown",
    "load_intoxicacao_tidy",
    "save_overall_analysis_charts",
    "save_state_share_pie_charts",
    "save_state_sex_timeseries_charts",
    "save_top_toxic_chart",
    "summarize_year_coverage",
    "write_json_report",
    "write_text_report",
]
