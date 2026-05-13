"""GBFS Audit Catalogue -- research dashboard.

Companion to Fossé & Pallares (2026), Computer Standards & Interfaces.

Run locally :
    streamlit run app/streamlit_app.py

Visual identity mirrors the bikeshare-data-explorer dashboard
(dark sidebar, light academic main content, primary blue #1A6FBF,
abstract box, numbered sections, metric cards).
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit_pipeline import ANOMALY_CLASSES, load_catalogue, load_summary  # noqa: E402

# Academic matplotlib style, aligned with the paper figures
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Inter", "Helvetica Neue", "Helvetica", "Arial",
                          "DejaVu Sans"],
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#404040",
    "axes.linewidth": 0.6,
    "axes.labelcolor": "#404040",
    "xtick.color": "#404040",
    "ytick.color": "#404040",
    "grid.color": "#E5E5E5",
    "grid.linewidth": 0.5,
    "figure.dpi": 110,
})

NAVY = "#1A6FBF"
NAVY_DARK = "#15538f"
ACCENT = "#C0392B"
MUTED = "#9DBADD"


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="GBFS Audit Catalogue",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/rohanfosse/gbfs-audit-catalogue/issues",
        "Report a bug": "https://github.com/rohanfosse/gbfs-audit-catalogue/issues/new",
        "About": (
            "GBFS Audit Catalogue v1.0  ·  "
            "Fossé & Pallares (2026), Computer Standards & Interfaces."
        ),
    },
)


# ---------------------------------------------------------------------------
# Shared academic CSS (mirrors bikeshare-data-explorer/utils/styles.py)
# ---------------------------------------------------------------------------

_CSS = """
<style>
/* === MAIN CONTENT ====================================================== */

.block-container {
    padding-top: 1.6rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 1240px;
}

/* H1 -- main title */
h1 {
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    color: #1A2332 !important;
    letter-spacing: -0.01em !important;
    margin-bottom: 0.2rem !important;
    border-bottom: 2px solid #1A6FBF !important;
    padding-bottom: 0.35rem !important;
}

/* H2 -- section subtitles */
h2 {
    font-size: 1.08rem !important;
    font-weight: 600 !important;
    color: #1A2332 !important;
    border-bottom: 1px solid #e8edf3 !important;
    padding-bottom: 0.2rem !important;
    margin-top: 0.6rem !important;
}

/* H3 -- numbered subsection headers */
h3 {
    font-size: 0.93rem !important;
    font-weight: 600 !important;
    color: #1A6FBF !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    margin-top: 0.5rem !important;
}

p, li, label { font-size: 0.93rem; line-height: 1.55; color: #2c3e50; }
.muted { color: #5a7a96; }

hr {
    border: none !important;
    border-top: 1px solid #e8edf3 !important;
    margin: 1.1rem 0 !important;
}

/* === SIDEBAR (DARK) ==================================================== */

[data-testid="stSidebar"] {
    background-color: #1B2635 !important;
}

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] span {
    color: #7a9bb8 !important;
    font-size: 0.82rem !important;
}

[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #c2d6e8 !important;
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.13em !important;
    border-bottom: 1px solid #2a3f58 !important;
    padding-bottom: 0.25rem !important;
    margin-bottom: 0.4rem !important;
    font-weight: 600 !important;
    border-top: none !important;
}

[data-testid="stSidebar"] hr {
    border-top-color: #2a3f58 !important;
    margin: 0.7rem 0 !important;
}

[data-testid="stSidebar"] label {
    color: #8aadc6 !important;
    font-size: 0.79rem !important;
}

[data-testid="stSidebar"] a {
    color: #7a9bb8 !important;
    text-decoration: none !important;
}
[data-testid="stSidebar"] a:hover {
    color: #5ab4e8 !important;
    text-decoration: underline !important;
}

[data-testid="stSidebar"] code {
    background: #2a3f58 !important;
    color: #c2d6e8 !important;
    font-size: 0.74rem !important;
    padding: 0.08rem 0.35rem !important;
    border-radius: 3px !important;
}

[data-testid="stSidebarNavItems"],
[data-testid="stSidebarNavSeparator"],
[data-testid="stSidebarNavLink"] { display: none !important; }

/* === METRIC CARDS ====================================================== */

[data-testid="metric-container"] {
    border: 1px solid #e4ecf3 !important;
    border-radius: 6px !important;
    padding: 0.55rem 0.9rem !important;
    background: #f8fafd !important;
    box-shadow: 0 1px 4px rgba(26, 35, 50, 0.05) !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    color: #1A2332 !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.66rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    color: #6b8aaa !important;
}

/* === TABS ============================================================== */

.stTabs [data-baseweb="tab-list"] {
    gap: 0.2rem;
    border-bottom: 1px solid #e8edf3;
    margin-bottom: 0.4rem;
}
.stTabs [data-baseweb="tab"] {
    height: 36px;
    padding: 0 1.1rem;
    font-weight: 500;
    font-size: 0.88rem;
    color: #5a7a96;
    background-color: transparent;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #1A6FBF;
    border-bottom: 2px solid #1A6FBF;
}

/* === CODE BLOCKS ======================================================= */

[data-testid="stCodeBlock"] {
    border-radius: 5px;
    border: 1px solid #e4ecf3;
    background: #f8fafd !important;
    font-size: 0.82rem !important;
}

/* === TABLES =========================================================== */

[data-testid="stDataFrame"] {
    border-radius: 6px;
    border: 1px solid #e4ecf3;
}
[data-testid="stDataFrame"] thead th {
    background-color: #eaf1fb !important;
    color: #1A6FBF !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

/* === BUTTONS =========================================================== */

.stDownloadButton button, .stButton button {
    border: 1px solid #1A6FBF !important;
    background-color: #1A6FBF !important;
    color: white !important;
    font-weight: 500 !important;
    border-radius: 5px !important;
    padding: 0.35rem 1.0rem !important;
    font-size: 0.86rem !important;
}
.stDownloadButton button:hover, .stButton button:hover {
    background-color: #15538f !important;
    border-color: #15538f !important;
}

/* === MULTISELECT / SELECT ============================================== */

.stMultiSelect [data-baseweb="tag"] {
    background: #eaf1fb !important;
    color: #1A6FBF !important;
    border: 1px solid #c4d8f0 !important;
    border-radius: 3px !important;
    font-size: 0.78rem !important;
}

/* === ANOMALY CLASS CARDS =============================================== */

.cls-card {
    border: 1px solid #e4ecf3;
    border-radius: 5px;
    padding: 0.65rem 0.9rem;
    margin-bottom: 0.45rem;
    background: #f8fafd;
    display: flex;
    gap: 0.85rem;
    align-items: flex-start;
}
.cls-card .code {
    font-family: ui-monospace, Menlo, Consolas, monospace;
    font-weight: 700;
    color: #1A6FBF;
    background: #eaf1fb;
    border: 1px solid #c4d8f0;
    padding: 0.15rem 0.5rem;
    border-radius: 3px;
    font-size: 0.85rem;
    flex-shrink: 0;
    min-width: 2.4rem;
    text-align: center;
    line-height: 1.4;
}
.cls-card .name {
    font-weight: 600;
    color: #1A2332;
    font-size: 0.92rem;
}
.cls-card .sig {
    color: #5a7a96;
    font-size: 0.83rem;
    margin-top: 0.12rem;
}
</style>
"""

st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers (mirror utils/styles.py)
# ---------------------------------------------------------------------------

def abstract_box(text: str, findings: list[tuple[str, str]] | None = None) -> None:
    """Research-paper abstract box with blue left border and chip findings."""
    chips_html = ""
    if findings:
        chips = " ".join(
            f'<span style="display:inline-block; background:#eaf1fb; '
            f'border:1px solid #c4d8f0; border-radius:20px; '
            f'padding:0.18rem 0.72rem; margin:0.15rem 0.18rem 0 0; '
            f'font-size:0.76rem; white-space:nowrap; vertical-align:middle;">'
            f'<b style="color:#1A6FBF;">{v}</b>'
            f'<span style="color:#5a7a96; margin-left:0.32rem;">{lbl}</span></span>'
            for v, lbl in findings
        )
        chips_html = (
            f'<div style="margin-top:0.8rem; padding-top:0.62rem; '
            f'border-top:1px solid #d0e4f5; line-height:2;">{chips}</div>'
        )
    st.markdown(
        f"""
        <div style="
            border-left: 3px solid #1A6FBF;
            background: #f4f8fc;
            padding: 0.85rem 1.3rem 0.75rem;
            border-radius: 0 5px 5px 0;
            margin: 0.4rem 0 1.4rem 0;
            font-size: 0.91rem;
            line-height: 1.65;
            color: #2c3e50;
        ">
            <span style="font-weight:600; color:#1A6FBF; font-size:0.72rem;
                         text-transform:uppercase; letter-spacing:0.08em;">
                Abstract
            </span><br/>
            {text}
            {chips_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section(number: int | str, title: str) -> None:
    """Numbered section header, research-paper style."""
    st.markdown(f"### {number}. {title}")


# ---------------------------------------------------------------------------
# Inline academic figures (matplotlib, cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def fig_anomaly_incidence() -> plt.Figure:
    """Side-by-side bars: FR vs Global incidence per class A1..A7."""
    classes = ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    fr = [14, 3, 8, 4, 5, 0, 19]
    glob = [46, 48, 33, 81, 17, 14, 215]
    x = np.arange(len(classes))
    w = 0.38
    fig, ax = plt.subplots(figsize=(6.4, 2.7))
    b1 = ax.bar(x - w / 2, fr, width=w, color=NAVY,
                 edgecolor="white", linewidth=0.5,
                 label="French corpus (123 systems)")
    b2 = ax.bar(x + w / 2, glob, width=w, color=MUTED,
                 edgecolor="white", linewidth=0.5,
                 label="Global catalogue (1,509 systems)")
    for rect, v in zip(b1, fr):
        if v:
            ax.text(rect.get_x() + w / 2, v + 5, str(v),
                    ha="center", va="bottom", fontsize=7, color=NAVY_DARK)
    for rect, v in zip(b2, glob):
        ax.text(rect.get_x() + w / 2, v + 5, str(v),
                ha="center", va="bottom", fontsize=7, color="#5a7a96")
    ax.set_xticks(x)
    ax.set_xticklabels(classes)
    ax.set_ylabel("Systems flagged")
    ax.set_ylim(0, max(glob) * 1.18)
    ax.grid(True, axis="y", alpha=0.45)
    ax.legend(frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.22), ncol=2)
    fig.tight_layout()
    return fig


@st.cache_data(ttl=3600)
def fig_confidence_distribution(audit_confidence: pd.Series) -> plt.Figure:
    """Stacked horizontal bar of audit_confidence proportions."""
    counts = audit_confidence.value_counts().reindex(
        ["high", "medium", "low"], fill_value=0
    )
    total = counts.sum()
    fig, ax = plt.subplots(figsize=(6.4, 0.9))
    palette = {"high": NAVY, "medium": MUTED, "low": "#D7E3F2"}
    left = 0
    for tier in ["high", "medium", "low"]:
        v = counts[tier]
        ax.barh(0, v, left=left, color=palette[tier],
                edgecolor="white", linewidth=0.6,
                label=f"{tier} ({v:,}, {100 * v / total:.1f}%)")
        if v / total > 0.04:
            ax.text(left + v / 2, 0, f"{tier}\n{100 * v / total:.1f}%",
                    ha="center", va="center", color="white",
                    fontsize=8, fontweight=600)
        left += v
    ax.set_xlim(0, total)
    ax.set_yticks([])
    ax.set_xlabel("Stations")
    ax.spines["left"].set_visible(False)
    ax.grid(False)
    ax.legend(frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.55), ncol=3, fontsize=8)
    fig.tight_layout()
    return fig


@st.cache_data(ttl=3600)
def fig_operator_anomaly_rates(gs_df: pd.DataFrame) -> plt.Figure:
    """Top-10 operators by station count, with A3 / A7 rates."""
    op = (
        gs_df.groupby("operator_name")
              .agg(n=("uid", "size"),
                   A3=("flag_A3", "mean"),
                   A7=("flag_A7", "mean"))
              .sort_values("n", ascending=False)
              .head(10)
              .sort_values("n", ascending=True)
    )
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    y = np.arange(len(op))
    h = 0.38
    ax.barh(y + h / 2, op["A3"] * 100, height=h, color=NAVY,
            edgecolor="white", linewidth=0.5,
            label="A3 (structural over-capacity)")
    ax.barh(y - h / 2, op["A7"] * 100, height=h, color=ACCENT,
            edgecolor="white", linewidth=0.5, alpha=0.85,
            label="A7 (null capacity field)")
    for yi, (a3, a7, n) in enumerate(zip(op["A3"], op["A7"], op["n"])):
        if a3 > 0.02:
            ax.text(a3 * 100 + 1.5, yi + h / 2,
                    f"{a3*100:.0f}%", va="center",
                    fontsize=7, color=NAVY_DARK)
        if a7 > 0.02:
            ax.text(a7 * 100 + 1.5, yi - h / 2,
                    f"{a7*100:.0f}%", va="center",
                    fontsize=7, color=ACCENT)
    ax.set_yticks(y)
    ax.set_yticklabels(
        [f"{name}  (n={int(n):,})" for name, n in
         zip(op.index, op["n"])],
        fontsize=8,
    )
    ax.set_xlabel("Anomaly rate (% of operator's stations)")
    ax.set_xlim(0, 110)
    ax.grid(True, axis="x", alpha=0.45)
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def _load() -> tuple[pd.DataFrame, pd.DataFrame]:
    return load_catalogue(), load_summary()


gs, summary = _load()


# ---------------------------------------------------------------------------
# Sidebar (dark, project branding + resources)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        """
        <div style="
            padding: 0.9rem 0.6rem 0.8rem;
            margin-bottom: 0.3rem;
            border-bottom: 1px solid #2a3f58;
        ">
            <div style="
                font-size: 0.62rem;
                text-transform: uppercase;
                letter-spacing: 0.15em;
                color: #4A9FDF;
                font-weight: 700;
            ">R. Fossé &amp; G. Pallares  ·  2025–2026</div>
            <div style="
                font-size: 1.0rem;
                font-weight: 700;
                color: #e0eaf4;
                margin-top: 0.3rem;
                line-height: 1.2;
            ">GBFS Audit Catalogue</div>
            <div style="
                font-size: 0.73rem;
                color: #4a6a88;
                margin-top: 0.2rem;
            ">v1.0  ·  46,307 stations  ·  46 columns</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='font-size:0.60rem; text-transform:uppercase; "
        "letter-spacing:0.13em; color:#3a5a78; font-weight:600; "
        "margin: 0.75rem 0 0.25rem 0.3rem;'>Resources</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "[Paper (CSI 2026)](#)  \n"
        "[Zenodo DOI](https://doi.org/10.5281/zenodo.20125460)  \n"
        "[Hugging Face Datasets](https://huggingface.co/datasets/rohanfosse/gbfs-audit-catalogue)  \n"
        "[Source code](https://github.com/rohanfosse/gbfs-audit-catalogue)  \n"
        "[Project page](https://rohanfosse.github.io/gbfs-audit-catalogue)  \n"
        "[Notebook (8 recipes)](https://github.com/rohanfosse/gbfs-audit-catalogue/blob/main/notebooks/catalogue_recipes.ipynb)"
    )

    st.markdown(
        "<div style='font-size:0.60rem; text-transform:uppercase; "
        "letter-spacing:0.13em; color:#3a5a78; font-weight:600; "
        "margin: 1.0rem 0 0.25rem 0.3rem;'>Companion programme</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "Broader research programme on French micromobility data quality "
        "(IMD composite, IES equity, Bayesian station-level monitor) at "
        "[bikeshare-data-explorer](https://github.com/rohanfosse/bikeshare-data-explorer)."
    )

    st.markdown(
        "<div style='font-size:0.60rem; text-transform:uppercase; "
        "letter-spacing:0.13em; color:#3a5a78; font-weight:600; "
        "margin: 1.0rem 0 0.25rem 0.3rem;'>Contact</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "**Rohan Fossé**  \n"
        "CESI École d'Ingénieurs  \n"
        "Montpellier, France  \n"
        "`rfosse@cesi.fr`\n\n"
        "**Gaël Pallares**  \n"
        "CESI LINEACT (EA 7527)  \n"
        "Montpellier, France"
    )


# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

st.title("GBFS Audit Catalogue")

n_total = len(gs)
n_dock = int((gs.station_type == "docked_bike").sum())
n_systems = gs["system_id"].nunique()
n_cities = gs["city"].nunique()
n_high = int((gs.audit_confidence == "high").sum())

abstract_box(
    "The General Bikeshare Feed Specification (GBFS) is the open "
    "standard published on <code>transport.data.gouv.fr</code> under "
    "the 2019 French Mobility Orientation Law. The standard guarantees "
    "syntactic interoperability but does not enforce semantic "
    "consistency. An audit of the 123 French GBFS systems combined with "
    "an exhaustive sweep of the 1,509-system MobilityData canonical "
    "catalogue exposes a unified taxonomy of seven recurring anomaly "
    "classes (A1 to A7). Across the French corpus, "
    "<b>30.9&nbsp;%</b> of the raw stations are reclassified ; across "
    "the global catalogue, 215 systems covering 70,176 stations are "
    "flagged on the null-capacity class alone. This dashboard is the "
    "interactive companion to the released parquet.",
    findings=[
        (f"{n_total:,}", "certified stations"),
        (f"{n_dock:,}", "dock-based"),
        (f"{n_systems}", "systems audited"),
        (f"{n_cities}", "cities"),
        ("46", "typed columns"),
        ("7", "anomaly classes"),
        (f"{100 * n_high / n_total:.1f}%", "high confidence"),
    ],
)


tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Overview", "Anomaly browser", "Operator audit", "Schema", "Data explorer"]
)


# === Tab 1 -- Overview =====================================================

with tab1:
    section(1, "Headline figures")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Certified stations", f"{n_total:,}", help="Rows in the released parquet")
    c2.metric("Dock-based", f"{n_dock:,}", help="Subset audited at the static level")
    c3.metric("French systems", f"{n_systems}", help="GBFS feeds inventoried")
    c4.metric("Cities", f"{n_cities}", help="Distinct city labels")
    c5.metric("High confidence", f"{n_high:,}",
              delta=f"{100 * n_high / n_total:.1f}%",
              delta_color="off",
              help="audit_confidence == 'high'")

    section(2, "Anomaly incidence across the French and global corpora")
    st.markdown(
        "<p class='muted' style='max-width:820px;'>"
        "The audit is structured as a sequential six-step purging "
        "protocol that screens every GBFS feed against the seven "
        "anomaly classes A1 to A7. The protocol is idempotent (re-running "
        "it on the certified output is a no-op), reversible (every "
        "rejected station is preserved in <code>rejected_stations.parquet</code> "
        "with its exclusion motive) and fully logged. The same rule "
        "set is applied to the French corpus (123 systems indexed on "
        "<code>transport.data.gouv.fr</code>) and to the 1,509-system "
        "MobilityData canonical catalogue covering 48 countries. "
        "Figure 1 reports the per-class system counts side by side : "
        "the French and global hotspots are driven by different "
        "operators but share the same anti-patterns, which is what "
        "the unified A1 to A7 taxonomy captures."
        "</p>",
        unsafe_allow_html=True,
    )
    st.pyplot(fig_anomaly_incidence(), clear_figure=False, use_container_width=True)
    st.caption(
        "Figure 1. System-level incidence of the seven anomaly classes "
        "(A1 to A7) across the 123 audited French GBFS systems and the "
        "1,509-system MobilityData canonical catalogue. The most "
        "frequent global class is A7 (null capacity field, 215 systems "
        "covering 70,176 stations), led by Dott across Germany, Italy "
        "and the United Arab Emirates. A4 (geospatial outliers) is the "
        "largest global class outside A7 because country-perimeter "
        "calibration only kicks in above 5 % of stations and at least "
        "5 absolute outside-country stations."
    )

    with st.expander("What does each anomaly class catch?  (A1 to A7)"):
        for code, info in ANOMALY_CLASSES.items():
            st.markdown(
                f"**{code} – {info['name']}**  \n"
                f"<span class='muted' style='font-size:0.85rem;'>"
                f"{info['signature']}</span>",
                unsafe_allow_html=True,
            )

    section(3, "A3: empirical signature of the structural over-capacity bias")
    st.markdown(
        "<p class='muted' style='max-width:760px;'>"
        "Free-floating fleets advertise virtual stations and typically "
        "report a capacity profile by conditional averaging on stations "
        "whose instantaneous capacity is non-zero. Aggregated at the "
        "system level, this estimator differs from the actual mean "
        "capacity by an order of magnitude and would wrongly classify "
        "thousands of free-floating bikes as dock-based stations."
        "</p>",
        unsafe_allow_html=True,
    )
    st.latex(
        r"""\bar{c}_{\text{profile}}
          \;=\;
          \frac{\sum_{i\,:\,c_i > 0} c_i}{\#\{i\,:\,c_i > 0\}}
          \;\neq\;
          \bar{c}_{\text{actual}}
          \;=\;
          \frac{1}{N}\sum_{i=1}^{N} c_i"""
    )
    st.markdown(
        "<p class='muted' style='font-size:0.86rem; max-width:820px;'>"
        "The audit detects A3 by computing the ratio "
        "$\\bar{c}_{\\text{profile}} / \\bar{c}_{\\text{actual}}$ per "
        "system and flagging any value above the empirical threshold "
        "5.0 that separates dock-based fleets from free-floating ones. "
        "Negative controls back this calibration : Bicing Barcelona, "
        "Oslo Bysykkel and Bergen Bysykkel all return a ratio of "
        "essentially 1.0. The most extreme case in the French corpus "
        "is <b>Pony Bordeaux</b> : it publishes 2,996 station entries "
        "with a declared capacity of 12 docks each (nominal total : "
        "35,952 docks), but its actual mean capacity per entry, computed "
        "without conditioning on non-zero values, is "
        "<b>0.03 bike / entry</b>. After A3 reclassification, Bordeaux's "
        "dock-based station count drops from 9,921 raw GBFS entries to "
        "<b>225</b> certified dock-based stations &mdash; a 98 % collapse "
        "of the nominal infrastructure, and a seven-position shift in any "
        "supply-side ranking built on the unaudited feed."
        "</p>",
        unsafe_allow_html=True,
    )

    section(4, "Reusing the catalogue")
    st.markdown(
        "<p class='muted'>Three drop-in patterns. Pick the one that suits "
        "your workflow.</p>",
        unsafe_allow_html=True,
    )

    cA, cB = st.columns(2)
    with cA:
        st.markdown("**Hugging Face Datasets**")
        st.code(
            'from datasets import load_dataset\n'
            'gs = load_dataset(\n'
            '    "rohanfosse/gbfs-audit-catalogue",\n'
            '    split="train",\n'
            ').to_pandas()',
            language="python",
        )
    with cB:
        st.markdown("**Direct from Zenodo**")
        st.code(
            'import pandas as pd\n'
            'gs = pd.read_parquet(\n'
            '    "https://zenodo.org/records/20125460/files/"\n'
            '    "stations_gold_standard_final.parquet"\n'
            ')',
            language="python",
        )

    st.markdown("**Inspecting the audit at the row level**")
    st.code(
        '# High-confidence dock-based stations\n'
        'clean = gs[(gs.station_type == "docked_bike")\n'
        '           & (gs.audit_confidence == "high")]\n'
        'print(len(clean))    # 5,402\n\n'
        '# Per-operator anomaly profile\n'
        'gs.groupby("operator_name").agg(\n'
        '    n=("uid", "size"),\n'
        '    A3_rate=("flag_A3", "mean"),\n'
        '    A7_rate=("flag_A7", "mean"),\n'
        ').sort_values("n", ascending=False).head(10)',
        language="python",
    )

    section(5, "Citation")
    st.code(
        '@article{Fosse2026gbfs,\n'
        '  author  = {Foss\\\'e, Rohan and Pallares, Ga\\"el},\n'
        '  title   = {Auditing GBFS bike-sharing feeds at country and global scale:\n'
        '             A reproducible anomaly taxonomy for open mobility data},\n'
        '  journal = {Computer Standards \\& Interfaces},\n'
        '  year    = {2026}, note = {Under review}\n'
        '}\n'
        '\n'
        '@dataset{Fosse2026gbfsdata,\n'
        '  author    = {Foss\\\'e, Rohan and Pallares, Ga\\"el},\n'
        '  title     = {{GBFS Audit Catalogue} v1.0},\n'
        '  year      = {2026},\n'
        '  publisher = {Zenodo},\n'
        '  doi       = {10.5281/zenodo.20125460}\n'
        '}',
        language="bibtex",
    )


# === Tab 2 -- Anomaly browser ============================================

with tab2:
    section(1, "How the audit's verdict is encoded per row")
    st.markdown(
        "<p class='muted' style='max-width:820px;'>"
        "The release exposes eleven audit-pipeline columns. Reading them "
        "together gives a complete picture of why a station ended up in "
        "(or out of) the certified subset :"
        "</p>"
        "<ul class='muted' style='max-width:820px; font-size:0.92rem;'>"
        "<li><b><code>station_type</code></b> &mdash; the audited type, in "
        "{<code>docked_bike</code>, <code>free_floating</code>, "
        "<code>carsharing</code>}. <code>docked_bike</code> is the only "
        "fully-audited tier at the static level.</li>"
        "<li><b><code>capacity_raw</code> vs <code>capacity_audited</code></b> "
        "&mdash; the GBFS-declared value before the audit (may be NaN or "
        "a placeholder) and the post-audit value. They are intentionally "
        "different : <code>capacity_audited</code> is set to NaN whenever "
        "the type has been re-labelled away from <code>docked_bike</code>, "
        "so that downstream consumers cannot accidentally sum free-floating "
        "anchors as physical docks.</li>"
        "<li><b><code>flag_A1</code> to <code>flag_A7</code></b> &mdash; "
        "one boolean per class of the seven-class taxonomy. A station "
        "carries the flag of every class its parent system triggers ; "
        "stations are kept in the catalogue with their flag set so that "
        "researchers can filter explicitly (e.g. only stations with no "
        "flag, or only stations from operators triggering A3).</li>"
        "<li><b><code>operator_name</code></b> &mdash; the normalised "
        "operator label extracted from <code>system_id</code> + "
        "<code>system_name</code>. Operator-driven hotspots are the "
        "central empirical finding : the same anti-pattern propagates "
        "across an operator's entire deployment, not city by city.</li>"
        "<li><b><code>audit_confidence</code></b> &mdash; an ordinal tag "
        "in {<i>high</i>, <i>medium</i>, <i>low</i>} that summarises the "
        "flag combination. <i>high</i> means zero flags triggered ; "
        "<i>medium</i> means one acceptable flag (A3 or A7 alone, the "
        "free-floating canonical cases) ; <i>low</i> means anything "
        "else.</li>"
        "</ul>",
        unsafe_allow_html=True,
    )

    section(2, "Audit-confidence distribution on the certified corpus")
    st.pyplot(fig_confidence_distribution(gs["audit_confidence"]),
              clear_figure=False, use_container_width=True)
    st.caption(
        "Figure 2. Distribution of the per-row audit confidence over "
        f"the {len(gs):,} certified stations. Only "
        f"{int((gs.audit_confidence == 'high').sum()):,} stations "
        f"({100 * (gs.audit_confidence == 'high').mean():.1f} %) "
        "reach the high-confidence tier ; the bulk of the corpus sits "
        "at low confidence because the dominant operators (Dott, Pony, "
        "Bird) propagate the A3 / A7 flags across every station they "
        "publish."
    )

    section(3, "Filter the catalogue at the row level")
    st.markdown(
        "<p class='muted'>Combine the four filters below to inspect any "
        "sub-population. The table refreshes live ; the download button "
        "exports the current selection as a CSV.</p>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    types = c1.multiselect(
        "Station type",
        sorted(gs.station_type.dropna().unique()),
        default=["docked_bike"],
    )
    conf = c2.multiselect(
        "Audit confidence",
        ["high", "medium", "low"],
        default=["high", "medium", "low"],
    )
    op_options = sorted(gs.operator_name.dropna().unique())
    operator = c3.multiselect(
        "Operator (optional)",
        op_options,
        default=[],
    )

    flag_filters = st.multiselect(
        "Require at least one of these anomaly flags",
        [f"flag_A{i}" for i in range(1, 8)],
        default=[],
    )

    mask = gs.station_type.isin(types) & gs.audit_confidence.isin(conf)
    if operator:
        mask &= gs.operator_name.isin(operator)
    if flag_filters:
        any_flag = gs[flag_filters].any(axis=1)
        mask &= any_flag
    sub = gs[mask]

    st.markdown(
        f"<p class='muted' style='margin-top:0.4rem;'>"
        f"<b>{len(sub):,}</b> stations match the current filter "
        f"(out of {len(gs):,} certified).</p>",
        unsafe_allow_html=True,
    )

    cols_show = [
        "uid", "city", "operator_name", "station_type",
        "capacity_raw", "capacity_audited",
        "flag_A1", "flag_A2", "flag_A3", "flag_A6", "flag_A7",
        "audit_confidence",
    ]
    st.dataframe(sub[cols_show].head(500), height=420, hide_index=True)

    csv = sub[cols_show].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered subset (CSV)",
        data=csv,
        file_name="gbfs_audit_subset.csv",
        mime="text/csv",
    )


# === Tab 3 -- Operator audit =============================================

with tab3:
    section(1, "Top operators: A3 and A7 rates")
    st.pyplot(fig_operator_anomaly_rates(gs),
              clear_figure=False, use_container_width=True)
    st.caption(
        "Figure 3. A3 (structural over-capacity) and A7 (null capacity "
        "field) flagging rates for the ten operators with the largest "
        "station count. Pony triggers A3 on 100 % of its stations and "
        "Dott triggers A7 on 100 % of its stations: the audit's verdict "
        "is operator-driven, not city-driven."
    )

    section(2, "Per-operator anomaly profile (full table)")
    st.markdown(
        "<p class='muted' style='max-width:780px;'>"
        "Operator-driven hotspots are the central empirical finding of "
        "the audit. <em>Pony</em> propagates A3 (structural over-capacity) "
        "across its French deployments ; <em>Dott</em> and <em>Bird</em> "
        "propagate A7 (null capacity field) ; <em>nextbike</em> propagates "
        "A2 and A3 across the Czech Republic ; <em>Citiz</em> "
        "systematically triggers A1 (out-of-domain car-sharing).</p>",
        unsafe_allow_html=True,
    )

    op = (
        gs.groupby("operator_name")
          .agg(
              n=("uid", "size"),
              A1_rate=("flag_A1", "mean"),
              A2_rate=("flag_A2", "mean"),
              A3_rate=("flag_A3", "mean"),
              A6_rate=("flag_A6", "mean"),
              A7_rate=("flag_A7", "mean"),
              high_conf=(
                  "audit_confidence",
                  lambda s: float((s == "high").mean()),
              ),
          )
          .reset_index()
          .rename(columns={"operator_name": "Operator", "n": "Stations"})
          .sort_values("Stations", ascending=False)
    )
    st.dataframe(
        op.style.format({
            "A1_rate": "{:.1%}",
            "A2_rate": "{:.1%}",
            "A3_rate": "{:.1%}",
            "A6_rate": "{:.1%}",
            "A7_rate": "{:.1%}",
            "high_conf": "{:.1%}",
        }),
        height=460,
        hide_index=True,
    )


# === Tab 4 -- Schema =====================================================

with tab4:
    section(1, "46-column schema")
    st.markdown(
        "<p class='muted' style='max-width:780px;'>"
        "Every column carries a stable name, a declared dtype, a source "
        "pointer and a measured completeness rate. The eleven audit-pipeline "
        "columns (<code>station_type</code>, <code>capacity_raw</code>, "
        "<code>capacity_audited</code>, <code>flag_A1</code> to "
        "<code>flag_A7</code>, <code>operator_name</code>, "
        "<code>audit_confidence</code>) make the audit's verdict inspectable "
        "per row. Machine-readable schema documents (JSON Schema, DCAT-AP, "
        "Frictionless Data Package, Croissant JSON-LD) ship with the Zenodo "
        "deposit.</p>",
        unsafe_allow_html=True,
    )

    # --- Visual data dictionary: 46 columns grouped by category ---
    SCHEMA_GROUPS = {
        "Identifiers": {
            "color": "#1A6FBF",
            "cols": [
                ("uid", "Audit Catalogue primary key"),
                ("station_id", "GBFS native identifier"),
                ("system_id", "Operator-system identifier"),
                ("system_name", "Operator-system label"),
                ("source", "Feed URL / catalogue source"),
            ],
        },
        "Spatial and administrative": {
            "color": "#1A6FBF",
            "cols": [
                ("lat", "Geofiltered WGS84 latitude"),
                ("lon", "Geofiltered WGS84 longitude"),
                ("city", "Normalised city name"),
                ("commune_name", "INSEE commune label"),
                ("code_commune", "INSEE commune code"),
                ("region_id", "Administrative region"),
            ],
        },
        "Station description": {
            "color": "#1A6FBF",
            "cols": [
                ("station_name", "GBFS station name"),
                ("address", "GBFS address"),
                ("capacity", "Raw declared capacity (may be placeholder)"),
                ("n_stations_system", "Total stations in parent system"),
            ],
        },
        "Audit pipeline outputs": {
            "color": "#C0392B",
            "cols": [
                ("station_type", "Audited type: docked_bike, free_floating, carsharing"),
                ("capacity_raw", "Raw GBFS capacity (preserves NaN, placeholders)"),
                ("capacity_audited", "Post-audit capacity (NaN for non-dock types)"),
                ("flag_A1", "Out-of-domain inclusion (carsharing)"),
                ("flag_A2", "Placeholder capacity at system level"),
                ("flag_A3", "Structural over-capacity (free-floating)"),
                ("flag_A4", "Geospatial outlier (kept set: False)"),
                ("flag_A5", "Out-of-perimeter (kept set: False)"),
                ("flag_A6", "Zero-capacity dock"),
                ("flag_A7", "Null capacity field at system level"),
                ("operator_name", "Normalised operator label"),
                ("audit_confidence", "Audit confidence: high, medium, low"),
                ("fetched_at", "Timestamp of the audited snapshot"),
            ],
        },
        "Network geometry": {
            "color": "#7B5EA7",
            "cols": [
                ("dist_to_nearest_station_m", "Intra-system KNN distance"),
                ("n_stations_within_500m", "Intra-system 500 m density"),
                ("n_stations_within_1km", "Intra-system 1 km density"),
                ("nearest_system_dist_m", "Distance to nearest non-self system"),
                ("catchment_density_per_km2", "Stations per km^2 (1 km buffer)"),
            ],
        },
        "Topography": {
            "color": "#2E7D32",
            "cols": [
                ("elevation_m", "BD ALTI elevation (IGN)"),
                ("topography_roughness_index", "Local relief amplitude"),
            ],
        },
        "Cycling infrastructure": {
            "color": "#2E7D32",
            "cols": [
                ("infra_cyclable_km", "BD TOPO cycle-lane linear (300 m buffer)"),
                ("infra_cyclable_pct", "Share of dedicated right-of-way"),
            ],
        },
        "Safety": {
            "color": "#2E7D32",
            "cols": [
                ("baac_accidents_cyclistes", "Severe-crash count (500 m, 5 yr)"),
            ],
        },
        "Multimodal access": {
            "color": "#2E7D32",
            "cols": [
                ("gtfs_heavy_stops_300m", "Heavy-transit stops within 300 m"),
                ("gtfs_stops_within_300m_pct", "Share of accessible heavy-transit"),
            ],
        },
        "Socio-economic context": {
            "color": "#E08E0B",
            "cols": [
                ("revenu_median_uc", "INSEE Filosofi median income per CU"),
                ("gini_revenu", "Local Gini index"),
                ("revenu_d1", "First-decile income"),
                ("ecart_interquar", "Interquartile income spread"),
                ("part_menages_voit0", "Share of car-less households"),
            ],
        },
        "Modal share": {
            "color": "#E08E0B",
            "cols": [
                ("part_velo_travail", "Share of commute by bike (INSEE)"),
            ],
        },
    }

    # Inject schema-card CSS once.
    st.markdown(
        """
        <style>
        .schema-group {
            margin: 0.55rem 0 1.1rem 0;
        }
        .schema-group-header {
            display: flex;
            align-items: baseline;
            gap: 0.6rem;
            padding: 0.35rem 0;
            border-bottom: 1px solid #e8edf3;
            margin-bottom: 0.45rem;
        }
        .schema-group-header .accent {
            width: 4px;
            height: 14px;
            border-radius: 2px;
            display: inline-block;
            margin-bottom: -2px;
        }
        .schema-group-header .name {
            font-size: 0.94rem;
            font-weight: 600;
            color: #1A2332;
        }
        .schema-group-header .count {
            font-size: 0.72rem;
            color: #5a7a96;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-left: auto;
        }
        .schema-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
            gap: 0.5rem;
        }
        .schema-card {
            border: 1px solid #e4ecf3;
            border-left-width: 3px;
            border-radius: 4px;
            padding: 0.55rem 0.7rem;
            background: #ffffff;
        }
        .schema-card .col-row {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            margin-bottom: 0.25rem;
        }
        .schema-card .col-name {
            font-family: ui-monospace, Menlo, Consolas, monospace;
            font-size: 0.83rem;
            font-weight: 600;
            color: #1A2332;
        }
        .schema-card .dtype-pill {
            font-family: ui-monospace, Menlo, monospace;
            font-size: 0.66rem;
            padding: 0.06rem 0.4rem;
            background: #eef2f7;
            color: #5a6470;
            border-radius: 999px;
            border: 1px solid #e4ecf3;
            text-transform: lowercase;
        }
        .schema-card .completeness {
            margin-left: auto;
            font-size: 0.7rem;
            color: #5a7a96;
            font-variant-numeric: tabular-nums;
        }
        .schema-card .bar {
            height: 3px;
            background: #eef2f7;
            border-radius: 999px;
            overflow: hidden;
            margin: 0.15rem 0 0.35rem 0;
        }
        .schema-card .bar > div {
            height: 100%;
            background: #1A6FBF;
            border-radius: 999px;
        }
        .schema-card .desc {
            font-size: 0.78rem;
            color: #5a6470;
            line-height: 1.4;
            margin-bottom: 0.2rem;
        }
        .schema-card .example {
            font-family: ui-monospace, Menlo, monospace;
            font-size: 0.72rem;
            color: #7a8a9a;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            border-top: 1px dashed #eef2f7;
            padding-top: 0.25rem;
            margin-top: 0.15rem;
        }
        .schema-card .example .lbl {
            color: #b0bccb;
            margin-right: 0.3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    def _format_example(value) -> str:
        if pd.isna(value):
            return "<i>NaN</i>"
        if isinstance(value, float):
            return f"{value:.3f}".rstrip("0").rstrip(".") or "0"
        if isinstance(value, bool):
            return "True" if value else "False"
        s = str(value)
        if len(s) > 38:
            return s[:35] + "…"
        return s

    sample_row = gs.iloc[0]

    for group_name, info in SCHEMA_GROUPS.items():
        # Header
        st.markdown(
            f'<div class="schema-group-header">'
            f'  <span class="accent" style="background:{info["color"]};"></span>'
            f'  <span class="name">{group_name}</span>'
            f'  <span class="count">{len(info["cols"])} column'
            f'{"s" if len(info["cols"]) > 1 else ""}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        cards_html = '<div class="schema-grid">'
        for col, desc in info["cols"]:
            if col not in gs.columns:
                continue
            series = gs[col]
            completeness = float(series.notna().mean())
            dtype = str(series.dtype)
            example = _format_example(sample_row[col])
            cards_html += (
                f'<div class="schema-card" style="border-left-color:{info["color"]};">'
                f'  <div class="col-row">'
                f'    <span class="col-name">{col}</span>'
                f'    <span class="dtype-pill">{dtype}</span>'
                f'    <span class="completeness">{completeness*100:.1f}%</span>'
                f'  </div>'
                f'  <div class="bar"><div style="width:{completeness*100:.1f}%;'
                f'background:{info["color"]};"></div></div>'
                f'  <div class="desc">{desc}</div>'
                f'  <div class="example"><span class="lbl">e.g.</span>{example}</div>'
                f'</div>'
            )
        cards_html += "</div>"
        st.markdown(cards_html, unsafe_allow_html=True)

    section(2, "The seven anomaly classes")
    classes_html = ""
    for code, info in ANOMALY_CLASSES.items():
        classes_html += (
            f'<div class="cls-card">'
            f'  <div class="code">{code}</div>'
            f'  <div>'
            f'    <div class="name">{info["name"]}</div>'
            f'    <div class="sig">{info["signature"]}</div>'
            f'  </div>'
            f'</div>'
        )
    st.markdown(classes_html, unsafe_allow_html=True)


# === Tab 5 -- Data explorer ==============================================

with tab5:
    section(1, "Search the 46,307-station catalogue")
    st.markdown(
        "<p class='muted' style='max-width:820px;'>"
        "Free-text search across station, city and operator labels, "
        "combined with categorical and numerical filters. The map and "
        "the table refresh live ; the download button at the bottom "
        "exports the current selection."
        "</p>",
        unsafe_allow_html=True,
    )

    # --- Filters row 1 : text search + station type ---
    f1a, f1b = st.columns([2, 1])
    query = f1a.text_input(
        "Free-text search (matches station_name, city, operator_name)",
        value="",
        placeholder="e.g. 'paris', 'pony bordeaux', 'gare', 'velib'",
    ).strip().lower()
    type_filter = f1b.multiselect(
        "Station type",
        sorted(gs.station_type.dropna().unique()),
        default=sorted(gs.station_type.dropna().unique()),
    )

    # --- Filters row 2 : confidence + flags + city + operator ---
    f2a, f2b, f2c = st.columns(3)
    conf_filter = f2a.multiselect(
        "Audit confidence",
        ["high", "medium", "low"],
        default=["high", "medium", "low"],
    )
    city_options = sorted(gs.city.dropna().unique())
    city_filter = f2b.multiselect(
        "City (optional)",
        city_options,
        default=[],
        max_selections=20,
        help="Leave empty to search all 97 cities",
    )
    op_options = sorted(gs.operator_name.dropna().unique())
    op_filter = f2c.multiselect(
        "Operator (optional)",
        op_options,
        default=[],
    )

    # --- Filters row 3 : flags + capacity range ---
    f3a, f3b = st.columns([2, 1])
    flag_filter = f3a.multiselect(
        "Require at least one of these anomaly flags",
        [f"flag_A{i}" for i in range(1, 8)],
        default=[],
    )
    cap_audited = gs["capacity_audited"]
    cap_min = int(np.nanmin(cap_audited)) if cap_audited.notna().any() else 0
    cap_max = int(np.nanmax(cap_audited)) if cap_audited.notna().any() else 100
    cap_range = f3b.slider(
        "Audited capacity (dock-based only)",
        min_value=cap_min,
        max_value=cap_max,
        value=(cap_min, cap_max),
        help="NaN-capacity rows (non-dock types) are kept regardless of this slider",
    )

    # --- Apply filters ---
    mask = gs.station_type.isin(type_filter) & gs.audit_confidence.isin(conf_filter)
    if query:
        haystack = (
            gs["station_name"].fillna("").str.lower()
            + " "
            + gs["city"].fillna("").str.lower()
            + " "
            + gs["operator_name"].fillna("").str.lower()
        )
        mask &= haystack.str.contains(query, regex=False, na=False)
    if city_filter:
        mask &= gs.city.isin(city_filter)
    if op_filter:
        mask &= gs.operator_name.isin(op_filter)
    if flag_filter:
        any_flag = gs[flag_filter].any(axis=1)
        mask &= any_flag
    # Capacity filter only applies to rows with non-NaN capacity_audited
    cap_mask = (
        gs["capacity_audited"].isna()
        | ((gs["capacity_audited"] >= cap_range[0])
           & (gs["capacity_audited"] <= cap_range[1]))
    )
    mask &= cap_mask

    sub = gs[mask]
    n_sub = len(sub)
    pct_sub = 100.0 * n_sub / len(gs) if len(gs) else 0.0

    # --- Result summary ---
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Selected stations", f"{n_sub:,}",
              delta=f"{pct_sub:.2f}% of corpus",
              delta_color="off")
    r2.metric("Cities in selection",
              f"{sub['city'].nunique() if n_sub else 0}")
    r3.metric("Operators in selection",
              f"{sub['operator_name'].nunique() if n_sub else 0}")
    r4.metric("High confidence in selection",
              f"{int((sub.audit_confidence == 'high').sum()) if n_sub else 0:,}")

    if n_sub == 0:
        st.warning("No station matches the current filter. Loosen the criteria above.")
    else:
        section(2, "Geographic distribution")
        # Build the map data
        map_df = sub[["lat", "lon"]].dropna().copy()
        if len(map_df) > 8000:
            st.caption(
                f"{len(map_df):,} stations would render on the map ; sampling "
                "8,000 for responsiveness."
            )
            map_df = map_df.sample(8000, random_state=2026)
        st.map(map_df, latitude="lat", longitude="lon", size=15,
               color="#1A6FBF", use_container_width=True)

        section(3, "Tabular view")
        cols_show = [
            "uid", "city", "operator_name", "station_type", "station_name",
            "capacity_raw", "capacity_audited",
            "flag_A1", "flag_A2", "flag_A3", "flag_A6", "flag_A7",
            "audit_confidence", "lat", "lon",
        ]
        cols_show = [c for c in cols_show if c in sub.columns]
        sort_options = [c for c in [
            "city", "operator_name", "capacity_audited", "station_name",
            "audit_confidence",
        ] if c in sub.columns]
        sb1, sb2 = st.columns([1, 4])
        sort_col = sb1.selectbox("Sort by", sort_options, index=0)
        sort_asc = sb2.radio("Order", ["ascending", "descending"],
                              horizontal=True, index=0,
                              label_visibility="collapsed") == "ascending"
        sub_sorted = sub.sort_values(sort_col, ascending=sort_asc)
        st.dataframe(sub_sorted[cols_show].head(500),
                     height=420, hide_index=True)
        if n_sub > 500:
            st.caption(
                f"Showing the first 500 of {n_sub:,} matching stations "
                "(sorted by the column above). Use the download button "
                "to export the full selection."
            )

        section(4, "Export")
        csv_bytes = sub_sorted[cols_show].to_csv(index=False).encode("utf-8")
        full_csv = sub_sorted.to_csv(index=False).encode("utf-8")
        d1, d2 = st.columns(2)
        d1.download_button(
            "Download shown columns (CSV)",
            data=csv_bytes,
            file_name=f"gbfs_audit_selection_{n_sub}.csv",
            mime="text/csv",
        )
        d2.download_button(
            "Download all 46 columns (CSV)",
            data=full_csv,
            file_name=f"gbfs_audit_selection_full_{n_sub}.csv",
            mime="text/csv",
        )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div style="
        margin-top: 2.4rem;
        padding-top: 0.9rem;
        border-top: 1px solid #e8edf3;
        font-size: 0.80rem;
        color: #5a7a96;
        line-height: 1.55;
    ">
      <b>GBFS Audit Catalogue v1.0</b>  ·  Fossé (CESI École d'Ingénieurs)
       &amp; Pallares (CESI LINEACT)  ·  Montpellier, France.
      <br/>
      Data licensed under
      <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank"
         style="color:#1A6FBF; text-decoration:none; font-weight:500;">ODbL v1.0</a>
       ·  code licensed under
      <a href="https://opensource.org/licenses/MIT" target="_blank"
         style="color:#1A6FBF; text-decoration:none; font-weight:500;">MIT</a>
       ·
      <a href="https://github.com/rohanfosse/gbfs-audit-catalogue/issues"
         target="_blank"
         style="color:#1A6FBF; text-decoration:none; font-weight:500;">
        Issues and contributions
      </a>.
    </div>
    """,
    unsafe_allow_html=True,
)
