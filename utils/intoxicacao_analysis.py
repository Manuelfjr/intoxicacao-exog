"""Utilities for the initial analysis of exogenous intoxication data."""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
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
    palette = {"Feminino": "#4C72B0", "Masculino": "#DD8452"}
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
            marker="o",
            linewidth=2.5,
            markersize=8,
            palette=palette,
            ax=ax,
        )

        ax.set_title(f"{row.state} - trajetoria anual por sexo")
        ax.set_xlabel("Ano")
        ax.set_ylabel("Notificacoes")
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

    ufs = ", ".join(sorted(year_totals["state"].unique()))
    lines = [
        f"A analise considera somente o intervalo {start_year}-{end_year}; registros fora dessa janela, como 1991, foram descartados.",
        f"A base consolidada cobre {year_totals['state'].nunique()} UFs ({ufs}) e soma {overall_total:,} notificacoes no periodo.",
        f"Mulheres concentram {female_share:.1f}% das notificacoes, considerando a serie anual completada com zeros quando necessario.",
        f"{top_state} responde por {top_state_share:.1f}% do total observado ({top_state_total:,} notificacoes somando os dois sexos).",
        (
            f"O ultimo ano da serie, {latest_year}, registra "
            f"{int(latest_totals.get('Feminino', 0)):,} notificacoes femininas e "
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
            f"Anos ausentes foram preenchidos com zero para manter a serie completa de {start_year} a {end_year}: {zero_fill_detail}."
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
