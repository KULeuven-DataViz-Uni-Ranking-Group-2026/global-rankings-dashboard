#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
full_dashboard_2.py

Standalone dashboard generator for:
Prestige vs. Performance: Visualizing Biases in Global University Rankings

This script:
1. Downloads or loads THE and QS ranking data.
2. Cleans and merges datasets.
3. Builds all Plotly visualizations.
4. Exports a modern GitHub Pages-ready HTML dashboard to dashboard/index.html.

Recommended run:
    pip install pandas numpy plotly scipy rapidfuzz requests kagglehub
    python full_dashboard_2.py --subjects-csv data/the_subjects_2026.csv

Optional local CSV usage:
    python full_dashboard_2.py \
        --times-csv path/to/the_rankings.csv \
        --qs-csv path/to/qs_2026.csv \
        --subjects-csv path/to/the_subjects_2026.csv
"""

import argparse
import os
import re
import sys
import warnings
from datetime import date

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import requests
from scipy.stats import linregress

try:
    from rapidfuzz import process as fuzzy_process
except Exception:
    try:
        from thefuzz import process as fuzzy_process
    except Exception:
        fuzzy_process = None

try:
    import kagglehub
except Exception:
    kagglehub = None


# ============================================================
# GLOBAL SETTINGS
# ============================================================

PLOT_CONFIG = {
    "responsive": True,
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
}

REGION_ORDER = [
    "Anglosphere (US/UK/etc)",
    "Asia (Major Economies)",
    "European Union (Major)",
    "Rest of World",
]

REGION_COLORS = {
    "Anglosphere (US/UK/etc)": "#2563eb",
    "Asia (Major Economies)": "#7c3aed",
    "European Union (Major)": "#f97316",
    "Rest of World": "#10b981",
}

PRISM = px.colors.qualitative.Prism


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def log(msg):
    print(f"[dashboard] {msg}", flush=True)


def normalize_column_name(col):
    col = str(col).strip()
    col = re.sub(r"[^0-9a-zA-Z]+", "_", col)
    col = col.strip("_").lower()
    return col


def normalize_columns(df):
    df = df.copy()
    df.columns = [normalize_column_name(c) for c in df.columns]
    return df


def parse_rank_value(value):
    """
    Converts values like:
    '=10', '601-650', '401–500', '1201+', 'Reporter'
    into numeric top-rank bucket.
    """
    if pd.isna(value):
        return np.nan

    s = str(value).strip()
    s = s.replace(",", "")
    s = s.replace("=", "")
    s = s.replace("+", "")
    match = re.search(r"\d+", s)

    if not match:
        return np.nan

    return float(match.group(0))


def to_numeric_clean(series):
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("–", "-", regex=False)
        .str.strip(),
        errors="coerce",
    )


def clean_university_name(name):
    name = str(name).lower()
    name = re.sub(r"\s*\(.*?\)", "", name)
    name = name.replace("’", "'")
    name = re.sub(r"^the\s+", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def norm_for_col_search(col):
    return re.sub(r"[^a-z0-9]+", "", str(col).lower())


def find_col_by_tokens(df, token_groups, exclude=None):
    """
    Finds a column by token groups.
    Example:
        find_col_by_tokens(df, [["ar", "score"], ["academic", "reputation"]])
    """
    exclude = set(exclude or [])
    cols = [c for c in df.columns if c not in exclude]
    norm_map = {c: norm_for_col_search(c) for c in cols}

    for tokens in token_groups:
        clean_tokens = [norm_for_col_search(t) for t in tokens]
        matches = []
        for col, normed in norm_map.items():
            if all(t in normed for t in clean_tokens):
                matches.append(col)
        if matches:
            return matches[0]

    return None


def best_fuzzy_match(query, choices):
    if fuzzy_process is None:
        raise ImportError(
            "No fuzzy matching library found. Install rapidfuzz or thefuzz:\n"
            "pip install rapidfuzz"
        )

    result = fuzzy_process.extractOne(query, choices)
    if result is None:
        return None, 0

    # rapidfuzz returns (choice, score, index)
    # thefuzz returns (choice, score)
    return result[0], result[1]


def get_region(country):
    anglosphere = [
        "United States", "United Kingdom", "Australia",
        "Canada", "New Zealand", "Ireland",
    ]
    asian_tigers = [
        "China", "Japan", "South Korea", "Singapore", "Hong Kong",
    ]
    eu_majors = [
        "Germany", "France", "Netherlands", "Switzerland",
        "Sweden", "Belgium", "Italy", "Spain",
    ]

    if country in anglosphere:
        return "Anglosphere (US/UK/etc)"
    elif country in asian_tigers:
        return "Asia (Major Economies)"
    elif country in eu_majors:
        return "European Union (Major)"
    else:
        return "Rest of World"


def get_granular_region(country):
    if country in ["United States", "Canada"]:
        return "North America"
    elif country in ["United Kingdom", "Ireland"]:
        return "UK & Ireland"
    elif country in ["Australia", "New Zealand"]:
        return "Oceania"
    elif country in ["China", "Hong Kong", "Macao", "Taiwan"]:
        return "Greater China"
    elif country in ["Japan", "South Korea"]:
        return "East Asia (Japan/Korea)"
    elif country in ["India", "Pakistan", "Bangladesh", "Sri Lanka"]:
        return "South Asia"
    elif country in ["Singapore", "Malaysia", "Indonesia", "Thailand", "Vietnam", "Philippines"]:
        return "Southeast Asia"
    elif country in [
        "Germany", "France", "Netherlands", "Switzerland", "Sweden",
        "Belgium", "Italy", "Spain", "Denmark", "Finland",
        "Norway", "Austria", "Luxembourg",
    ]:
        return "Western/Northern Europe"
    elif country in [
        "Saudi Arabia", "United Arab Emirates", "Qatar", "Israel",
        "Iran", "Turkey", "Egypt", "Lebanon", "Jordan", "Oman",
    ]:
        return "Middle East & North Africa (MENA)"
    elif country in ["Brazil", "Mexico", "Chile", "Argentina", "Colombia", "Peru"]:
        return "Latin America"
    elif country in ["South Africa", "Ghana", "Nigeria", "Kenya"]:
        return "Sub-Saharan Africa"
    else:
        return "Rest of Europe / Other"


def zscore_series(series):
    series = pd.to_numeric(series, errors="coerce")
    std = series.std(ddof=0)
    if std == 0 or pd.isna(std):
        return series * np.nan
    return (series - series.mean()) / std


def empty_figure(title, message):
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=18, color="#475467"),
        align="center",
    )
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=520,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="white",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def polish_figure(fig):
    """
    Light visual polishing without changing the analytical logic.
    """
    fig.update_layout(
        autosize=True,
        font=dict(
            family="Inter, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
            color="#1f2937",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.96)",
        title=dict(
            x=0.02,
            xanchor="left",
            font=dict(size=20, color="#111827"),
        ),
        margin=dict(l=60, r=40, t=85, b=120),
    )
    fig.layout.width = None
    return fig


def find_csv_in_dir(directory):
    csv_files = [f for f in os.listdir(directory) if f.lower().endswith(".csv")]
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {directory}")
    return os.path.join(directory, csv_files[0])


def download_kaggle_dataset(dataset_slug):
    if kagglehub is None:
        raise ImportError(
            "kagglehub is not installed. Install it with:\n"
            "pip install kagglehub\n"
            "Or pass local CSV paths using --times-csv and --qs-csv."
        )

    log(f"Downloading Kaggle dataset: {dataset_slug}")
    path = kagglehub.dataset_download(dataset_slug)
    return find_csv_in_dir(path)


# ============================================================
# DATA LOADING
# ============================================================

def load_times_data(times_csv=None):
    if times_csv:
        path = times_csv
    else:
        path = download_kaggle_dataset("raymondtoo/the-world-university-rankings-2016-2024")

    log(f"Loading THE data: {path}")
    df = pd.read_csv(path)
    df = normalize_columns(df)

    required = ["rank", "name", "country", "year"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"THE dataset missing required columns: {missing}")

    df["rank"] = df["rank"].apply(parse_rank_value)
    df["rank"] = df["rank"].fillna(9999).astype(int)

    if "student_population" in df.columns:
        df["student_population"] = to_numeric_clean(df["student_population"])
    else:
        df["student_population"] = np.nan

    if "international_students" in df.columns:
        df["international_students"] = to_numeric_clean(df["international_students"])

    numeric_cols = [
        "students_to_staff_ratio",
        "overall_score",
        "teaching",
        "research_environment",
        "research_quality",
        "industry_impact",
        "international_outlook",
        "year",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = to_numeric_clean(df[col])

    df["year"] = df["year"].astype(int)
    df["region_group"] = df["country"].apply(get_region)

    log(f"THE data loaded: {len(df):,} rows")
    return df


def load_qs_data(qs_csv=None):
    if qs_csv:
        path = qs_csv
    else:
        path = download_kaggle_dataset("akashbommidi/2026-qs-world-university-rankings")

    log(f"Loading QS data: {path}")
    df = pd.read_csv(path)

    rank_col = find_col_by_tokens(df, [["2026", "rank"], ["rank"]])
    if rank_col is None:
        raise ValueError("Could not find QS rank column.")

    name_col = find_col_by_tokens(df, [["institution", "name"], ["university", "name"], ["name"]])
    if name_col is None:
        raise ValueError("Could not find QS institution name column.")

    df["qs_rank"] = df[rank_col].apply(parse_rank_value)
    df["name_clean_qs"] = df[name_col].apply(clean_university_name)

    for col in df.columns:
        if "score" in str(col).lower():
            df[col] = pd.to_numeric(df[col], errors="coerce")

    log(f"QS data loaded: {len(df):,} rows")
    return df


def merge_times_qs(df_times, df_qs):
    log("Preparing 2026 THE data for merge")
    df_times_2026 = df_times[df_times["year"] == 2026].copy()

    if df_times_2026.empty:
        raise ValueError("No 2026 rows found in THE dataset.")

    df_times_2026["name_clean_the"] = df_times_2026["name"].apply(clean_university_name)

    # Remove duplicated clean names to avoid duplicated merge explosions.
    df_times_2026 = df_times_2026.sort_values("rank").drop_duplicates("name_clean_the", keep="first")
    df_qs = df_qs.sort_values("qs_rank").drop_duplicates("name_clean_qs", keep="first")

    times_names = df_times_2026["name_clean_the"].dropna().unique().tolist()
    times_set = set(times_names)
    qs_names = df_qs["name_clean_qs"].dropna().unique().tolist()

    log("Running fuzzy matching between QS and THE names")
    name_mapping = {}

    for i, qs_name in enumerate(qs_names, start=1):
        if qs_name in times_set:
            name_mapping[qs_name] = qs_name
        else:
            best, score = best_fuzzy_match(qs_name, times_names)
            if score >= 90:
                name_mapping[qs_name] = best

        if i % 250 == 0:
            log(f"Matched progress: {i:,}/{len(qs_names):,}")

    df_qs["merge_name"] = df_qs["name_clean_qs"].map(name_mapping)
    df_qs_matched = df_qs.dropna(subset=["merge_name"]).copy()

    df_merged = pd.merge(
        df_times_2026,
        df_qs_matched,
        left_on="name_clean_the",
        right_on="merge_name",
        how="inner",
        suffixes=("_the", "_qs"),
    )

    df_merged["region_group"] = df_merged["country"].apply(get_region)
    df_merged["display_university"] = df_merged["name"]

    log(f"Successfully matched {len(df_merged):,} universities")
    return df_merged


# ============================================================
# FIGURE CREATION
# ============================================================

def create_macro_area(df_times):
    df_top200 = df_times[df_times["rank"] <= 200].copy()

    matrix = df_top200.groupby(["year", "region_group"]).size().unstack().fillna(0)

    for region in REGION_ORDER:
        if region not in matrix.columns:
            matrix[region] = 0

    matrix = matrix[REGION_ORDER].sort_index()
    market_share = (matrix / 200) * 100

    df_market = market_share.reset_index().melt(
        id_vars="year",
        var_name="Region",
        value_name="Market_Share",
    )

    fig = px.area(
        df_market,
        x="year",
        y="Market_Share",
        color="Region",
        title="Zero-Sum Geopolitics: Global Market Share of Top 200 Universities (2016–2026)",
        labels={
            "Market_Share": "Market Share of Top 200 (%)",
            "year": "Year",
        },
        template="plotly_white",
        color_discrete_map=REGION_COLORS,
        height=620,
        category_orders={"Region": REGION_ORDER},
    )

    fig.update_layout(
        legend_title_text="Geopolitical Region",
        yaxis=dict(ticksuffix="%"),
    )

    stats_list = []
    years = matrix.index.values

    for col in matrix.columns:
        y_values = matrix[col].values

        if len(years) >= 2:
            slope, intercept, r_value, p_value, std_err = linregress(years, y_values)
            consistency = r_value ** 2
        else:
            slope = 0
            consistency = 0

        start_val = y_values[0] if y_values[0] != 0 else 1
        end_val = y_values[-1]
        if len(years) > 1 and start_val > 0:
            cagr = ((end_val / start_val) ** (1 / (len(years) - 1)) - 1) * 100
        else:
            cagr = 0

        stats_list.append({
            "Region": col,
            "Net Change (Seats)": int(end_val - start_val),
            "Velocity (Seats/Year)": round(float(slope), 2),
            "Consistency (R²)": round(float(consistency), 3),
            "CAGR (%)": round(float(cagr), 2),
        })

    stats = pd.DataFrame(stats_list).sort_values("Velocity (Seats/Year)", ascending=False)

    return fig, stats


def create_compare_scatter(df_merged):
    if df_merged.empty:
        return empty_figure(
            "Methodological Divergence: Times vs. QS",
            "No matched THE/QS universities available.",
        ), np.nan

    plot_df = df_merged.copy()
    plot_df["qs_rank"] = pd.to_numeric(plot_df["qs_rank"], errors="coerce")
    plot_df = plot_df.dropna(subset=["rank", "qs_rank"])

    rank_corr = plot_df["rank"].corr(plot_df["qs_rank"])

    plot_df = plot_df[(plot_df["rank"] <= 260) & (plot_df["qs_rank"] <= 260)].copy()

    plot_df["display_name"] = plot_df.apply(
        lambda x: x["display_university"] if (x["rank"] <= 50 or x["qs_rank"] <= 50) else "",
        axis=1,
    )

    fig = px.scatter(
        plot_df,
        x="rank",
        y="qs_rank",
        color="region_group",
        hover_name="display_university",
        text="display_name",
        hover_data=["country"],
        title="Methodological Divergence: THE vs. QS World Rankings 2026",
        labels={
            "rank": "THE Rank, Research-Heavy →",
            "qs_rank": "QS Rank, Reputation-Heavy ↑",
            "region_group": "Geopolitical Region",
        },
        template="plotly_white",
        color_discrete_map=REGION_COLORS,
        height=820,
        category_orders={"region_group": REGION_ORDER},
    )

    fig.update_xaxes(range=[260, 0])
    fig.update_yaxes(range=[260, 0])
    fig.add_shape(
        type="line",
        x0=260,
        y0=260,
        x1=0,
        y1=0,
        line=dict(color="#dc2626", dash="dash"),
    )

    fig.add_annotation(
        x=200,
        y=30,
        text="<b>QS Advantage Zone</b><br>High reputation, lower THE rank",
        showarrow=False,
        font=dict(size=15, color="rgba(75,85,99,0.72)"),
        align="center",
        bgcolor="rgba(255,255,255,0.75)",
    )

    fig.add_annotation(
        x=30,
        y=200,
        text="<b>THE Advantage Zone</b><br>High research performance, lower QS rank",
        showarrow=False,
        font=dict(size=15, color="rgba(75,85,99,0.72)"),
        align="center",
        bgcolor="rgba(255,255,255,0.75)",
    )

    fig.update_traces(
        mode="markers",
        textposition="top right",
        textfont=dict(size=9, color="#374151"),
        marker=dict(size=8, line=dict(width=0.5, color="white")),
    )

    fig.update_layout(
        margin=dict(b=125),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                buttons=[
                    dict(label="Hide Names", method="update", args=[{"mode": "markers"}]),
                    dict(label="Show Top 50 Names", method="update", args=[{"mode": "markers+text"}]),
                ],
                showactive=True,
                x=0,
                xanchor="left",
                y=-0.15,
                yanchor="top",
            )
        ],
    )

    return fig, rank_corr


def create_elite_box(df_times):
    elite_names = df_times[df_times["rank"] <= 10]["name"].unique()
    df_elite = df_times[df_times["name"].isin(elite_names)].copy()

    if df_elite.empty:
        return empty_figure(
            "Statistical Volatility of the Elite",
            "No elite university rows available.",
        ), pd.DataFrame()

    median_ranks = df_elite.groupby("name")["rank"].median().sort_values(ascending=False)
    ordered_unis = median_ranks.index.tolist()

    fig = px.box(
        df_elite,
        x="rank",
        y="name",
        color="name",
        points="all",
        hover_data=["year"],
        category_orders={"name": ordered_unis},
        title="Statistical Volatility of the Elite: Distribution & Variance (2016–2026)",
        labels={"rank": "Global Rank Distribution", "name": ""},
        template="plotly_white",
        color_discrete_sequence=PRISM,
        height=760,
    )

    fig.update_xaxes(autorange="reversed", tickmode="linear", tick0=1, dtick=1, range=[20, 0])
    fig.update_layout(showlegend=False)
    fig.update_traces(
        marker=dict(size=6, opacity=0.8, line=dict(width=1, color="DarkSlateGrey"))
    )

    volatility = (
        df_elite.groupby("name")["rank"]
        .std()
        .round(2)
        .reset_index()
        .rename(columns={"rank": "Volatility (Std Dev)"})
        .sort_values("Volatility (Std Dev)")
    )

    return fig, volatility


def create_correlation_heatmap(df_times):
    score_cols = [
        "teaching",
        "research_environment",
        "research_quality",
        "industry_impact",
        "international_outlook",
        "overall_score",
    ]

    available = [c for c in score_cols if c in df_times.columns]
    df_2026 = df_times[df_times["year"] == 2026][available].dropna()

    if df_2026.empty or len(available) < 2:
        return empty_figure(
            "Correlation Matrix of Ranking Indicators",
            "Not enough 2026 score columns available.",
        ), pd.Series(dtype=float)

    corr = df_2026.corr()

    fig = px.imshow(
        corr,
        text_auto=".2f",
        aspect="auto",
        color_continuous_scale="RdBu_r",
        title="Correlation Matrix of THE Ranking Indicators, 2026",
        template="plotly_white",
        height=650,
    )

    sorted_corr = corr["overall_score"].sort_values(ascending=False) if "overall_score" in corr.columns else pd.Series(dtype=float)

    return fig, sorted_corr


def create_prestige_vs_performance(df_merged):
    if df_merged.empty:
        return empty_figure(
            "Methodology Clash: QS Reputation vs. THE Research Quality",
            "No matched THE/QS data available.",
        ), np.nan, None, None

    qs_ar_col = find_col_by_tokens(
        df_merged,
        [["ar", "score"], ["academic", "reputation", "score"], ["academic", "reputation"]],
    )

    if qs_ar_col is None:
        qs_ar_col = find_col_by_tokens(
            df_merged,
            [["overall", "score"]],
            exclude={"overall_score"},
        )

    the_research_col = "research_quality" if "research_quality" in df_merged.columns else find_col_by_tokens(
        df_merged,
        [["research", "quality"], ["research"]],
    )

    if qs_ar_col is None or the_research_col is None:
        return empty_figure(
            "Methodology Clash: QS Reputation vs. THE Research Quality",
            "Required QS reputation or THE research columns were not found.",
        ), np.nan, qs_ar_col, the_research_col

    plot_df = df_merged.copy()
    plot_df[qs_ar_col] = pd.to_numeric(plot_df[qs_ar_col], errors="coerce")
    plot_df[the_research_col] = pd.to_numeric(plot_df[the_research_col], errors="coerce")
    plot_df = plot_df.dropna(subset=[qs_ar_col, the_research_col])

    metric_corr = plot_df[qs_ar_col].corr(plot_df[the_research_col])

    plot_df["display_name"] = plot_df.apply(
        lambda x: x["display_university"]
        if (x["rank"] <= 100 or (x[the_research_col] > 80 and x[qs_ar_col] < 40))
        else "",
        axis=1,
    )

    fig = px.scatter(
        plot_df,
        x=qs_ar_col,
        y=the_research_col,
        color="region_group",
        hover_name="display_university",
        text="display_name",
        hover_data=["country"],
        title="Methodology Clash: QS Academic Reputation vs. THE Research Quality",
        labels={
            qs_ar_col: "QS Academic Reputation / Reputation Proxy →",
            the_research_col: "THE Research Quality ↑",
            "region_group": "Geopolitical Region",
        },
        template="plotly_white",
        color_discrete_map=REGION_COLORS,
        height=820,
        category_orders={"region_group": REGION_ORDER},
    )

    fig.update_xaxes(range=[0, 100])
    fig.update_yaxes(range=[0, 100])

    fig.add_shape(
        type="line",
        x0=0,
        y0=0,
        x1=100,
        y1=100,
        line=dict(color="#dc2626", dash="dash"),
    )

    fig.add_annotation(
        x=22,
        y=93,
        text="<b>Hidden Gems</b><br>Strong research,<br>weaker global brand",
        showarrow=False,
        font=dict(size=15, color="rgba(75,85,99,0.78)"),
        align="center",
        bgcolor="rgba(255,255,255,0.78)",
    )

    fig.add_annotation(
        x=82,
        y=86,
        text="<b>Old Guard</b><br>High output and high prestige",
        showarrow=False,
        font=dict(size=15, color="rgba(75,85,99,0.78)"),
        align="center",
        bgcolor="rgba(255,255,255,0.78)",
    )

    fig.update_traces(
        mode="markers",
        textposition="top right",
        textfont=dict(size=9, color="#374151"),
        marker=dict(size=8, line=dict(width=0.5, color="white")),
    )

    fig.update_layout(
        margin=dict(b=125),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                buttons=[
                    dict(label="Hide Names", method="update", args=[{"mode": "markers"}]),
                    dict(label="Show Target Names", method="update", args=[{"mode": "markers+text"}]),
                ],
                showactive=True,
                x=0,
                xanchor="left",
                y=-0.15,
                yanchor="top",
            )
        ],
    )

    return fig, metric_corr, qs_ar_col, the_research_col


def create_employability_gap(df_merged):
    if df_merged.empty:
        return empty_figure(
            "Distribution of the Employability Gap",
            "No matched THE/QS data available.",
        ), pd.DataFrame(), pd.DataFrame(), None, None

    qs_er_col = find_col_by_tokens(
        df_merged,
        [["er", "score"], ["employer", "reputation", "score"], ["employer", "reputation"]],
    )

    # Fallback only if the ER column does not exist.
    if qs_er_col is None:
        qs_er_col = find_col_by_tokens(
            df_merged,
            [["overall", "score"]],
            exclude={"overall_score"},
        )

    the_industry_col = "industry_impact" if "industry_impact" in df_merged.columns else find_col_by_tokens(
        df_merged,
        [["industry", "impact"], ["industry"]],
    )

    if qs_er_col is None or the_industry_col is None:
        return empty_figure(
            "Distribution of the Employability Gap",
            "Required QS employer or THE industry columns were not found.",
        ), pd.DataFrame(), pd.DataFrame(), qs_er_col, the_industry_col

    plot_df = df_merged.copy()
    plot_df[qs_er_col] = pd.to_numeric(plot_df[qs_er_col], errors="coerce")
    plot_df[the_industry_col] = pd.to_numeric(plot_df[the_industry_col], errors="coerce")
    plot_df = plot_df.dropna(subset=[qs_er_col, the_industry_col]).copy()

    if plot_df.empty:
        return empty_figure(
            "Distribution of the Employability Gap",
            "No valid employability / industry rows available.",
        ), pd.DataFrame(), pd.DataFrame(), qs_er_col, the_industry_col

    plot_df["z_qs"] = zscore_series(plot_df[qs_er_col])
    plot_df["z_the"] = zscore_series(plot_df[the_industry_col])
    plot_df["employability_gap"] = plot_df["z_qs"] - plot_df["z_the"]

    top_brand_power = plot_df.sort_values("employability_gap", ascending=False).head(5)
    top_hidden_engines = plot_df.sort_values("employability_gap", ascending=True).head(5)

    fig = px.histogram(
        plot_df,
        x="employability_gap",
        color="region_group",
        nbins=60,
        marginal="rug",
        hover_name="display_university",
        hover_data=["country"],
        title="Distribution of the Employability Gap, Standardized Z-Scores",
        labels={
            "employability_gap": "Gap: Positive = Brand Dominant | Negative = Industry Dominant",
            "region_group": "Geopolitical Region",
        },
        template="plotly_white",
        color_discrete_map=REGION_COLORS,
        height=720,
        category_orders={"region_group": REGION_ORDER},
    )

    fig.add_vline(
        x=0,
        line_dash="dash",
        line_color="#dc2626",
        annotation_text="Balanced Profile",
    )

    fig.update_layout(barmode="stack")

    return fig, top_brand_power, top_hidden_engines, qs_er_col, the_industry_col


def create_size_bias(df_merged):
    if df_merged.empty or "student_population" not in df_merged.columns:
        return empty_figure(
            "Size Bias Analysis",
            "No student population data available.",
        ), np.nan, np.nan

    plot_df = df_merged.copy()
    plot_df["rank"] = pd.to_numeric(plot_df["rank"], errors="coerce")
    plot_df["qs_rank"] = pd.to_numeric(plot_df["qs_rank"], errors="coerce")
    plot_df["student_population"] = pd.to_numeric(plot_df["student_population"], errors="coerce")

    plot_df["rank_advantage_qs"] = plot_df["rank"] - plot_df["qs_rank"]
    plot_df = plot_df.dropna(subset=["rank_advantage_qs", "student_population"]).copy()
    plot_df = plot_df[plot_df["student_population"] > 0].copy()

    if plot_df.empty:
        return empty_figure(
            "Size Bias Analysis",
            "No valid rank advantage / population rows available.",
        ), np.nan, np.nan

    plot_df["display_name"] = plot_df.apply(
        lambda x: x["display_university"] if x["rank"] <= 200 else "",
        axis=1,
    )

    fig = px.scatter(
        plot_df,
        x="student_population",
        y="rank_advantage_qs",
        color="region_group",
        hover_name="display_university",
        text="display_name",
        hover_data=["country", "rank", "qs_rank"],
        title="Size Bias Analysis: Student Population vs. QS Rank Advantage",
        labels={
            "student_population": "Student Population, Log Scale",
            "rank_advantage_qs": "Rank Advantage in QS: Positive = QS Favors",
            "region_group": "Geopolitical Region",
        },
        log_x=True,
        template="plotly_white",
        color_discrete_map=REGION_COLORS,
        height=820,
        category_orders={"region_group": REGION_ORDER},
    )

    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="#dc2626",
        annotation_text="Neutral Rank",
    )

    fig.update_traces(
        mode="markers",
        textposition="top right",
        textfont=dict(size=8, color="#374151"),
        marker=dict(size=8, line=dict(width=0.5, color="white")),
    )

    fig.update_layout(
        margin=dict(b=125),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                buttons=[
                    dict(label="Hide Names", method="update", args=[{"mode": "markers"}]),
                    dict(label="Show Top 200 Names", method="update", args=[{"mode": "markers+text"}]),
                ],
                showactive=True,
                x=0,
                xanchor="left",
                y=-0.15,
                yanchor="top",
            )
        ],
    )

    large = plot_df[plot_df["student_population"] > 20000]
    small = plot_df[plot_df["student_population"] <= 20000]

    large_avg = large["rank_advantage_qs"].mean() if not large.empty else np.nan
    small_avg = small["rank_advantage_qs"].mean() if not small.empty else np.nan

    return fig, large_avg, small_avg


def create_gdp_scatter(df_merged):
    if df_merged.empty:
        return empty_figure(
            "Economic Power vs. Academic Standing",
            "No matched university data available.",
        ), np.nan

    log("Fetching World Bank GDP per capita data")

    url = "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.CD?format=json&per_page=300&date=2023"

    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()[1]
        gdp_api_map = {
            entry["country"]["value"]: entry["value"]
            for entry in data
            if entry.get("value") is not None
        }
    except Exception as exc:
        log(f"World Bank API failed: {exc}")
        gdp_api_map = {}

    name_fixer = {
        "United States": "United States",
        "United Kingdom": "United Kingdom",
        "Korea, Rep.": "South Korea",
        "Hong Kong SAR, China": "Hong Kong",
        "Russian Federation": "Russia",
        "Egypt, Arab Rep.": "Egypt",
        "Iran, Islamic Rep.": "Iran",
        "Turkiye": "Turkey",
        "Singapore": "Singapore",
        "China": "China",
        "Japan": "Japan",
        "Germany": "Germany",
        "Switzerland": "Switzerland",
        "Australia": "Australia",
        "Canada": "Canada",
        "Netherlands": "Netherlands",
        "Sweden": "Sweden",
        "Luxembourg": "Luxembourg",
        "Ireland": "Ireland",
    }

    for wb_name, times_name in name_fixer.items():
        if wb_name in gdp_api_map:
            gdp_api_map[times_name] = gdp_api_map[wb_name]

    plot_source = df_merged.copy()
    plot_source["country_gdp"] = plot_source["country"].map(gdp_api_map)

    country_perf = (
        plot_source.groupby("country")[["rank", "country_gdp"]]
        .median()
        .dropna()
        .reset_index()
    )

    if country_perf.empty:
        return empty_figure(
            "Economic Power vs. Academic Standing",
            "No GDP data could be matched to countries.",
        ), np.nan

    country_perf["granular_region"] = country_perf["country"].apply(get_granular_region)

    labels = [
        "United States", "United Kingdom", "China", "Singapore",
        "Switzerland", "Germany", "Australia", "Canada", "Japan",
        "South Korea", "Hong Kong", "France", "Netherlands",
        "Sweden", "India", "Brazil", "South Africa", "Luxembourg",
    ]

    country_perf["display_label"] = country_perf["country"].apply(
        lambda x: x if x in labels else ""
    )

    fig = px.scatter(
        country_perf,
        x="country_gdp",
        y="rank",
        color="granular_region",
        hover_name="country",
        size="country_gdp",
        text="display_label",
        title="Economic Power, World Bank API Data, vs. Academic Standing",
        labels={
            "country_gdp": "GDP per Capita, USD, 2023",
            "rank": "Median THE Rank, Lower is Better",
            "granular_region": "Geopolitical Region",
        },
        hover_data={"display_label": False, "country_gdp": ":.0f"},
        template="plotly_white",
        color_discrete_sequence=PRISM,
        height=820,
    )

    fig.update_traces(textposition="middle right", textfont=dict(size=11, color="#111827"))

    max_gdp = country_perf["country_gdp"].max()
    fig.update_xaxes(range=[-5000, max_gdp * 1.15])
    fig.update_yaxes(autorange="reversed")

    gdp_rank_corr = country_perf["country_gdp"].corr(country_perf["rank"])

    return fig, gdp_rank_corr


def load_subject_data(subjects_csv):
    if not subjects_csv:
        candidates = [
            "data/the_subjects_2026.csv",
            "../data/the_subjects_2026.csv",
            "the_subjects_2026.csv",
        ]
        subjects_csv = next((p for p in candidates if os.path.exists(p)), None)

    if not subjects_csv or not os.path.exists(subjects_csv):
        log("Subject ranking CSV not found. Subject charts will be placeholders.")
        return None

    log(f"Loading THE subject data: {subjects_csv}")

    try:
        df = pd.read_csv(subjects_csv, sep=";", decimal=",")
        if df.shape[1] == 1:
            df = pd.read_csv(subjects_csv)
    except Exception:
        df = pd.read_csv(subjects_csv)

    return df


def prepare_subject_pivot(subjects_csv):
    df_subs = load_subject_data(subjects_csv)

    if df_subs is None:
        return None

    df_subs = df_subs.copy()

    # Normalize expected important columns lightly.
    col_map = {normalize_column_name(c): c for c in df_subs.columns}

    required_norm = ["rank", "subject", "name", "location"]
    if not all(c in col_map for c in required_norm):
        log("Subject data missing rank/subject/name/location columns.")
        return None

    rank_col = col_map["rank"]
    subject_col = col_map["subject"]
    name_col = col_map["name"]
    location_col = col_map["location"]

    df_subs["rank_bucket"] = df_subs[rank_col].apply(parse_rank_value)

    score_norms = [
        "scores_teaching",
        "scores_research",
        "scores_citations",
        "scores_international_outlook",
        "scores_industry_income",
    ]

    score_cols = []
    for norm in score_norms:
        if norm in col_map:
            original = col_map[norm]
            df_subs[original] = (
                df_subs[original]
                .astype(str)
                .str.replace(",", ".", regex=False)
            )
            df_subs[original] = pd.to_numeric(df_subs[original], errors="coerce")
            score_cols.append(original)

    if score_cols:
        df_subs["tie_breaker_score"] = df_subs[score_cols].sum(axis=1)
    else:
        df_subs["tie_breaker_score"] = 0

    df_subs["rank_bucket_sort"] = df_subs["rank_bucket"].fillna(999999)

    df_subs = df_subs.sort_values(
        by=[subject_col, "rank_bucket_sort", "tie_breaker_score"],
        ascending=[True, True, False],
    )

    df_subs["continuous_rank"] = df_subs.groupby(subject_col).cumcount() + 1

    subjects_needed = ["arts-and-humanities", "engineering"]

    df_arts_eng = df_subs[df_subs[subject_col].isin(subjects_needed)].copy()

    if df_arts_eng.empty:
        log("Subject data has no arts-and-humanities / engineering rows.")
        return None

    df_pivot = (
        df_arts_eng.pivot_table(
            index=[name_col, location_col],
            columns=subject_col,
            values="continuous_rank",
        )
        .reset_index()
        .rename(columns={name_col: "name", location_col: "location"})
    )

    if not all(s in df_pivot.columns for s in subjects_needed):
        log("Subject pivot missing one of the required subjects.")
        return None

    df_pivot = df_pivot.dropna(subset=subjects_needed).copy()
    df_pivot["region_group"] = df_pivot["location"].apply(get_region)
    df_pivot["granular_region"] = df_pivot["location"].apply(get_granular_region)

    return df_pivot


def create_domain_strategy(df_pivot):
    if df_pivot is None or df_pivot.empty:
        return empty_figure(
            "Domain Strategy: Engineering vs. Arts & Humanities",
            "Subject ranking data was not found or could not be prepared.",
        )

    plot_df = df_pivot.copy()
    plot_df["display_name"] = plot_df.apply(
        lambda x: x["name"] if (x["arts-and-humanities"] <= 150 or x["engineering"] <= 150) else "",
        axis=1,
    )

    fig = px.scatter(
        plot_df,
        x="arts-and-humanities",
        y="engineering",
        color="region_group",
        hover_name="name",
        text="display_name",
        hover_data=["location"],
        title="Domain Strategy: Engineering vs. Arts & Humanities, Top 1000",
        labels={
            "arts-and-humanities": "Arts Rank, Continuous",
            "engineering": "Engineering Rank, Continuous",
            "region_group": "Geopolitical Region",
        },
        template="plotly_white",
        color_discrete_map=REGION_COLORS,
        height=820,
        category_orders={"region_group": REGION_ORDER},
    )

    fig.update_xaxes(range=[1000, 0])
    fig.update_yaxes(range=[1000, 0])

    fig.add_shape(
        type="line",
        x0=0,
        y0=0,
        x1=1000,
        y1=1000,
        line=dict(color="#dc2626", dash="dash"),
    )

    fig.update_traces(
        mode="markers",
        textposition="top right",
        textfont=dict(size=8, color="#374151"),
        marker=dict(size=8, line=dict(width=0.5, color="white")),
    )

    fig.update_layout(
        margin=dict(b=125),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                buttons=[
                    dict(label="Hide Names", method="update", args=[{"mode": "markers"}]),
                    dict(label="Show Selected Names", method="update", args=[{"mode": "markers+text"}]),
                ],
                showactive=True,
                x=0,
                xanchor="left",
                y=-0.15,
                yanchor="top",
            )
        ],
    )

    return fig


def create_granular_domain_strategy(df_pivot):
    if df_pivot is None or df_pivot.empty:
        return empty_figure(
            "Micro-Geopolitics: Granular Domain Strategy",
            "Subject ranking data was not found or could not be prepared.",
        )

    plot_df = df_pivot.copy()
    plot_df["display_name"] = plot_df.apply(
        lambda x: x["name"] if (x["arts-and-humanities"] <= 120 or x["engineering"] <= 120) else "",
        axis=1,
    )

    fig = px.scatter(
        plot_df,
        x="arts-and-humanities",
        y="engineering",
        color="granular_region",
        hover_name="name",
        text="display_name",
        hover_data=["location"],
        title="Micro-Geopolitics: Granular Domain Strategy, Top 1000",
        labels={
            "arts-and-humanities": "Arts Rank, Continuous",
            "engineering": "Engineering Rank, Continuous",
            "granular_region": "Geopolitical Region",
        },
        template="plotly_white",
        color_discrete_sequence=PRISM,
        height=820,
    )

    fig.update_xaxes(range=[1000, 0])
    fig.update_yaxes(range=[1000, 0])

    fig.add_shape(
        type="line",
        x0=0,
        y0=0,
        x1=1000,
        y1=1000,
        line=dict(color="#dc2626", dash="dash"),
    )

    fig.update_traces(
        mode="markers",
        textposition="top right",
        textfont=dict(size=8, color="#374151"),
        marker=dict(size=8, line=dict(width=0.5, color="white")),
    )

    fig.update_layout(
        margin=dict(b=125),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                buttons=[
                    dict(label="Hide Names", method="update", args=[{"mode": "markers"}]),
                    dict(label="Show Selected Names", method="update", args=[{"mode": "markers+text"}]),
                ],
                showactive=True,
                x=0,
                xanchor="left",
                y=-0.15,
                yanchor="top",
            )
        ],
    )

    return fig


def create_europe_case_study(df_pivot):
    if df_pivot is None or df_pivot.empty:
        return empty_figure(
            "European Case Study",
            "Subject ranking data was not found or could not be prepared.",
        )

    european_countries = [
        "United Kingdom", "Germany", "France", "Italy", "Spain",
        "Netherlands", "Switzerland", "Sweden", "Belgium",
        "Denmark", "Finland", "Norway", "Austria", "Ireland",
        "Portugal", "Poland", "Greece", "Czech Republic",
    ]

    df_europe = df_pivot[df_pivot["location"].isin(european_countries)].copy()

    if df_europe.empty:
        return empty_figure(
            "European Case Study",
            "No European rows available in subject ranking data.",
        )

    def get_eu_system(country):
        if country == "United Kingdom":
            return "United Kingdom"
        elif country == "Germany":
            return "Germany, TU & Excellence Model"
        elif country == "France":
            return "France, Grandes Écoles & ComUEs"
        elif country in ["Italy", "Spain", "Portugal", "Greece"]:
            return "Southern Europe, Historic Comprehensives"
        elif country in ["Netherlands", "Belgium", "Switzerland", "Austria"]:
            return "Western / Alpine Hubs"
        elif country in ["Sweden", "Denmark", "Finland", "Norway"]:
            return "Nordics"
        else:
            return "Eastern / Central Europe"

    df_europe["eu_system"] = df_europe["location"].apply(get_eu_system)
    df_europe["display_name"] = df_europe.apply(
        lambda x: x["name"] if (x["arts-and-humanities"] <= 120 or x["engineering"] <= 120) else "",
        axis=1,
    )

    fig = px.scatter(
        df_europe,
        x="arts-and-humanities",
        y="engineering",
        color="eu_system",
        hover_name="name",
        text="display_name",
        hover_data=["location"],
        title="European Case Study: National Strategies in Engineering vs. Arts",
        labels={
            "arts-and-humanities": "Arts Rank, Continuous",
            "engineering": "Engineering Rank, Continuous",
            "eu_system": "European System",
        },
        template="plotly_white",
        color_discrete_sequence=px.colors.qualitative.Bold,
        height=820,
    )

    fig.update_xaxes(range=[800, 0])
    fig.update_yaxes(range=[800, 0])

    fig.add_shape(
        type="line",
        x0=0,
        y0=0,
        x1=800,
        y1=800,
        line=dict(color="#6b7280", dash="dash"),
    )

    fig.update_traces(
        mode="markers",
        textposition="top right",
        textfont=dict(size=8, color="#374151"),
        marker=dict(size=8, line=dict(width=0.5, color="white")),
    )

    fig.update_layout(
        margin=dict(b=125),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                buttons=[
                    dict(label="Hide Names", method="update", args=[{"mode": "markers"}]),
                    dict(label="Show Selected Names", method="update", args=[{"mode": "markers+text"}]),
                ],
                showactive=True,
                x=0,
                xanchor="left",
                y=-0.15,
                yanchor="top",
            )
        ],
    )

    return fig


# ============================================================
# HTML EXPORT
# ============================================================

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />

  <title>Prestige vs. Performance | University Rankings Dashboard</title>

  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">

  <style>
    :root {
      --bg: #f6f8fc;
      --card: rgba(255,255,255,0.88);
      --solid: #ffffff;
      --text: #101828;
      --muted: #667085;
      --line: rgba(15,23,42,0.10);
      --blue: #2563eb;
      --purple: #7c3aed;
      --orange: #f97316;
      --green: #10b981;
      --red: #dc2626;
      --shadow: 0 24px 70px rgba(15,23,42,0.11);
      --soft-shadow: 0 12px 36px rgba(15,23,42,0.08);
      --radius-xl: 28px;
      --radius-lg: 20px;
    }

    * { box-sizing: border-box; }

    html { scroll-behavior: smooth; }

    body {
      margin: 0;
      font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 0% 0%, rgba(37,99,235,0.18), transparent 30rem),
        radial-gradient(circle at 100% 0%, rgba(124,58,237,0.16), transparent 32rem),
        linear-gradient(180deg, #f8fafc 0%, #eef2f7 50%, #f8fafc 100%);
      line-height: 1.6;
    }

    a { color: inherit; text-decoration: none; }

    .page {
      width: min(1440px, calc(100% - 42px));
      margin: 0 auto;
    }

    .nav {
      position: sticky;
      top: 0;
      z-index: 20;
      backdrop-filter: blur(18px);
      background: rgba(248,250,252,0.82);
      border-bottom: 1px solid var(--line);
    }

    .nav-inner {
      width: min(1440px, calc(100% - 42px));
      margin: 0 auto;
      padding: 14px 0;
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: center;
    }

    .brand {
      display: flex;
      gap: 12px;
      align-items: center;
      font-weight: 800;
      letter-spacing: -0.035em;
      white-space: nowrap;
    }

    .brand-mark {
      width: 36px;
      height: 36px;
      border-radius: 13px;
      background: linear-gradient(135deg, var(--blue), var(--purple));
      box-shadow: 0 12px 28px rgba(79,70,229,0.35);
    }

    .nav-links {
      display: flex;
      gap: 7px;
      overflow-x: auto;
      padding-bottom: 2px;
    }

    .nav-links a {
      font-size: 13px;
      font-weight: 700;
      color: #475467;
      padding: 8px 11px;
      border-radius: 999px;
      white-space: nowrap;
    }

    .nav-links a:hover {
      color: #111827;
      background: rgba(15,23,42,0.06);
    }

    .hero {
      padding: 72px 0 32px;
    }

    .hero-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.38fr) minmax(340px, 0.62fr);
      gap: 26px;
    }

    .hero-card {
      position: relative;
      overflow: hidden;
      color: white;
      padding: 48px;
      border-radius: var(--radius-xl);
      border: 1px solid rgba(255,255,255,0.16);
      background:
        radial-gradient(circle at 84% 8%, rgba(96,165,250,0.38), transparent 24rem),
        linear-gradient(135deg, #0f172a, #1e293b 60%, #312e81);
      box-shadow: var(--shadow);
    }

    .eyebrow {
      display: inline-flex;
      padding: 7px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.12);
      border: 1px solid rgba(255,255,255,0.18);
      color: rgba(255,255,255,0.86);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .hero h1 {
      max-width: 960px;
      margin: 22px 0 18px;
      font-size: clamp(42px, 6vw, 76px);
      line-height: 0.96;
      letter-spacing: -0.065em;
    }

    .hero p {
      max-width: 860px;
      margin: 0;
      color: rgba(255,255,255,0.78);
      font-size: 18px;
    }

    .meta-card {
      padding: 28px;
      border-radius: var(--radius-xl);
      background: var(--card);
      border: 1px solid rgba(255,255,255,0.82);
      box-shadow: var(--soft-shadow);
      backdrop-filter: blur(18px);
    }

    .meta-card h3 {
      margin: 0 0 18px;
      font-size: 18px;
      letter-spacing: -0.025em;
    }

    .meta-item {
      padding: 0 0 14px;
      margin-bottom: 14px;
      border-bottom: 1px solid var(--line);
    }

    .meta-item:last-child {
      border-bottom: 0;
      margin-bottom: 0;
      padding-bottom: 0;
    }

    .meta-label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 4px;
    }

    .meta-value {
      font-weight: 700;
      color: #111827;
      font-size: 14px;
    }

    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin-top: 22px;
    }

    .kpi {
      padding: 22px;
      border-radius: var(--radius-lg);
      background: rgba(255,255,255,0.80);
      border: 1px solid rgba(255,255,255,0.84);
      box-shadow: 0 12px 32px rgba(15,23,42,0.06);
    }

    .kpi-number {
      font-size: 30px;
      font-weight: 800;
      letter-spacing: -0.05em;
      line-height: 1;
    }

    .kpi-label {
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 650;
    }

    section {
      scroll-margin-top: 96px;
    }

    .section, .viz-section {
      margin: 54px 0;
    }

    .section-header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 18px;
    }

    .kicker {
      color: var(--blue);
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.11em;
      margin-bottom: 8px;
    }

    h2 {
      margin: 0;
      color: #111827;
      font-size: clamp(28px, 4vw, 44px);
      line-height: 1.05;
      letter-spacing: -0.055em;
    }

    .subtitle {
      max-width: 800px;
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 16px;
    }

    .panel {
      background: var(--card);
      border: 1px solid rgba(255,255,255,0.84);
      border-radius: var(--radius-xl);
      box-shadow: var(--soft-shadow);
      backdrop-filter: blur(18px);
      overflow: hidden;
    }

    .panel-pad { padding: 28px; }

    .overview-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }

    .mini-card {
      padding: 22px;
      border-radius: var(--radius-lg);
      background: rgba(255,255,255,0.76);
      border: 1px solid var(--line);
    }

    .mini-card h3 {
      margin: 0 0 10px;
      color: #111827;
      letter-spacing: -0.025em;
    }

    .mini-card p, .mini-card li {
      color: #475467;
      font-size: 15px;
    }

    .mini-card ul {
      margin: 10px 0 0;
      padding-left: 18px;
    }

    .insight-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin: 18px 0;
    }

    .insight {
      position: relative;
      overflow: hidden;
      padding: 22px;
      border-radius: var(--radius-lg);
      background: rgba(255,255,255,0.84);
      border: 1px solid rgba(15,23,42,0.08);
      box-shadow: 0 12px 36px rgba(15,23,42,0.06);
    }

    .insight::before {
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      height: 5px;
      width: 100%;
      background: linear-gradient(90deg, var(--blue), var(--purple));
    }

    .insight strong {
      display: block;
      color: #111827;
      font-size: 15px;
      margin-bottom: 8px;
    }

    .insight span {
      color: #475467;
      font-size: 14px;
    }

    .chart-card {
      padding: 18px;
      border-radius: var(--radius-xl);
      background: var(--solid);
      border: 1px solid rgba(15,23,42,0.08);
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .plot-wrap {
      width: 100%;
      min-height: 520px;
    }

    .js-plotly-plot, .plotly-graph-div {
      width: 100% !important;
    }

    .story-card {
      margin-top: 16px;
      padding: 24px;
      border-radius: var(--radius-lg);
      border: 1px solid rgba(37,99,235,0.14);
      background: linear-gradient(135deg, rgba(239,246,255,0.92), rgba(255,255,255,0.94));
    }

    .story-card h3 {
      margin: 0 0 10px;
      color: #111827;
      letter-spacing: -0.03em;
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
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(37,99,235,0.08);
      color: #1d4ed8;
      font-size: 12px;
      font-weight: 800;
    }

    .conclusion-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }

    .callout {
      margin-top: 20px;
      padding: 32px;
      border-radius: var(--radius-xl);
      color: white;
      background: linear-gradient(135deg, #111827, #1e293b);
      box-shadow: var(--shadow);
    }

    .callout h2 {
      color: white;
      font-size: 34px;
    }

    .callout p {
      color: rgba(255,255,255,0.78);
      margin: 12px 0 0;
    }

    .bibliography {
      columns: 2;
      column-gap: 36px;
      color: #475467;
      font-size: 14px;
    }

    .bibliography li {
      break-inside: avoid;
      margin-bottom: 10px;
    }

    footer {
      padding: 46px 0 70px;
      color: var(--muted);
      font-size: 14px;
    }

    @media (max-width: 1100px) {
      .hero-grid, .overview-grid, .conclusion-grid {
        grid-template-columns: 1fr;
      }

      .kpi-grid, .insight-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .nav-inner {
        flex-direction: column;
        align-items: flex-start;
      }
    }

    @media (max-width: 720px) {
      .page, .nav-inner {
        width: min(100% - 24px, 1440px);
      }

      .hero-card {
        padding: 30px;
      }

      .kpi-grid, .insight-grid {
        grid-template-columns: 1fr;
      }

      .bibliography {
        columns: 1;
      }
    }
  </style>
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
        <a href="#drivers">Drivers</a>
        <a href="#prestige">Prestige Gap</a>
        <a href="#employability">Employability</a>
        <a href="#size">Size</a>
        <a href="#gdp">GDP</a>
        <a href="#domain">Domain</a>
        <a href="#eu">Europe</a>
        <a href="#conclusion">Conclusion</a>
      </div>
    </div>
  </nav>

  <main id="top" class="page">
    <header class="hero">
      <div class="hero-grid">
        <div class="hero-card">
          <div class="eyebrow">Global University Rankings Dashboard</div>
          <h1>Prestige vs. Performance</h1>
          <p>
            An interactive data visualization dashboard uncovering how reputation, research output,
            national wealth, institutional size, and domain strategy shape global university rankings.
          </p>
        </div>

        <aside class="meta-card">
          <h3>Project Details</h3>
          <div class="meta-item">
            <span class="meta-label">Course</span>
            <span class="meta-value">Data Visualisation [B-KUL-G0R04a], KU Leuven</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Audience</span>
            <span class="meta-value">University Strategic Planners & Higher Education Policymakers</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Team</span>
            <span class="meta-value">YIN Renlong, Victor Kao, Lei Pei, Szabó Gergely, Kawtar Darkaoui, Deborah Adelakun</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Updated</span>
            <span class="meta-value">01 May 2026 · Exported {{export_date}}</span>
          </div>
        </aside>
      </div>

      <div class="kpi-grid">
        <div class="kpi">
          <div class="kpi-number">{{records_count}}</div>
          <div class="kpi-label">THE ranking records cleaned</div>
        </div>
        <div class="kpi">
          <div class="kpi-number">{{matched_count}}</div>
          <div class="kpi-label">Universities matched between THE and QS</div>
        </div>
        <div class="kpi">
          <div class="kpi-number">{{rank_corr}}</div>
          <div class="kpi-label">THE-QS rank correlation</div>
        </div>
        <div class="kpi">
          <div class="kpi-number">{{gdp_corr}}</div>
          <div class="kpi-label">GDP per capita vs. median rank correlation</div>
        </div>
      </div>
    </header>

    <section id="overview" class="section">
      <div class="section-header">
        <div>
          <div class="kicker">Project Narrative</div>
          <h2>Why rankings need visual auditing</h2>
          <p class="subtitle">
            Global rankings compress diverse institutions into a single hierarchy. This dashboard
            uses interaction, comparison, and domain-level decomposition to expose where that hierarchy is biased.
          </p>
        </div>
      </div>

      <div class="panel panel-pad">
        <div class="overview-grid">
          <div class="mini-card">
            <h3>Motivation</h3>
            <p>
              Rankings influence funding, partnerships, academic branding, and talent flows.
              Yet reputation-heavy systems and research-heavy systems reward very different forms of excellence.
            </p>
          </div>
          <div class="mini-card">
            <h3>Visualization Objectives</h3>
            <ul>
              <li>Compare ranking methodologies through interactive scatter plots.</li>
              <li>Reveal longitudinal geopolitical shifts in the global Top 200.</li>
              <li>Connect academic standing with national economic context.</li>
              <li>Decompose overall ranking into domain-specific strategies.</li>
            </ul>
          </div>
          <div class="mini-card">
            <h3>Data Sources</h3>
            <ul>
              <li>THE World University Rankings 2016–2026</li>
              <li>QS World University Rankings 2026</li>
              <li>World Bank GDP per capita API</li>
              <li>THE Subject Rankings 2026</li>
            </ul>
          </div>
          <div class="mini-card">
            <h3>Design Approach</h3>
            <p>
              The page prioritizes interactive graphics, compact executive insights, and policy-oriented
              interpretation. Use legends, hover tooltips, and chart buttons to explore details on demand.
            </p>
          </div>
        </div>
      </div>
    </section>

    <section id="macro" class="viz-section">
      <div class="section-header">
        <div>
          <div class="kicker">Longitudinal Geopolitics</div>
          <h2>The Eastward Shift in the global Top 200</h2>
          <p class="subtitle">
            The Top 200 operates like a finite market: when one region gains seats, another must lose them.
          </p>
        </div>
      </div>

      <div class="insight-grid">
        <div class="insight">
          <strong>Zero-sum competition</strong>
          <span>The 100% stacked area chart treats elite ranking seats as a fixed geopolitical market.</span>
        </div>
        <div class="insight">
          <strong>Asia’s consistent rise</strong>
          <span>Major Asian economies gained seats with strong positive velocity over the decade.</span>
        </div>
        <div class="insight">
          <strong>Anglosphere erosion</strong>
          <span>US/UK-led dominance remains large, but its share has visibly compressed.</span>
        </div>
      </div>

      <div class="chart-card"><div class="plot-wrap">{{plot_macro}}</div></div>

      <div class="story-card">
        <h3>Policy insight</h3>
        <p>
          Historical prestige is no longer a sufficient defense against state-directed academic investment.
          Western policymakers must treat STEM infrastructure and research capacity as strategic assets.
        </p>
        <div class="tag-row">
          <span class="tag">Top 200 market share</span>
          <span class="tag">Regional velocity</span>
          <span class="tag">State-funded competition</span>
        </div>
      </div>
    </section>

    <section id="methodology" class="viz-section">
      <div class="section-header">
        <div>
          <div class="kicker">Methodological Divergence</div>
          <h2>Times Higher Education vs. QS</h2>
          <p class="subtitle">
            THE and QS agree broadly, but the disagreement reveals where methodology changes institutional prestige.
          </p>
        </div>
      </div>

      <div class="insight-grid">
        <div class="insight">
          <strong>Moderate-high agreement</strong>
          <span>The systems agree overall but leave meaningful room for divergence.</span>
        </div>
        <div class="insight">
          <strong>Anglosphere consensus</strong>
          <span>US, UK, and Australian universities tend to cluster closer to the diagonal agreement line.</span>
        </div>
        <div class="insight">
          <strong>Non-Western volatility</strong>
          <span>Asian and Rest-of-World institutions are more sensitive to reputation vs. research weighting.</span>
        </div>
      </div>

      <div class="chart-card"><div class="plot-wrap">{{plot_compare}}</div></div>
    </section>

    <section id="elite" class="viz-section">
      <div class="section-header">
        <div>
          <div class="kicker">Elite Volatility</div>
          <h2>The calcified top of global academia</h2>
          <p class="subtitle">
            A distribution view shows which elite institutions are structurally stable and which remain algorithmically volatile.
          </p>
        </div>
      </div>

      <div class="insight-grid">
        <div class="insight">
          <strong>Diamond core</strong>
          <span>Oxford, Stanford, Cambridge, and MIT show extremely low volatility across the decade.</span>
        </div>
        <div class="insight">
          <strong>Boundary instability</strong>
          <span>Outside the very top, minor metric shifts can trigger large rank movements.</span>
        </div>
        <div class="insight">
          <strong>Glass ceiling</strong>
          <span>The absolute pinnacle remains dominated by US and UK institutions.</span>
        </div>
      </div>

      <div class="chart-card"><div class="plot-wrap">{{plot_elite}}</div></div>

      <div class="story-card">
        <h3>Policy insight</h3>
        <p>
          For non-US/UK systems, targeting the global Top 5 may be inefficient.
          The more realistic intervention zone is the volatile Top 20–50 range.
        </p>
      </div>
    </section>

    <section id="drivers" class="viz-section">
      <div class="section-header">
        <div>
          <div class="kicker">Ranking Mechanics</div>
          <h2>What drives the THE overall score?</h2>
          <p class="subtitle">
            The correlation matrix reveals the internal center of gravity of the THE methodology.
          </p>
        </div>
      </div>

      <div class="insight-grid">
        <div class="insight">
          <strong>Research environment dominates</strong>
          <span>It is one of the strongest correlates of THE overall performance.</span>
        </div>
        <div class="insight">
          <strong>Research quality follows closely</strong>
          <span>Bibliometric performance is central to THE ranking success.</span>
        </div>
        <div class="insight">
          <strong>International outlook is weaker</strong>
          <span>Research strength can outweigh internationalization.</span>
        </div>
      </div>

      <div class="chart-card"><div class="plot-wrap">{{plot_corr}}</div></div>
    </section>

    <section id="prestige" class="viz-section">
      <div class="section-header">
        <div>
          <div class="kicker">Prestige vs. Performance</div>
          <h2>The reputation lag problem</h2>
          <p class="subtitle">
            QS reputation and THE research quality are related, but far from identical. This is where hidden excellence appears.
          </p>
        </div>
      </div>

      <div class="insight-grid">
        <div class="insight">
          <strong>Reputation is a lagging indicator</strong>
          <span>Historic brand recognition can trail behind or exceed current research performance.</span>
        </div>
        <div class="insight">
          <strong>Hidden gems</strong>
          <span>Some Asian and European institutions show strong research quality but weaker global brand recognition.</span>
        </div>
        <div class="insight">
          <strong>Old Guard advantage</strong>
          <span>Historic Anglosphere institutions often combine high output with inherited reputation.</span>
        </div>
      </div>

      <div class="chart-card"><div class="plot-wrap">{{plot_prestige}}</div></div>

      <div class="story-card">
        <h3>Strategic interpretation</h3>
        <p>
          Survey-heavy systems preserve the halo of historically famous universities,
          while research-heavy systems can detect rising technical powerhouses earlier.
        </p>
      </div>
    </section>

    <section id="employability" class="viz-section">
      <div class="section-header">
        <div>
          <div class="kicker">Utility vs. Prestige</div>
          <h2>The employability gap</h2>
          <p class="subtitle">
            Standardized gaps expose whether an institution is recognized more for its brand or for its industrial performance.
          </p>
        </div>
      </div>

      <div class="insight-grid">
        <div class="insight">
          <strong>Right-tail brand power</strong>
          <span>Historic universities often have disproportionate reputational capital.</span>
        </div>
        <div class="insight">
          <strong>Left-tail hidden engines</strong>
          <span>Technical institutions can show stronger industrial output than global recognition.</span>
        </div>
        <div class="insight">
          <strong>Balanced center</strong>
          <span>Many institutions sit near the zero line where reputation and utility signals align.</span>
        </div>
      </div>

      <div class="chart-card"><div class="plot-wrap">{{plot_employability}}</div></div>
    </section>

    <section id="size" class="viz-section">
      <div class="section-header">
        <div>
          <div class="kicker">Institutional Scale</div>
          <h2>Size bias and university growth strategy</h2>
          <p class="subtitle">
            Student population interacts with ranking methodology, but bigger is not automatically better.
          </p>
        </div>
      </div>

      <div class="insight-grid">
        <div class="insight">
          <strong>Boutique premium</strong>
          <span>Smaller universities can receive strong QS advantages when reputation and selectivity are high.</span>
        </div>
        <div class="insight">
          <strong>Volume engines</strong>
          <span>Large institutions can convert scale into research volume, which THE may reward.</span>
        </div>
        <div class="insight">
          <strong>Strategy matters</strong>
          <span>Growth must be aligned with the target ranking methodology.</span>
        </div>
      </div>

      <div class="chart-card"><div class="plot-wrap">{{plot_size}}</div></div>

      <div class="story-card">
        <h3>Policy insight</h3>
        <p>
          If the target is THE, scale and research volume matter. If the target is QS,
          selectivity, exclusivity, and global reputation management become more important.
        </p>
      </div>
    </section>

    <section id="gdp" class="viz-section">
      <div class="section-header">
        <div>
          <div class="kicker">Economic Augmentation</div>
          <h2>National wealth and academic standing</h2>
          <p class="subtitle">
            Live World Bank GDP per capita data adds macroeconomic context to ranking outcomes.
          </p>
        </div>
      </div>

      <div class="insight-grid">
        <div class="insight">
          <strong>Wealth helps</strong>
          <span>GDP per capita is strongly associated with better median university ranking.</span>
        </div>
        <div class="insight">
          <strong>China as outlier</strong>
          <span>China performs above what GDP per capita alone would predict.</span>
        </div>
        <div class="insight">
          <strong>Money is not sufficient</strong>
          <span>Small wealthy economies still need scale and deep research ecosystems.</span>
        </div>
      </div>

      <div class="chart-card"><div class="plot-wrap">{{plot_gdp}}</div></div>
    </section>

    <section id="domain" class="viz-section">
      <div class="section-header">
        <div>
          <div class="kicker">Domain Strategy</div>
          <h2>Engineering vs. Arts & Humanities</h2>
          <p class="subtitle">
            Decomposing subject rankings reveals that the comprehensive university model is a regional luxury, not a global default.
          </p>
        </div>
      </div>

      <div class="insight-grid">
        <div class="insight">
          <strong>Dimensionality reduction problem</strong>
          <span>Overall ranks hide whether universities are balanced generalists or domain specialists.</span>
        </div>
        <div class="insight">
          <strong>Matthew Effect</strong>
          <span>Historic institutions convert reputation into funding, talent, and more reputation.</span>
        </div>
        <div class="insight">
          <strong>Goodhart’s Law</strong>
          <span>Some systems appear optimized for STEM citations, patents, and industry output.</span>
        </div>
      </div>

      <div class="chart-card"><div class="plot-wrap">{{plot_domain}}</div></div>

      <div class="story-card">
        <h3>Regional strategy summary</h3>
        <p>
          The Anglosphere maintains balanced comprehensive titans. Asia and parts of Northern Europe pursue asymmetric
          STEM specialization. Emerging economies face a capital barrier in engineering.
        </p>
      </div>
    </section>

    <section id="granular" class="viz-section">
      <div class="section-header">
        <div>
          <div class="kicker">Micro-Geopolitics</div>
          <h2>Sub-regional academic strategies</h2>
          <p class="subtitle">
            Granular filtering shows that academic systems copy, specialize, or diverge according to national incentives.
          </p>
        </div>
      </div>

      <div class="insight-grid">
        <div class="insight">
          <strong>Institutional isomorphism</strong>
          <span>UK, Ireland, and Oceania often follow balanced diagonal patterns.</span>
        </div>
        <div class="insight">
          <strong>State-capital tech vanguard</strong>
          <span>Greater China and MENA show strong engineering-oriented asymmetry.</span>
        </div>
        <div class="insight">
          <strong>Capital barrier</strong>
          <span>Latin America and Sub-Saharan Africa often perform better in Arts than Engineering.</span>
        </div>
      </div>

      <div class="chart-card"><div class="plot-wrap">{{plot_granular}}</div></div>

      <div class="story-card">
        <h3>Data science note</h3>
        <p>
          Pure specialist institutions can disappear from comparative subject plots if they lack one required domain.
          This exposes a bias toward the Western comprehensive university model.
        </p>
      </div>
    </section>

    <section id="eu" class="viz-section">
      <div class="section-header">
        <div>
          <div class="kicker">European Case Study</div>
          <h2>The fractured European Higher Education Area</h2>
          <p class="subtitle">
            Europe promotes a shared higher education area, but the data reveals very different national funding models.
          </p>
        </div>
      </div>

      <div class="insight-grid">
        <div class="insight">
          <strong>France: algorithmic optimizers</strong>
          <span>Mergers and consortiums helped create larger, ranking-visible generalist profiles.</span>
        </div>
        <div class="insight">
          <strong>Germany & Nordics: industrial engines</strong>
          <span>Technical universities sit high in Engineering, reflecting export-driven STEM strategies.</span>
        </div>
        <div class="insight">
          <strong>UK: regulated generalists</strong>
          <span>Centralized evaluation encourages more balanced scaling across domains.</span>
        </div>
      </div>

      <div class="chart-card"><div class="plot-wrap">{{plot_eu}}</div></div>

      <div class="story-card">
        <h3>European policy insight</h3>
        <p>
          Europe should not force all institutions into one generalist template. Heritage universities and technical
          universities serve different strategic purposes and need differentiated funding tools.
        </p>
      </div>
    </section>

    <section id="conclusion" class="section">
      <div class="section-header">
        <div>
          <div class="kicker">Final Synthesis</div>
          <h2>Actionable policy insights</h2>
          <p class="subtitle">
            The dashboard points to four major realities for higher education planners.
          </p>
        </div>
      </div>

      <div class="conclusion-grid">
        <div class="mini-card">
          <h3>1. The Eastward Shift</h3>
          <p>
            Asian universities have structurally increased their presence in the global elite,
            challenging the historical Anglosphere monopoly.
          </p>
        </div>
        <div class="mini-card">
          <h3>2. Prestige vs. Performance</h3>
          <p>
            QS and THE reward different things. Reputation-heavy systems favor established brands,
            while research-heavy systems identify rising technical powerhouses earlier.
          </p>
        </div>
        <div class="mini-card">
          <h3>3. Wealth Helps, Strategy Matters</h3>
          <p>
            GDP per capita strongly correlates with performance, but coordinated state policy can outperform
            economic expectations.
          </p>
        </div>
        <div class="mini-card">
          <h3>4. Specialization Is Often Rational</h3>
          <p>
            Outside the US/UK elite, hyper-specialization in STEM or targeted domain niches may be more realistic
            than chasing the full comprehensive university model.
          </p>
        </div>
      </div>

      <div class="callout">
        <h2>Final recommendation</h2>
        <p>
          Policymakers outside the historic Anglosphere should avoid blindly copying the “Generalist Titan” model.
          The data suggests that focused investment, technical specialization, and strategic reputation-building
          are more viable paths into the global Top 100.
        </p>
      </div>
    </section>

    <section id="disclaimer" class="section">
      <div class="panel panel-pad">
        <div class="kicker">Methodological Disclaimer</div>
        <h2 style="font-size: 32px;">Interpret rankings with caution</h2>
        <p class="subtitle">
          Commercial rankings can be volatile, metric-sensitive, and sometimes disconnected from perceived academic reality.
          High performance may reflect genuine excellence, strategic optimization, or successful tailoring to specific indicators.
        </p>
      </div>
    </section>

    <section id="bibliography" class="section">
      <div class="panel panel-pad">
        <div class="kicker">References</div>
        <h2 style="font-size: 32px;">Bibliography</h2>
        <ol class="bibliography">
          <li>Bowman, N. A., & Bastedo, M. N. (2011). Anchoring effects in world university rankings. <em>Higher Education</em>, 61(4), 431–444.</li>
          <li>Cleveland, W. S., & McGill, R. (1984). Graphical perception. <em>Journal of the American Statistical Association</em>, 79(387), 531–554.</li>
          <li>Heer, J., & Shneiderman, B. (2012). Interactive dynamics for visual analysis. <em>Communications of the ACM</em>, 55(4), 45–54.</li>
          <li>Pietrucha, J. (2018). Country-specific determinants of world university rankings. <em>Scientometrics</em>, 114(3), 1129–1139.</li>
          <li>Shin, J. C., Toutkoushian, R. K., & Teichler, U. (Eds.). (2011). <em>University rankings: Theoretical basis, methodology and impacts on global higher education</em>. Springer.</li>
          <li>Yi, J. S., Kang, Y.-A., Stasko, J. T., & Jacko, J. A. (2007). Interaction in information visualization. <em>IEEE TVCG</em>, 13(6), 1224–1231.</li>
        </ol>
      </div>
    </section>

    <footer>
      <strong>Prestige vs. Performance:</strong> Visualizing Biases in Global University Rankings.
      Built with Python, Pandas, Plotly, and GitHub Pages.
    </footer>
  </main>
</body>
</html>
"""


def fig_to_div(fig):
    fig = polish_figure(fig)
    return pio.to_html(
        fig,
        include_plotlyjs=False,
        full_html=False,
        config=PLOT_CONFIG,
    )


def fmt_num(value, decimals=2):
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.{decimals}f}"


def build_dashboard_html(figures, metrics):
    html = HTML_TEMPLATE

    replacements = {
        "export_date": date.today().strftime("%d %b %Y"),
        "records_count": f"{metrics.get('records_count', 0):,}",
        "matched_count": f"{metrics.get('matched_count', 0):,}",
        "rank_corr": fmt_num(metrics.get("rank_corr"), 2),
        "gdp_corr": fmt_num(metrics.get("gdp_corr"), 2),
    }

    for key, value in replacements.items():
        html = html.replace("{{" + key + "}}", value)

    for key, fig in figures.items():
        html = html.replace("{{" + key + "}}", fig_to_div(fig))

    return html


# ============================================================
# MAIN
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate the Prestige vs. Performance university rankings dashboard."
    )

    parser.add_argument(
        "--times-csv",
        default=None,
        help="Optional local CSV path for THE rankings. If omitted, Kaggle download is used.",
    )

    parser.add_argument(
        "--qs-csv",
        default=None,
        help="Optional local CSV path for QS 2026 rankings. If omitted, Kaggle download is used.",
    )

    parser.add_argument(
        "--subjects-csv",
        default=None,
        help="Optional local CSV path for THE Subject Rankings 2026.",
    )

    parser.add_argument(
        "--output-dir",
        default="dashboard",
        help="Output directory for index.html. Default: dashboard",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    log("Starting standalone dashboard generation")
    log("This avoids the Jupyter 'Invalid string length' save problem.")

    os.makedirs(args.output_dir, exist_ok=True)

    # 1. Load core datasets
    df_times = load_times_data(args.times_csv)
    df_qs = load_qs_data(args.qs_csv)
    df_merged = merge_times_qs(df_times, df_qs)

    # 2. Create figures
    log("Creating visualization figures")

    fig_macro, macro_stats = create_macro_area(df_times)
    fig_compare, rank_corr = create_compare_scatter(df_merged)
    fig_elite, elite_volatility = create_elite_box(df_times)
    fig_corr, sorted_corr = create_correlation_heatmap(df_times)
    fig_prestige, prestige_corr, qs_ar_col, the_research_col = create_prestige_vs_performance(df_merged)
    fig_employability, top_brand, top_hidden, qs_er_col, the_industry_col = create_employability_gap(df_merged)
    fig_size, large_avg, small_avg = create_size_bias(df_merged)
    fig_gdp, gdp_corr = create_gdp_scatter(df_merged)

    df_pivot = prepare_subject_pivot(args.subjects_csv)
    fig_domain = create_domain_strategy(df_pivot)
    fig_granular = create_granular_domain_strategy(df_pivot)
    fig_eu = create_europe_case_study(df_pivot)

    figures = {
        "plot_macro": fig_macro,
        "plot_compare": fig_compare,
        "plot_elite": fig_elite,
        "plot_corr": fig_corr,
        "plot_prestige": fig_prestige,
        "plot_employability": fig_employability,
        "plot_size": fig_size,
        "plot_gdp": fig_gdp,
        "plot_domain": fig_domain,
        "plot_granular": fig_granular,
        "plot_eu": fig_eu,
    }

    metrics = {
        "records_count": len(df_times),
        "matched_count": len(df_merged),
        "rank_corr": rank_corr,
        "gdp_corr": gdp_corr,
    }

    # 3. Export HTML
    log("Building HTML dashboard")
    html = build_dashboard_html(figures, metrics)

    output_path = os.path.join(args.output_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 4. Console summaries
    log("Dashboard export complete")
    log(f"Output file: {output_path}")

    print("\n================ SUMMARY ================")
    print(f"THE rows cleaned: {len(df_times):,}")
    print(f"THE/QS matched universities: {len(df_merged):,}")
    print(f"THE/QS rank correlation: {fmt_num(rank_corr, 3)}")
    print(f"GDP/rank correlation: {fmt_num(gdp_corr, 3)}")

    print("\n--- Macro region velocity ---")
    try:
        print(macro_stats.to_string(index=False))
    except Exception:
        print("Macro stats unavailable.")

    print("\n--- THE overall score correlations ---")
    try:
        print(sorted_corr.to_string())
    except Exception:
        print("Correlation summary unavailable.")

    print("\n--- Prestige vs. Performance ---")
    print(f"QS reputation column used: {qs_ar_col}")
    print(f"THE research column used: {the_research_col}")
    print(f"Correlation: {fmt_num(prestige_corr, 3)}")

    print("\n--- Employability Gap ---")
    print(f"QS employer/reputation column used: {qs_er_col}")
    print(f"THE industry column used: {the_industry_col}")

    if not top_brand.empty:
        print("\nTop Brand-Power Outliers:")
        cols = ["display_university", "country", "employability_gap"]
        print(top_brand[cols].to_string(index=False))

    if not top_hidden.empty:
        print("\nTop Hidden-Engine Outliers:")
        cols = ["display_university", "country", "employability_gap"]
        print(top_hidden[cols].to_string(index=False))

    print("\n--- Size Bias ---")
    print(f"Average QS advantage, large universities >20k: {fmt_num(large_avg, 2)}")
    print(f"Average QS advantage, small universities <=20k: {fmt_num(small_avg, 2)}")

    print("\nNow open:")
    print(f"  {output_path}")
    print("\nFor GitHub Pages, upload this file as index.html to your repository root.")
    print("========================================\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(1)
    except Exception as exc:
        print("\nERROR:", exc)
        sys.exit(1)