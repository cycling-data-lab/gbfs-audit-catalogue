"""Shared styles and HTML helpers for the Streamlit dashboard.

Keeping the CSS soup and the HTML helper widgets out of
``streamlit_app.py`` means the main app reads as an app rather than
as a stylesheet, and the CSS is one ``Ctrl-F`` away from anyone who
needs to touch the visual identity.

Visual identity mirrors the wider research programme
(bikeshare-data-explorer) : dark sidebar, light academic main
content, primary blue ``#1A6FBF``, abstract box, numbered sections,
metric cards.
"""
from __future__ import annotations

import streamlit as st

NAVY = "#1A6FBF"
NAVY_DARK = "#15538f"
ACCENT = "#C0392B"
MUTED = "#9DBADD"

# Categorical palette used by the schema-group accents and the
# pydeck anomaly-flag legend. Keys are user-facing labels.
CATEGORICAL_PALETTE: dict[str, str] = {
    "identifiers": "#1A6FBF",
    "audit": "#C0392B",
    "geometry": "#7B5EA7",
    "context": "#2E7D32",
    "socio_economic": "#E08E0B",
}

_CSS = """
<style>
/* === MAIN CONTENT ====================================================== */

.block-container {
    padding-top: 1.6rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 1240px;
}

h1 {
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    color: #1A2332 !important;
    letter-spacing: -0.01em !important;
    margin-bottom: 0.2rem !important;
    border-bottom: 2px solid #1A6FBF !important;
    padding-bottom: 0.35rem !important;
}

h2 {
    font-size: 1.08rem !important;
    font-weight: 600 !important;
    color: #1A2332 !important;
    border-bottom: 1px solid #e8edf3 !important;
    padding-bottom: 0.2rem !important;
    margin-top: 0.6rem !important;
}

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

/* === SCHEMA CARDS ====================================================== */

.schema-group { margin: 0.55rem 0 1.1rem 0; }
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
"""


def inject_styles() -> None:
    """Render the global CSS block once per session."""
    st.markdown(_CSS, unsafe_allow_html=True)


def section(number: int | str, title: str) -> None:
    """Numbered section header, research-paper style."""
    st.markdown(f"### {number}. {title}")


def muted(text: str, max_width: int | None = 820) -> None:
    """Render a muted-grey paragraph without scattering inline HTML
    across the call sites. Accepts the same raw-HTML content as
    Streamlit's ``markdown`` with ``unsafe_allow_html=True``."""
    style = "color:#5a7a96; font-size:0.92rem; line-height:1.55;"
    if max_width is not None:
        style += f" max-width:{max_width}px;"
    st.markdown(
        f"<p style='{style}'>{text}</p>",
        unsafe_allow_html=True,
    )


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


__all__ = [
    "NAVY",
    "NAVY_DARK",
    "ACCENT",
    "MUTED",
    "CATEGORICAL_PALETTE",
    "inject_styles",
    "section",
    "muted",
    "abstract_box",
]
