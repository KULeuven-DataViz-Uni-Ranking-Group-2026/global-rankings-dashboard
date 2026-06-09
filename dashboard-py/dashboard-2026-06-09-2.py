"""
dashboard-2026-06-09.py
=======================

Prestige vs. Performance — Focused University Rankings Dashboard

Final narrative:
1. Macro Shift       — Asia is gaining Top-200 market share
2. THE vs QS         — Ranking choice affects universities differently by region
3. Elite Stability   — The very top is structurally locked
4. Ranking Mechanics — THE mainly rewards research capacity
5. GDP Outliers      — Wealth matters, but China outperforms its GDP level
6. Domain Strategy   — Only Asia shows a clear Engineering advantage over Arts & Humanities

Usage
-----
    python3 dashboard-2026-06-09.py

Output
------
    index.html

Required local files
--------------------
    the_rankings.csv
    qs_rankings.csv

Optional local files
--------------------
    the_subjects_2026.csv
    the_subjects.csv
    gdp_per_capita.csv

If gdp_per_capita.csv is not found, GDP data is fetched from the World Bank API.
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
import plotly.graph_objects as go

warnings.filterwarnings("ignore")


# =============================================================================
# Constants
# =============================================================================

OUTPUT_FILE = "index.html"

FONT = "Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"

REGION_ORDER = [
    "Anglosphere",
    "Asia",
    "Europe",
    "Rest of World",
]

REGION_COLORS = {
    "Anglosphere": "#0072B2",
    "Asia": "#D55E00",
    "Europe": "#009E73",
    "Rest of World": "#CC79A7",
}

ANGLOSPHERE = {
    "United States",
    "United Kingdom",
    "Australia",
    "Canada",
    "New Zealand",
    "Ireland",
}

ASIA_MAJOR = {
    "China",
    "Japan",
    "South Korea",
    "Singapore",
    "Hong Kong",
    "Taiwan",
    "Macao",
}

EUROPE_MAJOR = {
    "Germany",
    "France",
    "Netherlands",
    "Belgium",
    "Sweden",
    "Spain",
    "Italy",
    "Switzerland",
    "Denmark",
    "Finland",
    "Norway",
    "Austria",
    "Portugal",
    "Luxembourg",
}

COUNTRY_ALIASES = {
    "United States of America": "United States",
    "USA": "United States",
    "US": "United States",
    "U.S.": "United States",
    "U.S.A.": "United States",
    "UK": "United Kingdom",
    "United Kingdom of Great Britain and Northern Ireland": "United Kingdom",
    "Korea, Rep.": "South Korea",
    "Republic of Korea": "South Korea",
    "Korea, South": "South Korea",
    "Hong Kong SAR, China": "Hong Kong",
    "Hong Kong SAR China": "Hong Kong",
    "Hong Kong, China": "Hong Kong",
    "Macao SAR, China": "Macao",
    "Macau": "Macao",
    "Russian Federation": "Russia",
    "Viet Nam": "Vietnam",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
    "Egypt, Arab Rep.": "Egypt",
    "Iran, Islamic Rep.": "Iran",
}

PLOTLY_CONFIG = {
    "responsive": True,
    "displayModeBar": False,
    "displaylogo": False,
}

BASE_LAYOUT = dict(
    font=dict(family=FONT, color="#111827"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(255,255,255,0.98)",
    margin=dict(l=70, r=40, t=90, b=90),
    hoverlabel=dict(
        align="left",
        bgcolor="white",
        bordercolor="#d0d5dd",
        font=dict(color="#111827"),
    ),
)


# =============================================================================
# General helpers
# =============================================================================

def read_csv_auto(path: str | Path) -> pd.DataFrame:
    """
    Automatically read comma- or semicolon-separated CSV.
    Useful because QS/THE are usually comma-separated, while subject data may be semicolon-separated.
    """
    return pd.read_csv(
        path,
        sep=None,
        engine="python",
        encoding="utf-8-sig",
    )


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise column names."""
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[^\w]+", "_", regex=True)
        .str.strip("_")
    )
    return df


def first_existing(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """Return first candidate column that exists in the dataframe."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def first_column_containing(df: pd.DataFrame, tokens: list[str]) -> Optional[str]:
    """Return first column containing all requested tokens."""
    for c in df.columns:
        if all(t in c for t in tokens):
            return c
    return None


def parse_rank(value) -> float:
    """
    Parse ranking values:
    - "1" -> 1
    - "=12" -> 12
    - "7=" -> 7
    - "201-250" -> 225
    - "1001+" -> 1001
    """
    if pd.isna(value):
        return np.nan

    s = str(value).strip()

    if not s:
        return np.nan

    s = (
        s.replace(",", "")
        .replace("=", "")
        .replace("#", "")
        .replace("+", "")
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
    )

    nums = re.findall(r"\d+(?:\.\d+)?", s)

    if not nums:
        return np.nan

    if "-" in s and len(nums) >= 2:
        return (float(nums[0]) + float(nums[1])) / 2

    return float(nums[0])


def parse_numeric(value) -> float:
    """
    Parse numeric values safely.

    Handles:
    - "98.4"    -> 98.4
    - "91,3"    -> 91.3
    - "11,703"  -> 11703
    - "23%"     -> 23
    - "50-60"   -> 55
    """
    if pd.isna(value):
        return np.nan

    raw = str(value).strip()

    if not raw:
        return np.nan

    raw = raw.replace("%", "")
    raw = raw.replace("–", "-").replace("—", "-").replace("−", "-")

    # Simple numeric ranges.
    if re.search(r"\d+\s*-\s*\d+", raw):
        parts = re.split(r"\s*-\s*", raw)
        vals = [parse_numeric(p) for p in parts[:2]]
        vals = [v for v in vals if not pd.isna(v)]
        if len(vals) == 2:
            return sum(vals) / 2

    s = raw.replace(" ", "")

    # Both comma and dot: assume comma is thousands separator.
    if "," in s and "." in s:
        s = s.replace(",", "")

    # Comma only.
    elif "," in s:
        parts = s.split(",")

        # Decimal comma: "91,3" or "91,35"
        if len(parts) == 2 and len(parts[1]) in [1, 2]:
            s = parts[0] + "." + parts[1]

        # Thousands comma: "11,703" or "1,234,567"
        elif len(parts) >= 2 and all(len(p) == 3 for p in parts[1:]):
            s = "".join(parts)

        # Fallback: decimal comma.
        else:
            s = s.replace(",", ".")

    match = re.search(r"-?\d+(?:\.\d+)?", s)

    if not match:
        return np.nan

    return float(match.group(0))


def normalize_country(country) -> str:
    """Normalise country names for matching and region assignment."""
    if pd.isna(country):
        return "Unknown"

    c = str(country).strip()
    c = re.sub(r"\s+", " ", c)

    return COUNTRY_ALIASES.get(c, c)


def assign_region(country) -> str:
    """Assign countries to simplified geopolitical regions."""
    c = normalize_country(country)

    if c in ANGLOSPHERE:
        return "Anglosphere"
    if c in ASIA_MAJOR:
        return "Asia"
    if c in EUROPE_MAJOR:
        return "Europe"

    return "Rest of World"


def normalize_institution_name(name) -> str:
    """Create institution matching key."""
    if pd.isna(name):
        return ""

    s = str(name).lower().strip()
    s = s.replace("&", "and")
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    return s


def short_label(text: str, max_len: int = 34) -> str:
    """Shorten long university names."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def format_pp(value: float) -> str:
    """Format percentage-point change."""
    if pd.isna(value):
        return "n/a"
    return f"{value:+.1f} pp"


def _chart_layout(title: str, height: int = 620, **kwargs) -> dict:
    """Shared Plotly layout."""
    layout = dict(BASE_LAYOUT)
    layout.update(
        dict(
            title=dict(
                text=title,
                x=0.02,
                xanchor="left",
                font=dict(size=21, color="#111827"),
            ),
            height=height,
        )
    )
    layout.update(kwargs)
    return layout


def _placeholder_fig(message: str, title: str = "Data unavailable") -> go.Figure:
    """Placeholder chart if data is missing."""
    fig = go.Figure()
    fig.update_layout(
        **_chart_layout(title, height=520),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text=message,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                align="center",
                font=dict(size=17, color="#667085"),
            )
        ],
    )
    return fig


# =============================================================================
# Data loading
# =============================================================================

def load_the(path: str = "the_rankings.csv") -> pd.DataFrame:
    """Load and clean THE ranking data."""
    if not Path(path).exists():
        raise FileNotFoundError(f"Missing THE file: {path}")

    print(f"Loading THE data from: {path}")

    df = read_csv_auto(path)
    df = clean_columns(df)

    name_col = first_existing(
        df,
        ["name", "university_name", "institution", "institution_name", "display_name"],
    )
    if name_col and name_col != "name":
        df = df.rename(columns={name_col: "name"})

    if "name" not in df.columns:
        raise ValueError(f"THE file must contain institution name. Columns: {list(df.columns)}")

    country_col = first_existing(df, ["country", "location", "country_name"])
    if country_col and country_col != "country":
        df = df.rename(columns={country_col: "country"})

    if "country" not in df.columns:
        df["country"] = "Unknown"

    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").fillna(2026).astype(int)
    else:
        df["year"] = 2026

    rank_col = first_existing(
        df,
        ["rank_order", "rank", "world_rank", "ranking", "rank_display"],
    )

    if rank_col is None:
        raise ValueError(f"THE file must contain rank column. Columns: {list(df.columns)}")

    df["rank_order"] = df[rank_col].apply(parse_rank)

    rename_if_missing = {
        "scores_overall": "overall_score",
        "score_overall": "overall_score",
        "overall": "overall_score",
        "scores_teaching": "teaching",
        "teaching_score": "teaching",
        "scores_research": "research_environment",
        "research": "research_environment",
        "research_score": "research_environment",
        "scores_citations": "research_quality",
        "citations": "research_quality",
        "citation_score": "research_quality",
        "scores_industry_income": "industry_impact",
        "industry_income": "industry_impact",
        "industry": "industry_impact",
        "scores_international_outlook": "international_outlook",
        "international": "international_outlook",
    }

    for src, target in rename_if_missing.items():
        if src in df.columns and target not in df.columns:
            df = df.rename(columns={src: target})

    if "overall_score" not in df.columns:
        overall_col = first_column_containing(df, ["overall"])
        if overall_col is not None:
            df["overall_score"] = df[overall_col]

    numeric_cols = [
        "overall_score",
        "teaching",
        "research_environment",
        "research_quality",
        "industry_impact",
        "international_outlook",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(parse_numeric)

    df["country"] = df["country"].apply(normalize_country)
    df["region"] = df["country"].apply(assign_region)

    df = df.dropna(subset=["rank_order"]).reset_index(drop=True)

    print(f"Loaded THE data: {len(df):,} rows")
    print(f"THE rank column used: {rank_col}")

    return df


def load_qs(path: str = "qs_rankings.csv") -> pd.DataFrame:
    """Load and clean QS Rankings 2026."""
    if not Path(path).exists():
        raise FileNotFoundError(f"Missing QS file: {path}")

    print(f"Loading QS data from: {path}")

    df = read_csv_auto(path)
    df = clean_columns(df)

    name_col = first_existing(
        df,
        [
            "name",
            "university_name",
            "institution",
            "institution_name",
            "display_name",
        ],
    )

    if name_col and name_col != "name":
        df = df.rename(columns={name_col: "name"})

    if "name" not in df.columns:
        raise ValueError(
            "QS file must contain institution name column. "
            f"Available columns: {list(df.columns)}"
        )

    country_col = first_existing(
        df,
        [
            "country",
            "country_territory",
            "territory",
            "location",
            "country_name",
        ],
    )

    if country_col and country_col != "country":
        df = df.rename(columns={country_col: "country"})

    if "country" not in df.columns:
        df["country"] = "Unknown"

    rank_col = first_existing(
        df,
        [
            "qs_rank",
            "2026_rank",
            "rank",
            "rank_order",
            "world_rank",
            "ranking",
            "rank_display",
        ],
    )

    if rank_col is None:
        year_rank_cols = [
            c for c in df.columns
            if re.fullmatch(r"\d{4}_rank", c)
        ]
        if year_rank_cols:
            rank_col = sorted(year_rank_cols)[-1]

    if rank_col is None:
        raise ValueError(
            "QS file must contain rank column. "
            f"Available columns after cleaning: {list(df.columns)}"
        )

    df["qs_rank"] = df[rank_col].apply(parse_rank)

    ar_col = first_existing(
        df,
        [
            "academic_reputation",
            "academic_reputation_score",
            "ar_score",
        ],
    )

    if ar_col is None:
        ar_col = first_column_containing(df, ["academic", "reputation"])

    if ar_col is not None and ar_col != "academic_reputation":
        df = df.rename(columns={ar_col: "academic_reputation"})

    if "academic_reputation" in df.columns:
        df["academic_reputation"] = df["academic_reputation"].apply(parse_numeric)

    er_col = first_existing(
        df,
        [
            "employer_reputation",
            "employer_reputation_score",
            "er_score",
        ],
    )

    if er_col is not None and er_col != "employer_reputation":
        df = df.rename(columns={er_col: "employer_reputation"})

    if "employer_reputation" in df.columns:
        df["employer_reputation"] = df["employer_reputation"].apply(parse_numeric)

    overall_col = first_existing(
        df,
        [
            "overall_score",
            "overall",
            "score_overall",
        ],
    )

    if overall_col is not None and overall_col != "overall_score":
        df = df.rename(columns={overall_col: "overall_score"})

    if "overall_score" in df.columns:
        df["overall_score"] = df["overall_score"].apply(parse_numeric)

    df["country"] = df["country"].apply(normalize_country)
    df["region"] = df["country"].apply(assign_region)

    df = df.dropna(subset=["qs_rank"]).reset_index(drop=True)

    print(f"Loaded QS data: {len(df):,} rows")
    print(f"QS rank column used: {rank_col}")

    return df


def fetch_world_bank_gdp_per_capita(
    start_year: int = 2020,
    end_year: int = 2025,
) -> pd.DataFrame:
    """
    Fetch GDP per capita from World Bank API.

    Indicator:
    NY.GDP.PCAP.CD = GDP per capita, current US$
    """
    indicator = "NY.GDP.PCAP.CD"

    url = (
        "https://api.worldbank.org/v2/country/all/indicator/"
        f"{indicator}"
        f"?format=json&per_page=20000&date={start_year}:{end_year}"
    )

    print("Fetching GDP per capita from World Bank API...")

    request = Request(
        url,
        headers={"User-Agent": "KU-Leuven-DataViz-Dashboard/1.0"},
    )

    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, list) or len(payload) < 2:
        raise RuntimeError("Unexpected World Bank API response.")

    records = payload[1]
    rows = []

    for item in records:
        value = item.get("value")

        if value is None:
            continue

        country_info = item.get("country", {})
        country_name = country_info.get("value")

        if not country_name:
            continue

        rows.append(
            {
                "country": normalize_country(country_name),
                "year": int(item.get("date")),
                "gdp_per_capita": float(value),
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(columns=["country", "year", "gdp_per_capita"])

    df = (
        df.sort_values("year")
        .groupby("country")
        .last()
        .reset_index()
    )

    print(f"Loaded GDP data from World Bank API: {len(df):,} countries")

    return df


def load_gdp(path: str | None = "gdp_per_capita.csv") -> pd.DataFrame:
    """
    Load GDP per capita.

    If gdp_per_capita.csv exists, use it.
    Otherwise fetch from World Bank API.
    """
    if path is not None and Path(path).exists():
        print(f"Loading GDP data from local file: {path}")

        df = read_csv_auto(path)
        df = clean_columns(df)

        country_col = first_existing(
            df,
            ["country", "country_name", "economy"],
        )

        if country_col and country_col != "country":
            df = df.rename(columns={country_col: "country"})

        if "country" not in df.columns:
            raise ValueError("GDP file must contain country column.")

        gdp_col = first_existing(
            df,
            ["gdp_per_capita", "gdp_pc", "ny_gdp_pcap_cd"],
        )

        if gdp_col is None:
            gdp_col = first_column_containing(df, ["gdp", "capita"])

        if gdp_col is None:
            raise ValueError("GDP file must contain GDP per capita column.")

        if gdp_col != "gdp_per_capita":
            df = df.rename(columns={gdp_col: "gdp_per_capita"})

        if "year" in df.columns:
            df["year"] = pd.to_numeric(df["year"], errors="coerce")

        df["country"] = df["country"].apply(normalize_country)
        df["gdp_per_capita"] = df["gdp_per_capita"].apply(parse_numeric)

        return df

    try:
        return fetch_world_bank_gdp_per_capita()

    except Exception as e:
        print("Warning: World Bank API failed.")
        print(f"Reason: {e}")
        print("GDP chart will show a placeholder.")

        return pd.DataFrame(columns=["country", "year", "gdp_per_capita"])


def load_subjects(path: str | None = "the_subjects.csv") -> Optional[pd.DataFrame]:
    """Load THE Subject Rankings data."""
    candidate_paths = []

    if path is not None:
        candidate_paths.append(Path(path))

    candidate_paths.extend(
        [
            Path("the_subjects_2026.csv"),
            Path("the_subjects.csv"),
        ]
    )

    selected_path = None

    for p in candidate_paths:
        if p.exists():
            selected_path = p
            break

    if selected_path is None:
        print(
            "Warning: no subject file found. "
            "Expected the_subjects.csv or the_subjects_2026.csv."
        )
        return None

    print(f"Loading subject data from: {selected_path}")

    df = read_csv_auto(selected_path)
    df = clean_columns(df)

    name_col = first_existing(
        df,
        [
            "name",
            "university_name",
            "institution",
            "institution_name",
            "display_name",
        ],
    )

    if name_col and name_col != "name":
        df = df.rename(columns={name_col: "name"})

    if "name" not in df.columns:
        df["name"] = "Unknown institution"

    country_col = first_existing(
        df,
        [
            "country",
            "location",
            "country_name",
            "country_territory",
        ],
    )

    if country_col and country_col != "country":
        df = df.rename(columns={country_col: "country"})

    if "country" not in df.columns:
        df["country"] = "Unknown"

    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    df["country"] = df["country"].apply(normalize_country)

    print(f"Loaded subject data: {len(df):,} rows")

    return df


# =============================================================================
# Data preparation
# =============================================================================

def build_merged(the_df: pd.DataFrame, qs_df: pd.DataFrame) -> pd.DataFrame:
    """
    Match latest THE year with QS using normalised institution names.
    Adds raw rank_diff, but the chart uses percentile disagreement.
    """
    if the_df.empty or qs_df.empty:
        return pd.DataFrame()

    latest_year = int(the_df["year"].max())
    the_latest = the_df[the_df["year"] == latest_year].copy()
    qs = qs_df.copy()

    the_latest["merge_key"] = the_latest["name"].apply(normalize_institution_name)
    qs["merge_key"] = qs["name"].apply(normalize_institution_name)

    the_latest = (
        the_latest.sort_values("rank_order")
        .drop_duplicates("merge_key", keep="first")
    )

    qs = (
        qs.sort_values("qs_rank")
        .drop_duplicates("merge_key", keep="first")
    )

    qs_cols = ["merge_key", "name", "country", "qs_rank"]

    if "academic_reputation" in qs.columns:
        qs_cols.append("academic_reputation")

    qs_small = qs[qs_cols].rename(
        columns={
            "name": "qs_name",
            "country": "country_qs",
        }
    )

    merged = the_latest.merge(qs_small, on="merge_key", how="inner")

    if merged.empty:
        print("Warning: no THE-QS institutions matched.")
        return merged

    merged["rank_diff"] = (merged["rank_order"] - merged["qs_rank"]).abs()

    print(f"Matched THE-QS institutions: {len(merged):,}")

    return merged


def compute_top200_share(the_df: pd.DataFrame) -> pd.DataFrame:
    """Compute regional share of THE Top 200 by year."""
    if the_df.empty:
        return pd.DataFrame()

    top200 = the_df[the_df["rank_order"] <= 200].copy()

    if top200.empty:
        return pd.DataFrame()

    counts = (
        top200.groupby(["year", "region"])
        .size()
        .reset_index(name="count")
    )

    counts["total"] = counts.groupby("year")["count"].transform("sum")
    counts["share"] = counts["count"] / counts["total"] * 100

    pivot = (
        counts.pivot(index="year", columns="region", values="share")
        .fillna(0)
        .sort_index()
    )

    for region in REGION_ORDER:
        if region not in pivot.columns:
            pivot[region] = 0.0

    return pivot[REGION_ORDER]


def compute_share_delta(share_df: pd.DataFrame, region: str) -> float:
    """Compute first-to-last change in Top-200 share."""
    if share_df.empty or region not in share_df.columns:
        return np.nan

    s = share_df[region].dropna()

    if len(s) < 2:
        return np.nan

    return float(s.iloc[-1] - s.iloc[0])


def build_gdp_country_frame(the_df: pd.DataFrame, gdp_df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per country:
    - median THE rank
    - number of ranked universities
    - latest GDP per capita
    """
    if the_df.empty or gdp_df.empty:
        return pd.DataFrame()

    latest_year = int(the_df["year"].max())
    the_latest = the_df[the_df["year"] == latest_year].copy()

    country_stats = (
        the_latest.groupby("country")
        .agg(
            median_rank=("rank_order", "median"),
            ranked_universities=("name", "nunique"),
        )
        .reset_index()
    )

    if "year" in gdp_df.columns:
        latest_gdp = (
            gdp_df.dropna(subset=["year"])
            .sort_values("year")
            .groupby("country")
            .last()
            .reset_index()[["country", "gdp_per_capita"]]
        )
    else:
        latest_gdp = gdp_df[["country", "gdp_per_capita"]].copy()

    df = country_stats.merge(latest_gdp, on="country", how="inner")

    df["gdp_per_capita"] = pd.to_numeric(df["gdp_per_capita"], errors="coerce")

    df = df.dropna(subset=["gdp_per_capita", "median_rank"])
    df = df[df["gdp_per_capita"] > 0].copy()

    df["region"] = df["country"].apply(assign_region)

    return df


# =============================================================================
# Chart 1 — Macro Shift
# =============================================================================

def fig_macro_shift(share_df: pd.DataFrame) -> go.Figure:
    """100% stacked area chart of Top-200 market share."""
    if share_df.empty:
        return _placeholder_fig(
            "No Top-200 share data could be calculated.",
            title="Asia is gaining Top-200 market share",
        )

    fig = go.Figure()

    for region in REGION_ORDER:
        fig.add_trace(
            go.Scatter(
                x=share_df.index,
                y=share_df[region],
                mode="lines",
                name=region,
                stackgroup="one",
                line=dict(color=REGION_COLORS[region], width=2),
                hovertemplate=(
                    f"<b>{region}</b><br>"
                    "Year: %{x}<br>"
                    "Top-200 share: %{y:.1f}%"
                    "<extra></extra>"
                ),
            )
        )

    if "Asia" in share_df.columns and len(share_df) >= 2:
        first_year = share_df.index.min()
        last_year = share_df.index.max()
        asia_delta = share_df.loc[last_year, "Asia"] - share_df.loc[first_year, "Asia"]

        cumulative = share_df.loc[last_year].cumsum()
        asia_mid = cumulative["Asia"] - share_df.loc[last_year, "Asia"] / 2

        fig.add_annotation(
            text=f"Asia: {asia_delta:+.1f} percentage points",
            x=last_year,
            y=asia_mid,
            showarrow=True,
            arrowhead=2,
            ax=-90,
            ay=-30,
            bgcolor="rgba(255,255,255,0.88)",
            bordercolor="#d0d5dd",
            font=dict(size=13, color="#111827"),
        )

    fig.update_layout(
        **_chart_layout(
            "Asia is gaining Top-200 market share",
            height=620,
        ),
        xaxis=dict(title="Year", dtick=1),
        yaxis=dict(
            title="Share of THE Top 200 universities",
            range=[0, 100],
            ticksuffix="%",
        ),
        legend=dict(
            title=dict(text="Region"),
            orientation="h",
            yanchor="bottom",
            y=-0.22,
            xanchor="left",
            x=0,
        ),
    )

    return fig


# =============================================================================
# Chart 2 — THE vs QS, improved with percentile disagreement
# =============================================================================

def fig_methodology_divergence(merged: pd.DataFrame) -> go.Figure:
    """
    Boxplot of normalised THE-QS disagreement by region.

    Uses percentile-position difference instead of raw rank difference.
    This avoids exaggerating differences for lower-ranked universities.
    """
    if merged.empty or "rank_order" not in merged.columns or "qs_rank" not in merged.columns:
        return _placeholder_fig(
            "No matched THE-QS data available.",
            title="Ranking choice affects universities differently by region",
        )

    df = merged.copy()
    df = df.dropna(subset=["rank_order", "qs_rank", "region"])

    if df.empty:
        return _placeholder_fig(
            "No valid matched THE-QS ranks available.",
            title="Ranking choice affects universities differently by region",
        )

    df["the_percentile"] = df["rank_order"].rank(
        method="average",
        ascending=True,
        pct=True,
    ) * 100

    df["qs_percentile"] = df["qs_rank"].rank(
        method="average",
        ascending=True,
        pct=True,
    ) * 100

    df["method_gap"] = (df["the_percentile"] - df["qs_percentile"]).abs()

    fig = go.Figure()

    for region in REGION_ORDER:
        sub = df[df["region"] == region].copy()

        if sub.empty:
            continue

        fig.add_trace(
            go.Box(
                x=[region] * len(sub),
                y=sub["method_gap"],
                name=region,
                boxpoints="all",
                jitter=0.35,
                pointpos=0,
                marker=dict(
                    color=REGION_COLORS[region],
                    size=5,
                    opacity=0.45,
                    line=dict(color="white", width=0.5),
                ),
                line=dict(color=REGION_COLORS[region]),
                hovertext=sub["name"],
                customdata=sub[["country", "rank_order", "qs_rank"]].to_numpy(),
                hovertemplate=(
                    "<b>%{hovertext}</b><br>"
                    "Country: %{customdata[0]}<br>"
                    "THE rank: %{customdata[1]:.0f}<br>"
                    "QS rank: %{customdata[2]:.0f}<br>"
                    "Normalised disagreement: %{y:.1f} percentile points"
                    "<extra></extra>"
                ),
                showlegend=False,
            )
        )

    medians = (
        df.groupby("region")["method_gap"]
        .median()
        .reindex(REGION_ORDER)
        .dropna()
    )

    fig.add_trace(
        go.Scatter(
            x=medians.index,
            y=medians.values,
            mode="markers",
            name="Regional median",
            marker=dict(
                symbol="diamond",
                size=15,
                color="#111827",
                line=dict(color="white", width=1.2),
            ),
            hovertemplate="Regional median: %{y:.1f} percentile points<extra></extra>",
        )
    )

    fig.update_layout(
        **_chart_layout(
            "Ranking choice affects universities differently by region",
            height=620,
        ),
        xaxis=dict(
            title="Region",
            categoryorder="array",
            categoryarray=REGION_ORDER,
        ),
        yaxis=dict(
            title="THE-QS disagreement, percentile points",
            rangemode="tozero",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.22,
            xanchor="left",
            x=0,
        ),
    )

    return fig


# =============================================================================
# Chart 3 — Elite Stability
# =============================================================================

def fig_elite_stability(the_df: pd.DataFrame, top_n: int = 12) -> go.Figure:
    """
    Range plot for top universities:
    - horizontal line = full 2016-2026 rank range
    - dots = yearly ranks
    - diamond = median rank
    """
    if the_df.empty:
        return _placeholder_fig(
            "No THE ranking history available.",
            title="The very top is structurally locked",
        )

    latest_year = int(the_df["year"].max())

    elite_names = (
        the_df[the_df["year"] == latest_year]
        .nsmallest(top_n, "rank_order")["name"]
        .dropna()
        .tolist()
    )

    if not elite_names:
        return _placeholder_fig(
            "No elite universities found.",
            title="The very top is structurally locked",
        )

    elite = the_df[the_df["name"].isin(elite_names)].copy()

    stats = (
        elite.groupby("name")
        .agg(
            best_rank=("rank_order", "min"),
            worst_rank=("rank_order", "max"),
            median_rank=("rank_order", "median"),
            n_years=("year", "nunique"),
        )
        .reset_index()
        .sort_values("median_rank", ascending=True)
    )

    stats["label"] = stats["name"].apply(lambda x: short_label(x, 34))
    label_map = dict(zip(stats["name"], stats["label"]))
    elite["label"] = elite["name"].map(label_map)

    fig = go.Figure()

    line_x = []
    line_y = []

    for _, row in stats.iterrows():
        line_x += [row["best_rank"], row["worst_rank"], None]
        line_y += [row["label"], row["label"], None]

    fig.add_trace(
        go.Scatter(
            x=line_x,
            y=line_y,
            mode="lines",
            line=dict(color="#94a3b8", width=7),
            name="Rank range",
            hoverinfo="skip",
            showlegend=True,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=elite["rank_order"],
            y=elite["label"],
            mode="markers",
            name="Yearly rank",
            marker=dict(
                size=7,
                color="#2563eb",
                opacity=0.55,
                line=dict(color="white", width=0.5),
            ),
            customdata=elite[["name", "year"]].to_numpy(),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Year: %{customdata[1]}<br>"
                "Rank: %{x:.0f}"
                "<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=stats["median_rank"],
            y=stats["label"],
            mode="markers",
            name="Median rank",
            marker=dict(
                symbol="diamond",
                size=14,
                color="#111827",
                line=dict(color="white", width=1.2),
            ),
            customdata=stats[["name", "best_rank", "worst_rank", "n_years"]].to_numpy(),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Best rank: %{customdata[1]:.0f}<br>"
                "Worst rank: %{customdata[2]:.0f}<br>"
                "Years observed: %{customdata[3]:.0f}<br>"
                "Median rank: %{x:.1f}"
                "<extra></extra>"
            ),
        )
    )

    fig.add_vline(
        x=5,
        line_dash="dash",
        line_color="#dc2626",
        annotation_text="Top-5 boundary",
        annotation_position="top",
    )

    max_rank = max(15, float(stats["worst_rank"].max()) + 2)

    fig.update_layout(
        **_chart_layout(
            "The very top is structurally locked",
            height=720,
            margin=dict(l=260, r=40, t=90, b=110),
        ),
        xaxis=dict(
            title="THE global rank, 2016-2026 — lower is better",
            range=[0, max_rank],
            dtick=2,
        ),
        yaxis=dict(
            title="",
            categoryorder="array",
            categoryarray=stats["label"].tolist()[::-1],
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.18,
            xanchor="left",
            x=0,
        ),
    )

    return fig


# =============================================================================
# Chart 4 — Ranking Mechanics
# =============================================================================

def fig_the_driver_bar(the_df: pd.DataFrame, year: Optional[int] = None) -> go.Figure:
    """
    Shows which THE indicators are most associated with the overall score.
    Replaces the complicated correlation matrix.
    """
    if the_df.empty:
        return _placeholder_fig(
            "No THE data available.",
            title="THE mainly rewards research capacity",
        )

    if year is None:
        year = int(the_df["year"].max())

    display_names = {
        "teaching": "Teaching",
        "research_environment": "Research Environment",
        "research_quality": "Research Quality",
        "industry_impact": "Industry Impact",
        "international_outlook": "International Outlook",
    }

    metrics = [c for c in display_names if c in the_df.columns]

    if "overall_score" not in the_df.columns or not metrics:
        return _placeholder_fig(
            "THE indicator columns or overall score were not found.",
            title="THE mainly rewards research capacity",
        )

    sub = the_df[the_df["year"] == year][metrics + ["overall_score"]].copy()

    for c in metrics + ["overall_score"]:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")

    sub = sub.dropna()

    if len(sub) < 10:
        return _placeholder_fig(
            "Not enough valid THE indicator data.",
            title="THE mainly rewards research capacity",
        )

    corr = (
        sub[metrics + ["overall_score"]]
        .corr()["overall_score"]
        .drop("overall_score")
        .reset_index()
    )

    corr.columns = ["metric", "correlation"]
    corr = corr.dropna()

    if corr.empty:
        return _placeholder_fig(
            "Indicator correlations could not be computed.",
            title="THE mainly rewards research capacity",
        )

    corr["label"] = corr["metric"].map(display_names)

    research_metrics = {"research_environment", "research_quality"}

    corr["color"] = corr["metric"].apply(
        lambda m: "#2563eb" if m in research_metrics else "#94a3b8"
    )

    corr = corr.sort_values("correlation", ascending=True)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=corr["correlation"],
            y=corr["label"],
            orientation="h",
            marker=dict(color=corr["color"]),
            text=[f"{v:.2f}" for v in corr["correlation"]],
            textposition="outside",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Correlation with THE overall score: %{x:.2f}"
                "<extra></extra>"
            ),
        )
    )

    fig.add_vline(
        x=0.80,
        line_dash="dash",
        line_color="#dc2626",
        annotation_text="Strong association",
        annotation_position="top",
    )

    fig.update_layout(
        **_chart_layout(
            "THE mainly rewards research capacity",
            height=560,
            margin=dict(l=190, r=70, t=90, b=90),
        ),
        xaxis=dict(
            title="Correlation with THE overall score",
            range=[0, 1.08],
            tickformat=".2f",
        ),
        yaxis=dict(title=""),
        showlegend=False,
    )

    return fig


# =============================================================================
# Chart 5 — GDP Outliers, improved
# =============================================================================

def fig_gdp_outlier_strategy(the_df: pd.DataFrame, gdp_df: pd.DataFrame) -> go.Figure:
    """
    GDP per capita vs median THE rank.
    Bubble size = number of ranked universities.
    Trendline = expected median rank based on log GDP per capita.
    """
    df = build_gdp_country_frame(the_df, gdp_df)

    if df.empty or len(df) < 5:
        return _placeholder_fig(
            "Not enough matched GDP-ranking data.",
            title="Wealth matters, but China outperforms its GDP level",
        )

    df["log_gdp"] = np.log10(df["gdp_per_capita"])

    slope, intercept = np.polyfit(df["log_gdp"], df["median_rank"], 1)

    df["expected_rank"] = slope * df["log_gdp"] + intercept

    # Positive = actual rank is better/lower than expected.
    df["outperformance"] = df["expected_rank"] - df["median_rank"]

    # Smaller bubbles to reduce clutter.
    df["bubble_size"] = np.clip(
        7 + 2.7 * np.sqrt(df["ranked_universities"]),
        7,
        30,
    )

    # Only label meaningful countries. Avoid noisy automatic labels.
    label_set = {
        "China",
        "United States",
        "United Kingdom",
        "Switzerland",
        "Singapore",
        "Hong Kong",
        "Luxembourg",
        "Germany",
        "France",
    }

    df["label"] = df["country"].apply(lambda c: c if c in label_set else "")

    fig = go.Figure()

    x_line = np.logspace(df["log_gdp"].min(), df["log_gdp"].max(), 120)
    y_line = slope * np.log10(x_line) + intercept

    fig.add_trace(
        go.Scatter(
            x=x_line,
            y=y_line,
            mode="lines",
            name="GDP expectation line",
            line=dict(color="#64748b", width=2, dash="dash"),
            hovertemplate="GDP expectation line<extra></extra>",
        )
    )

    for region in REGION_ORDER:
        sub = df[df["region"] == region].copy()

        if sub.empty:
            continue

        fig.add_trace(
            go.Scatter(
                x=sub["gdp_per_capita"],
                y=sub["median_rank"],
                mode="markers+text",
                name=region,
                text=sub["label"],
                textposition="top center",
                marker=dict(
                    color=REGION_COLORS[region],
                    size=sub["bubble_size"],
                    opacity=0.75,
                    line=dict(color="white", width=0.8),
                ),
                customdata=sub[["country", "ranked_universities", "outperformance"]].to_numpy(),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "GDP per capita: $%{x:,.0f}<br>"
                    "Median THE rank: %{y:.0f}<br>"
                    "Ranked universities: %{customdata[1]:.0f}<br>"
                    "Outperformance vs GDP expectation: %{customdata[2]:+.0f} rank places"
                    "<extra></extra>"
                ),
            )
        )

    china = df[df["country"] == "China"]

    if not china.empty:
        row = china.iloc[0]
        fig.add_annotation(
            text="China performs better<br>than GDP predicts",
            x=row["gdp_per_capita"],
            y=row["median_rank"],
            showarrow=True,
            arrowhead=2,
            ax=90,
            ay=-55,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#d0d5dd",
            font=dict(size=13, color="#111827"),
        )

    fig.update_layout(
        **_chart_layout(
            "Wealth matters, but China outperforms its GDP level",
            height=660,
            margin=dict(l=80, r=50, t=90, b=120),
        ),
        xaxis=dict(
            title="GDP per capita, current USD — log scale",
            type="log",
            tickmode="array",
            tickvals=[1000, 2000, 5000, 10000, 20000, 50000, 100000, 150000],
            ticktext=["$1k", "$2k", "$5k", "$10k", "$20k", "$50k", "$100k", "$150k"],
        ),
        yaxis=dict(
            title="Median THE rank, latest year — lower is better",
            autorange="reversed",
        ),
        legend=dict(
            title=dict(text="Region"),
            orientation="h",
            yanchor="bottom",
            y=-0.22,
            xanchor="left",
            x=0,
        ),
    )

    return fig


# =============================================================================
# Chart 6 — Domain Strategy, improved diverging bar
# =============================================================================

def fig_engineering_advantage_diverging_bar(subj_df: Optional[pd.DataFrame]) -> go.Figure:
    """
    Professor-friendly version of the Domain Strategy chart.

    Shows regional median Engineering advantage as a diverging bar chart.

    If rank data exists:
        advantage = Arts rank - Engineering rank
        positive = Engineering ranks better.

    If only score data exists:
        advantage = Engineering score - Arts score
        positive = Engineering scores better.
    """
    if subj_df is None or subj_df.empty:
        return _placeholder_fig(
            "Subject ranking data was not found. Add the_subjects_2026.csv to enable this chart.",
            title="Only Asia shows a clear Engineering advantage over Arts & Humanities",
        )

    df = subj_df.copy()
    df = clean_columns(df)

    if "year" in df.columns:
        latest_year = df["year"].max()
        df = df[df["year"] == latest_year].copy()

    subject_col = first_existing(df, ["subject", "subject_area", "area", "field"])

    if subject_col is None:
        subject_col = first_column_containing(df, ["subject"])

    if subject_col is None:
        return _placeholder_fig(
            "No subject column found in subject ranking data.",
            title="Only Asia shows a clear Engineering advantage over Arts & Humanities",
        )

    rank_col = first_existing(
        df,
        ["rank_order", "rank", "world_rank", "ranking", "rank_display"],
    )

    score_col = first_existing(
        df,
        ["score", "overall_score", "scores_overall", "subject_score"],
    )

    if score_col is None:
        score_col = first_column_containing(df, ["score"])

    if "name" not in df.columns:
        name_col = first_existing(
            df,
            ["university_name", "institution", "institution_name", "display_name"],
        )

        if name_col:
            df = df.rename(columns={name_col: "name"})
        else:
            df["name"] = "Unknown institution"

    if "country" not in df.columns:
        country_col = first_existing(df, ["location", "country_name"])

        if country_col:
            df = df.rename(columns={country_col: "country"})
        else:
            df["country"] = "Unknown"

    df["country"] = df["country"].apply(normalize_country)
    df["region"] = df["country"].apply(assign_region)

    df["subject_text"] = df[subject_col].astype(str).str.lower()

    engineering_mask = df["subject_text"].str.contains("engineering", na=False)

    arts_mask = (
        df["subject_text"].str.contains("arts", na=False)
        & df["subject_text"].str.contains("human", na=False)
    )

    df = df[engineering_mask | arts_mask].copy()

    if df.empty:
        return _placeholder_fig(
            "Engineering and Arts & Humanities rows were not found.",
            title="Only Asia shows a clear Engineering advantage over Arts & Humanities",
        )

    df["domain"] = np.where(
        df["subject_text"].str.contains("engineering", na=False),
        "Engineering",
        "Arts & Humanities",
    )

    use_rank = rank_col is not None

    if use_rank:
        df["value"] = df[rank_col].apply(parse_rank)
        value_type = "rank"
    elif score_col is not None:
        df["value"] = df[score_col].apply(parse_numeric)
        value_type = "score"
    else:
        return _placeholder_fig(
            "No rank or score column found in subject data.",
            title="Only Asia shows a clear Engineering advantage over Arts & Humanities",
        )

    df = df.dropna(subset=["value"])

    pivot = (
        df.pivot_table(
            index=["name", "country", "region"],
            columns="domain",
            values="value",
            aggfunc="median",
        )
        .reset_index()
    )

    if "Engineering" not in pivot.columns or "Arts & Humanities" not in pivot.columns:
        return _placeholder_fig(
            "Not enough universities appear in both Engineering and Arts & Humanities.",
            title="Only Asia shows a clear Engineering advantage over Arts & Humanities",
        )

    if value_type == "rank":
        pivot["engineering_advantage"] = (
            pivot["Arts & Humanities"] - pivot["Engineering"]
        )
        x_title = "Median Engineering advantage: Arts rank − Engineering rank"
        interpretation = (
            "Positive values mean Engineering ranks better. "
            "Negative values mean Arts & Humanities ranks better."
        )
    else:
        pivot["engineering_advantage"] = (
            pivot["Engineering"] - pivot["Arts & Humanities"]
        )
        x_title = "Median Engineering advantage: Engineering score − Arts score"
        interpretation = (
            "Positive values mean Engineering scores higher. "
            "Negative values mean Arts & Humanities scores higher."
        )

    summary = (
        pivot.groupby("region")["engineering_advantage"]
        .agg(
            median="median",
            q1=lambda s: s.quantile(0.25),
            q3=lambda s: s.quantile(0.75),
            n="count",
        )
        .reindex(REGION_ORDER)
        .dropna()
        .reset_index()
    )

    if summary.empty:
        return _placeholder_fig(
            "No regional Engineering advantage summary could be computed.",
            title="Only Asia shows a clear Engineering advantage over Arts & Humanities",
        )

    summary["err_plus"] = summary["q3"] - summary["median"]
    summary["err_minus"] = summary["median"] - summary["q1"]
    summary["label"] = summary["median"].apply(lambda v: f"{v:+.0f}")

    max_abs = max(
        abs(summary["q1"].min()),
        abs(summary["q3"].max()),
        1,
    )

    axis_limit = max_abs * 1.25

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=summary["median"],
            y=summary["region"],
            orientation="h",
            marker=dict(
                color=[REGION_COLORS.get(r, "#94a3b8") for r in summary["region"]],
                line=dict(color="white", width=1),
            ),
            error_x=dict(
                type="data",
                symmetric=False,
                array=summary["err_plus"],
                arrayminus=summary["err_minus"],
                color="#475467",
                thickness=1.4,
                width=5,
            ),
            text=summary["label"],
            textposition="outside",
            cliponaxis=False,
            customdata=summary[["q1", "q3", "n"]].to_numpy(),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Median advantage: %{x:.1f}<br>"
                "IQR: %{customdata[0]:.1f} to %{customdata[1]:.1f}<br>"
                "Universities compared: %{customdata[2]:.0f}"
                "<extra></extra>"
            ),
            name="Median Engineering advantage",
        )
    )

    fig.add_vline(
        x=0,
        line_dash="dash",
        line_color="#dc2626",
        line_width=2,
    )

    fig.add_annotation(
        text="Arts & Humanities stronger",
        x=-axis_limit * 0.70,
        y=1.08,
        xref="x",
        yref="paper",
        showarrow=False,
        font=dict(size=13, color="#475467"),
    )

    fig.add_annotation(
        text="Engineering stronger",
        x=axis_limit * 0.70,
        y=1.08,
        xref="x",
        yref="paper",
        showarrow=False,
        font=dict(size=13, color="#475467"),
    )

    fig.add_annotation(
        text=interpretation,
        x=0,
        y=-0.22,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
        font=dict(size=12, color="#667085"),
    )

    fig.update_layout(
        **_chart_layout(
            "Only Asia shows a clear Engineering advantage over Arts & Humanities",
            height=560,
            margin=dict(l=150, r=80, t=100, b=130),
        ),
        xaxis=dict(
            title=x_title,
            zeroline=True,
            zerolinecolor="#dc2626",
            range=[-axis_limit, axis_limit],
        ),
        yaxis=dict(
            title="",
            categoryorder="array",
            categoryarray=REGION_ORDER[::-1],
        ),
        showlegend=False,
    )

    return fig


# =============================================================================
# HTML / CSS
# =============================================================================

CSS = """
:root {
  --bg: #f6f8fb;
  --card: #ffffff;
  --text: #101828;
  --muted: #667085;
  --line: #e4e7ec;
  --blue: #2563eb;
  --dark: #111827;
  --soft: #f9fafb;
  --shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
  --radius: 22px;
}

* {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--text);
  background: var(--bg);
  line-height: 1.55;
}

a {
  color: inherit;
  text-decoration: none;
}

.page {
  width: min(1280px, calc(100% - 40px));
  margin: 0 auto;
}

.nav {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--line);
}

.nav-inner {
  width: min(1280px, calc(100% - 40px));
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 800;
  letter-spacing: -0.03em;
  white-space: nowrap;
}

.brand-mark {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
}

.nav-links {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.nav-links a {
  font-size: 13px;
  font-weight: 700;
  color: #475467;
  padding: 8px 10px;
  border-radius: 999px;
  white-space: nowrap;
}

.nav-links a:hover {
  background: #f2f4f7;
  color: #111827;
}

.hero {
  padding: 54px 0 30px;
}

.hero-card {
  background:
    radial-gradient(circle at 90% 0%, rgba(96, 165, 250, 0.32), transparent 28rem),
    linear-gradient(135deg, #0f172a, #1e293b 55%, #312e81);
  color: white;
  border-radius: 32px;
  padding: 48px;
  box-shadow: var(--shadow);
}

.eyebrow {
  display: inline-flex;
  padding: 7px 11px;
  border-radius: 999px;
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.16);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.82);
}

.hero h1 {
  max-width: 900px;
  margin: 22px 0 18px;
  font-size: clamp(42px, 6vw, 76px);
  line-height: 0.96;
  letter-spacing: -0.065em;
}

.hero p {
  max-width: 820px;
  margin: 0;
  color: rgba(255,255,255,0.78);
  font-size: 18px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.kpi {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: 0 10px 28px rgba(15,23,42,0.05);
}

.kpi-number {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: #111827;
}

.kpi-label {
  margin-top: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
}

section {
  scroll-margin-top: 90px;
}

.section {
  margin: 52px 0;
}

.section-header {
  margin-bottom: 18px;
}

.kicker {
  color: var(--blue);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.11em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

h2 {
  margin: 0;
  font-size: clamp(28px, 4vw, 44px);
  line-height: 1.05;
  letter-spacing: -0.055em;
  color: #111827;
}

.subtitle {
  max-width: 850px;
  margin: 10px 0 0;
  color: var(--muted);
  font-size: 16px;
}

.panel {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 28px;
  box-shadow: var(--shadow);
  overflow: hidden;
}

.panel-pad {
  padding: 26px;
}

.claim-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.claim {
  padding: 18px;
  border-radius: 18px;
  background: var(--soft);
  border: 1px solid var(--line);
}

.claim-num {
  display: inline-flex;
  width: 26px;
  height: 26px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 10px;
}

.claim strong {
  display: block;
  font-size: 15px;
  margin-bottom: 6px;
  color: #111827;
}

.claim p {
  margin: 0;
  font-size: 14px;
  color: #475467;
}

.insight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin: 18px 0;
}

.insight {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 18px;
  box-shadow: 0 8px 22px rgba(15,23,42,0.04);
  position: relative;
  overflow: hidden;
}

.insight::before {
  content: "";
  position: absolute;
  inset: 0 auto auto 0;
  height: 4px;
  width: 100%;
  background: linear-gradient(90deg, #2563eb, #7c3aed);
}

.insight strong {
  display: block;
  font-size: 14px;
  margin-bottom: 7px;
  color: #111827;
}

.insight span {
  display: block;
  font-size: 14px;
  color: #475467;
}

.chart-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 28px;
  box-shadow: var(--shadow);
  padding: 16px;
  overflow: hidden;
}

.plot-wrap {
  width: 100%;
  min-height: 520px;
}

.js-plotly-plot,
.plotly-graph-div {
  width: 100% !important;
}

.story-card {
  margin-top: 15px;
  background: #f8fafc;
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 22px;
}

.story-card h3 {
  margin: 0 0 8px;
  font-size: 18px;
  letter-spacing: -0.025em;
}

.story-card p {
  margin: 0;
  color: #475467;
  font-size: 15px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.tag {
  display: inline-flex;
  padding: 5px 9px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
}

.callout {
  background: linear-gradient(135deg, #111827, #1f2937);
  color: white;
  border-radius: 28px;
  padding: 34px;
  box-shadow: var(--shadow);
}

.callout h2 {
  color: white;
  font-size: 34px;
}

.callout p {
  max-width: 900px;
  color: rgba(255,255,255,0.78);
  margin: 12px 0 0;
}

footer {
  padding: 44px 0 70px;
  color: var(--muted);
  font-size: 14px;
}

@media (max-width: 1000px) {
  .kpi-grid,
  .claim-grid,
  .insight-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .nav-inner {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 720px) {
  .page,
  .nav-inner {
    width: min(100% - 24px, 1280px);
  }

  .hero-card {
    padding: 30px;
  }

  .kpi-grid,
  .claim-grid,
  .insight-grid {
    grid-template-columns: 1fr;
  }
}
"""


def _fig_to_div(fig: go.Figure) -> str:
    """Render Plotly figure to HTML div."""
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config=PLOTLY_CONFIG,
    )


def _insight(title: str, body: str) -> str:
    return f"""
    <div class="insight">
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
    """


def _story(title: str, body: str, tags: Optional[list[str]] = None) -> str:
    tag_html = ""

    if tags:
        tag_html = '<div class="tag-row">' + "".join(
            f'<span class="tag">{tag}</span>' for tag in tags
        ) + "</div>"

    return f"""
    <div class="story-card">
      <h3>{title}</h3>
      <p>{body}</p>
      {tag_html}
    </div>
    """


def _section(
    section_id: str,
    kicker: str,
    heading: str,
    subtitle: str,
    insights: list[tuple[str, str]],
    fig: go.Figure,
    story_title: str,
    story_body: str,
    tags: Optional[list[str]] = None,
) -> str:
    insight_html = "\n".join(_insight(t, b) for t, b in insights)

    return f"""
    <section id="{section_id}" class="section">
      <div class="section-header">
        <div class="kicker">{kicker}</div>
        <h2>{heading}</h2>
        <p class="subtitle">{subtitle}</p>
      </div>

      <div class="insight-grid">
        {insight_html}
      </div>

      <div class="chart-card">
        <div class="plot-wrap">
          {_fig_to_div(fig)}
        </div>
      </div>

      {_story(story_title, story_body, tags)}
    </section>
    """


def build_html(
    fig_macro: go.Figure,
    fig_method: go.Figure,
    fig_elite: go.Figure,
    fig_drivers: go.Figure,
    fig_gdp: go.Figure,
    fig_domain: go.Figure,
    the_count: int,
    qs_matched: int,
    asia_delta_text: str,
    gdp_country_count: int,
) -> str:
    """Build final dashboard HTML."""
    sections = ""

    sections += _section(
        section_id="macro",
        kicker="1 · Macro Shift",
        heading="Asia is gaining Top-200 market share",
        subtitle=(
            "The THE Top 200 is a fixed global arena. When one region gains elite seats, "
            "another region must lose share."
        ),
        insights=[
            (
                "Zero-sum competition",
                "The chart treats the Top 200 as a fixed market of elite university positions.",
            ),
            (
                "Asia is rising",
                "Asian major economies gain a larger share of the Top 200 over time.",
            ),
            (
                "Prestige is becoming contested",
                "Historical Anglosphere dominance remains strong, but it is no longer expanding.",
            ),
        ],
        fig=fig_macro,
        story_title="Policy insight",
        story_body=(
            "Elite academic visibility is shifting from a historically Western-dominated order "
            "toward a more competitive global distribution. For policymakers, this means ranking "
            "performance is increasingly shaped by long-term national research investment."
        ),
        tags=["Top 200", "Geopolitics", "Market share"],
    )

    sections += _section(
        section_id="methodology",
        kicker="2 · THE vs QS",
        heading="Ranking choice affects universities differently by region",
        subtitle=(
            "This chart uses percentile-position disagreement, not raw rank difference. "
            "It shows where THE and QS produce different views of the same institutions."
        ),
        insights=[
            (
                "Rank is system-dependent",
                "A university's position changes depending on whether THE or QS is used.",
            ),
            (
                "Volatility is uneven",
                "Some regions experience larger THE-QS percentile disagreement than others.",
            ),
            (
                "Methodology is strategy",
                "Universities can rise in one system while remaining less visible in another.",
            ),
        ],
        fig=fig_method,
        story_title="Policy insight",
        story_body=(
            "Rankings are not neutral mirrors of quality. They are measurement systems with "
            "different priorities. Strategic planners should therefore choose which ranking system "
            "they are optimising for, instead of treating global rank as a single objective fact."
        ),
        tags=["THE", "QS", "Percentile disagreement"],
    )

    sections += _section(
        section_id="elite",
        kicker="3 · Elite Stability",
        heading="The very top is structurally locked",
        subtitle=(
            "The top universities do not move like ordinary institutions. Their rank ranges are "
            "narrow, showing a highly stable prestige ceiling."
        ),
        insights=[
            (
                "The top is sticky",
                "Elite universities remain within a narrow rank range across the decade.",
            ),
            (
                "Top-5 access is difficult",
                "The highest positions are dominated by a small group of historically prestigious institutions.",
            ),
            (
                "Better target zone",
                "For most systems, the Top 20-50 is a more realistic strategic intervention zone.",
            ),
        ],
        fig=fig_elite,
        story_title="Policy insight",
        story_body=(
            "For non-Anglosphere systems, aiming immediately for the global Top 5 may be inefficient. "
            "The data suggests that the pinnacle is structurally stable. Policy should instead focus "
            "on moving institutions into the more volatile elite boundary zones."
        ),
        tags=["Elite stability", "Prestige lock-in", "Rank volatility"],
    )

    sections += _section(
        section_id="drivers",
        kicker="4 · Ranking Mechanics",
        heading="THE mainly rewards research capacity",
        subtitle=(
            "Instead of showing a full correlation matrix, this chart answers one policy question: "
            "which THE indicators are most connected to the overall score?"
        ),
        insights=[
            (
                "Research is the main lever",
                "Research Environment and Research Quality are most strongly associated with THE overall score.",
            ),
            (
                "Not all missions count equally",
                "Industry Impact and International Outlook are weaker routes to overall THE improvement.",
            ),
            (
                "Metric-aware investment",
                "A THE-focused strategy should prioritise research infrastructure and citation visibility.",
            ),
        ],
        fig=fig_drivers,
        story_title="Policy insight",
        story_body=(
            "THE operationalises excellence mainly through research capacity. This is a methodology audit, "
            "not a causal model. It does not mean teaching or industry engagement are unimportant, but it does "
            "mean that they are weaker levers for improving THE rank compared with research strength."
        ),
        tags=["THE methodology", "Research capacity", "Ranking mechanics"],
    )

    sections += _section(
        section_id="gdp",
        kicker="5 · GDP Outliers",
        heading="Wealth matters, but China outperforms its GDP level",
        subtitle=(
            "GDP per capita captures national resource capacity. The trendline shows expected "
            "academic standing from wealth; labelled outliers show who performs above or below expectation."
        ),
        insights=[
            (
                "Wealth buys infrastructure",
                "High-GDP countries usually achieve stronger median university rankings.",
            ),
            (
                "China is an outlier",
                "China performs better than its GDP per capita would predict.",
            ),
            (
                "Scale is separate",
                "Bubble size shows the number of ranked universities, not GDP, avoiding duplicate encoding.",
            ),
        ],
        fig=fig_gdp,
        story_title="Policy insight",
        story_body=(
            "National wealth is a structural advantage, but it is not destiny. China suggests that "
            "coordinated, long-term state investment can partly overcome GDP constraints and produce "
            "ranking performance above economic expectation."
        ),
        tags=["GDP per capita", "Outlier analysis", "State investment"],
    )

    sections += _section(
        section_id="domain",
        kicker="6 · Domain Strategy",
        heading="Only Asia shows a clear Engineering advantage over Arts & Humanities",
        subtitle=(
            "This chart summarises each region's median difference between Engineering rank and "
            "Arts & Humanities rank. Positive values mean Engineering performs better."
        ),
        insights=[
            (
                "Asia is the clearest STEM specialist",
                "Asia is the only region with a clearly positive Engineering-over-Arts advantage.",
            ),
            (
                "Europe tilts toward Arts & Humanities",
                "European institutions show stronger relative positions in Arts & Humanities than Engineering.",
            ),
            (
                "Strategy implication",
                "STEM concentration can improve ranking visibility, but it narrows the broader university mission.",
            ),
        ],
        fig=fig_domain,
        story_title="Policy insight",
        story_body=(
            "Subject strategy is ranking strategy. Asian institutions appear to gain visibility through "
            "Engineering strength, while European and Rest-of-World institutions show a different balance. "
            "Policymakers should therefore decide whether they want to optimise for research-heavy STEM metrics "
            "or preserve a broader comprehensive university profile."
        ),
        tags=["Engineering advantage", "Subject rankings", "STEM strategy"],
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />

  <title>Prestige vs. Performance | Global University Rankings Dashboard</title>

  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link
    href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
    rel="stylesheet"
  >

  <style>{CSS}</style>
</head>

<body>
  <nav class="nav">
    <div class="nav-inner">
      <a class="brand" href="#top">
        <span class="brand-mark"></span>
        <span>Prestige vs. Performance</span>
      </a>

      <div class="nav-links">
        <a href="#overview">Overview</a>
        <a href="#macro">Macro Shift</a>
        <a href="#methodology">THE vs QS</a>
        <a href="#elite">Elite Stability</a>
        <a href="#drivers">Mechanics</a>
        <a href="#gdp">GDP</a>
        <a href="#domain">Domain</a>
        <a href="#conclusion">Conclusion</a>
      </div>
    </div>
  </nav>

  <main id="top" class="page">
    <header class="hero">
      <div class="hero-card">
        <div class="eyebrow">Global University Rankings Dashboard · KU Leuven Data Visualisation</div>
        <h1>Prestige vs. Performance</h1>
        <p>
          A focused visual argument showing how global university rankings reward different
          institutional strategies: reputation, research capacity, national wealth, and STEM specialisation.
        </p>
      </div>

      <div class="kpi-grid">
        <div class="kpi">
          <div class="kpi-number">{the_count:,}</div>
          <div class="kpi-label">THE records cleaned</div>
        </div>

        <div class="kpi">
          <div class="kpi-number">{qs_matched:,}</div>
          <div class="kpi-label">Universities matched between THE and QS</div>
        </div>

        <div class="kpi">
          <div class="kpi-number">{asia_delta_text}</div>
          <div class="kpi-label">Asia Top-200 share change</div>
        </div>

        <div class="kpi">
          <div class="kpi-number">{gdp_country_count}</div>
          <div class="kpi-label">Countries matched with GDP data</div>
        </div>
      </div>
    </header>

    <section id="overview" class="section">
      <div class="section-header">
        <div class="kicker">Project Narrative</div>
        <h2>Six visual claims, one policy argument</h2>
        <p class="subtitle">
          The dashboard has been simplified from an exploratory collection into an explanatory story.
          Each chart communicates one main takeaway without requiring the viewer to hover over every point.
        </p>
      </div>

      <div class="panel panel-pad">
        <div class="claim-grid">
          <div class="claim">
            <div class="claim-num">1</div>
            <strong>Macro Shift</strong>
            <p>Asia is gaining Top-200 market share.</p>
          </div>

          <div class="claim">
            <div class="claim-num">2</div>
            <strong>THE vs QS</strong>
            <p>Ranking choice affects universities differently by region.</p>
          </div>

          <div class="claim">
            <div class="claim-num">3</div>
            <strong>Elite Stability</strong>
            <p>The very top is structurally locked.</p>
          </div>

          <div class="claim">
            <div class="claim-num">4</div>
            <strong>Ranking Mechanics</strong>
            <p>THE mainly rewards research capacity.</p>
          </div>

          <div class="claim">
            <div class="claim-num">5</div>
            <strong>GDP Outliers</strong>
            <p>Wealth matters, but China outperforms its GDP level.</p>
          </div>

          <div class="claim">
            <div class="claim-num">6</div>
            <strong>Domain Strategy</strong>
            <p>Only Asia shows a clear Engineering advantage over Arts & Humanities.</p>
          </div>
        </div>
      </div>
    </section>

    {sections}

    <section id="conclusion" class="section">
      <div class="callout">
        <h2>Final recommendation</h2>
        <p>
          Policymakers should not treat global rank as a single neutral truth. THE and QS reward
          different forms of excellence, and countries follow different strategic paths. A responsible
          ranking strategy should triangulate multiple systems, invest in research capacity where the
          chosen metric rewards it, and remain aware of the social cost of over-specialising in STEM.
        </p>
      </div>
    </section>
  </main>

  <footer>
    <div class="page">
      Prestige vs. Performance · Data Visualisation · KU Leuven · 2026
    </div>
  </footer>
</body>
</html>"""


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    print("Loading data...")

    the_df = load_the("the_rankings.csv")
    qs_df = load_qs("qs_rankings.csv")
    gdp_df = load_gdp("gdp_per_capita.csv")
    subj_df = load_subjects("the_subjects.csv")

    print("Preparing data...")

    merged = build_merged(the_df, qs_df)
    share_df = compute_top200_share(the_df)
    gdp_country_frame = build_gdp_country_frame(the_df, gdp_df)

    the_count = len(the_df)
    qs_matched = len(merged)

    asia_delta = compute_share_delta(share_df, "Asia")
    asia_delta_text = format_pp(asia_delta)

    gdp_country_count = len(gdp_country_frame)

    print("Building charts...")

    fig_macro = fig_macro_shift(share_df)
    fig_method = fig_methodology_divergence(merged)
    fig_elite = fig_elite_stability(the_df, top_n=12)
    fig_drivers = fig_the_driver_bar(the_df)
    fig_gdp = fig_gdp_outlier_strategy(the_df, gdp_df)
    fig_domain = fig_engineering_advantage_diverging_bar(subj_df)

    print("Assembling HTML...")

    html = build_html(
        fig_macro=fig_macro,
        fig_method=fig_method,
        fig_elite=fig_elite,
        fig_drivers=fig_drivers,
        fig_gdp=fig_gdp,
        fig_domain=fig_domain,
        the_count=the_count,
        qs_matched=qs_matched,
        asia_delta_text=asia_delta_text,
        gdp_country_count=gdp_country_count,
    )

    Path(OUTPUT_FILE).write_text(html, encoding="utf-8")

    size_kb = Path(OUTPUT_FILE).stat().st_size // 1024

    print(f"Done → {OUTPUT_FILE} ({size_kb:,} KB)")


if __name__ == "__main__":
    main()