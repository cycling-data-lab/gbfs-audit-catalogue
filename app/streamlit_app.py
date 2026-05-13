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

import pandas as pd
import streamlit as st

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit_pipeline import ANOMALY_CLASSES, load_catalogue, load_summary  # noqa: E402


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
        "Rohan Fossé  \n"
        "CESI LINEACT (EA 7527)  \n"
        "Montpellier, France  \n"
        "`rfosse@cesi.fr`"
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


tab1, tab2, tab3, tab4 = st.tabs(
    ["Overview", "Anomaly browser", "Operator audit", "Schema"]
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

    section(2, "Reusing the catalogue")
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

    section(3, "Citation")
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
    section(1, "Filter the catalogue at the row level")
    st.markdown(
        "<p class='muted'>The 46-column parquet exposes one anomaly flag "
        "per class (<code>flag_A1</code> to <code>flag_A7</code>) and an "
        "ordinal <code>audit_confidence</code> tag (<i>high</i>, "
        "<i>medium</i>, <i>low</i>). Combine the filters below to inspect "
        "any sub-population.</p>",
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
    section(1, "Per-operator anomaly profile")
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

    schema_rows = []
    for col in gs.columns:
        s = gs[col]
        schema_rows.append({
            "column": col,
            "dtype": str(s.dtype),
            "completeness": float(s.notna().mean()),
            "n_unique": int(s.nunique(dropna=True)),
        })
    st.dataframe(
        pd.DataFrame(schema_rows).style.format({"completeness": "{:.1%}"}),
        height=520,
        hide_index=True,
    )

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
      <b>GBFS Audit Catalogue v1.0</b>  ·  Fossé &amp; Pallares (2026)
       ·  CESI LINEACT, Montpellier.
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
