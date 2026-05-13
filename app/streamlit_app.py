"""GBFS Audit Catalogue -- research dashboard.

Companion to Fossé & Pallares (2026), Computer Standards & Interfaces.

Run locally :
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit_pipeline import ANOMALY_CLASSES, load_catalogue, load_summary  # noqa: E402

from app.figures import (  # noqa: E402
    _fr_system_counts,
    configure_matplotlib,
    fig_anomaly_incidence,
    fig_confidence_distribution,
    fig_operator_anomaly_rates,
)
from app.styles import (  # noqa: E402
    abstract_box,
    inject_styles,
    muted,
    section,
)


# ---------------------------------------------------------------------------
# Page config + styles
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

inject_styles()
configure_matplotlib()


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@st.cache_data
def _load() -> tuple[pd.DataFrame, pd.DataFrame]:
    return load_catalogue(), load_summary()


with st.spinner("Loading the 46,307-station catalogue…"):
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
        "[Paper (CSI 2026, under review)](https://doi.org/10.5281/zenodo.20125460)  \n"
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
    c5.metric(
        "High confidence",
        f"{n_high:,}",
        delta=f"{100 * n_high / n_total:.1f}%",
        delta_color="off",
        help="audit_confidence == 'high'",
    )

    section(2, "Anomaly incidence across the French and global corpora")
    muted(
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
    )
    st.pyplot(
        fig_anomaly_incidence(_fr_system_counts(summary)),
        clear_figure=False,
        use_container_width=True,
    )
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
    muted(
        "Free-floating fleets advertise virtual stations and typically "
        "report a capacity profile by conditional averaging on stations "
        "whose instantaneous capacity is non-zero. Aggregated at the "
        "system level, this estimator differs from the actual mean "
        "capacity by an order of magnitude and would wrongly classify "
        "thousands of free-floating bikes as dock-based stations.",
        max_width=760,
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
    muted(
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
    )

    section(4, "Reusing the catalogue")
    muted(
        "Three drop-in patterns. Pick the one that suits your workflow.",
        max_width=None,
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
        '# All dock-based stations (5,442)\n'
        'docked = gs[gs.station_type == "docked_bike"]\n\n'
        '# Same, restricted to high-confidence systems (4,713)\n'
        'clean = docked[docked.audit_confidence == "high"]\n\n'
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
        '  year    = {2026},\n'
        '  note    = {Manuscript under peer review; preprint forthcoming}\n'
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
    st.pyplot(
        fig_confidence_distribution(gs["audit_confidence"]),
        clear_figure=False,
        use_container_width=True,
    )
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
    muted(
        "Combine the four filters below to inspect any sub-population. "
        "The table refreshes live ; the download button exports the "
        "current selection as a CSV.",
        max_width=None,
    )

    c1, c2, c3 = st.columns(3)
    types = c1.multiselect(
        "Station type",
        sorted(gs.station_type.dropna().unique()),
        default=["docked_bike"],
        key="anomaly_station_type",
    )
    conf = c2.multiselect(
        "Audit confidence",
        ["high", "medium", "low"],
        default=["high", "medium", "low"],
        key="anomaly_audit_confidence",
    )
    op_options_anom = sorted(gs.operator_name.dropna().unique())
    operator = c3.multiselect(
        "Operator (optional)",
        op_options_anom,
        default=[],
        key="anomaly_operator",
    )

    flag_filters = st.multiselect(
        "Require at least one of these anomaly flags",
        [f"flag_A{i}" for i in range(1, 8)],
        default=[],
        key="anomaly_flags",
    )

    mask = gs.station_type.isin(types) & gs.audit_confidence.isin(conf)
    if operator:
        mask &= gs.operator_name.isin(operator)
    if flag_filters:
        mask &= gs[flag_filters].any(axis=1)
    sub = gs[mask]

    if len(sub) == 0:
        st.warning("No station matches the current filter. Loosen the criteria above.")
    else:
        st.markdown(
            f"<p class='muted' style='margin-top:0.4rem;'>"
            f"<b>{len(sub):,}</b> stations match the current filter "
            f"(out of {len(gs):,} certified).</p>",
            unsafe_allow_html=True,
        )

        cols_show = [
            "uid", "city", "operator_name", "station_type",
            "capacity_raw", "capacity_audited",
            "flag_A1", "flag_A2", "flag_A3", "flag_A4", "flag_A5",
            "flag_A6", "flag_A7",
            "audit_confidence",
        ]
        st.dataframe(sub[cols_show].head(500), height=420, hide_index=True)

        csv = sub[cols_show].to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download filtered subset (CSV)",
            data=csv,
            file_name="gbfs_audit_subset.csv",
            mime="text/csv",
            key="anomaly_download",
        )


# === Tab 3 -- Operator audit =============================================

with tab3:
    section(1, "Top operators: A3 and A7 rates")
    st.pyplot(
        fig_operator_anomaly_rates(gs),
        clear_figure=False,
        use_container_width=True,
    )
    st.caption(
        "Figure 3. A3 (structural over-capacity) and A7 (null capacity "
        "field) flagging rates for the ten operators with the largest "
        "station count. Pony triggers A3 on 100 % of its stations and "
        "Dott triggers A7 on 100 % of its stations: the audit's verdict "
        "is operator-driven, not city-driven."
    )

    section(2, "Per-operator anomaly profile (full table)")
    muted(
        "Operator-driven hotspots are the central empirical finding of "
        "the audit. <em>Pony</em> propagates A3 (structural over-capacity) "
        "across its French deployments ; <em>Dott</em> and <em>Bird</em> "
        "propagate A7 (null capacity field) ; <em>nextbike</em> propagates "
        "A2 and A3 across the Czech Republic ; <em>Citiz</em> "
        "systematically triggers A1 (out-of-domain car-sharing).",
        max_width=780,
    )

    op = (
        gs.groupby("operator_name")
        .agg(
            n=("uid", "size"),
            A1_rate=("flag_A1", "mean"),
            A2_rate=("flag_A2", "mean"),
            A3_rate=("flag_A3", "mean"),
            A4_rate=("flag_A4", "mean"),
            A5_rate=("flag_A5", "mean"),
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
        op.style.format(
            {f"A{i}_rate": "{:.1%}" for i in range(1, 8)} | {"high_conf": "{:.1%}"}
        ),
        height=460,
        hide_index=True,
    )


# === Tab 4 -- Schema =====================================================

with tab4:
    section(1, "46-column schema")
    muted(
        "Every column carries a stable name, a declared dtype, a source "
        "pointer and a measured completeness rate. The sixteen "
        "audit-pipeline columns make the audit's verdict inspectable "
        "per row. Machine-readable schema documents (JSON Schema, "
        "DCAT-AP, Frictionless Data Package, Croissant JSON-LD) ship "
        "with the Zenodo deposit.",
        max_width=780,
    )

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
                ("flag_A4", "Geospatial outlier (3-sigma from system centroid)"),
                ("flag_A5", "Out-of-perimeter (bbox > 50,000 km^2)"),
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

# Anomaly colour map for the pydeck map (RGBA, 0-255).
_MAP_COLOURS: dict[str, list[int]] = {
    "high": [26, 111, 191, 200],     # NAVY
    "medium": [232, 142, 30, 200],   # amber
    "low": [192, 57, 43, 200],       # ACCENT red
}


def _row_colour(conf: str) -> list[int]:
    return _MAP_COLOURS.get(conf, [120, 120, 120, 180])


with tab5:
    section(1, "Search the 46,307-station catalogue")
    muted(
        "Free-text search across station, city and operator labels, "
        "combined with categorical and numerical filters. The map and "
        "the table refresh live ; the download button at the bottom "
        "exports the current selection."
    )

    f1a, f1b = st.columns([2, 1])
    query = (
        f1a.text_input(
            "Free-text search (matches station_name, city, operator_name)",
            value="",
            placeholder="e.g. 'paris', 'pony bordeaux', 'gare', 'velib'",
            key="explorer_query",
        )
        .strip()
        .lower()
    )
    type_filter = f1b.multiselect(
        "Station type",
        sorted(gs.station_type.dropna().unique()),
        default=sorted(gs.station_type.dropna().unique()),
        key="explorer_station_type",
    )

    f2a, f2b, f2c = st.columns(3)
    conf_filter = f2a.multiselect(
        "Audit confidence",
        ["high", "medium", "low"],
        default=["high", "medium", "low"],
        key="explorer_audit_confidence",
    )
    city_options = sorted(gs.city.dropna().unique())
    city_filter = f2b.multiselect(
        "City (optional)",
        city_options,
        default=[],
        max_selections=20,
        help="Leave empty to search all 97 cities",
        key="explorer_city",
    )
    op_options = sorted(gs.operator_name.dropna().unique())
    op_filter = f2c.multiselect(
        "Operator (optional)",
        op_options,
        default=[],
        key="explorer_operator",
    )

    f3a, f3b = st.columns([2, 1])
    flag_filter = f3a.multiselect(
        "Require at least one of these anomaly flags",
        [f"flag_A{i}" for i in range(1, 8)],
        default=[],
        key="explorer_flags",
    )

    cap_audited = gs["capacity_audited"]
    finite_cap = cap_audited.dropna()
    if finite_cap.empty:
        cap_min, cap_max = 0, 100
    else:
        # Clamp the upper bound at P99 so a placeholder outlier
        # (e.g. capacity = 99,999) does not collapse the slider.
        cap_min = int(np.floor(finite_cap.min()))
        cap_max = int(np.ceil(finite_cap.quantile(0.99)))
        if cap_max <= cap_min:
            cap_max = cap_min + 1
    cap_range = f3b.slider(
        "Audited capacity (dock-based, P1–P99)",
        min_value=cap_min,
        max_value=cap_max,
        value=(cap_min, cap_max),
        help=(
            "NaN-capacity rows (non-dock types) are kept regardless of "
            "this slider. The upper bound is the 99th percentile to avoid "
            "stretching by placeholder outliers."
        ),
        key="explorer_capacity",
    )

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
        mask &= gs[flag_filter].any(axis=1)
    cap_mask = gs["capacity_audited"].isna() | (
        (gs["capacity_audited"] >= cap_range[0])
        & (gs["capacity_audited"] <= cap_range[1])
    )
    mask &= cap_mask

    sub = gs[mask]
    n_sub = len(sub)
    pct_sub = 100.0 * n_sub / len(gs) if len(gs) else 0.0

    r1, r2, r3, r4 = st.columns(4)
    r1.metric(
        "Selected stations",
        f"{n_sub:,}",
        delta=f"{pct_sub:.2f}% of corpus",
        delta_color="off",
    )
    r2.metric("Cities in selection", f"{sub['city'].nunique() if n_sub else 0}")
    r3.metric(
        "Operators in selection",
        f"{sub['operator_name'].nunique() if n_sub else 0}",
    )
    r4.metric(
        "High confidence in selection",
        f"{int((sub.audit_confidence == 'high').sum()) if n_sub else 0:,}",
    )

    if n_sub == 0:
        st.warning("No station matches the current filter. Loosen the criteria above.")
    else:
        section(2, "Geographic distribution")
        map_df = sub[
            [
                "lat",
                "lon",
                "operator_name",
                "system_name",
                "city",
                "audit_confidence",
                "capacity_audited",
                "station_type",
            ]
        ].dropna(subset=["lat", "lon"]).copy()
        if len(map_df) > 8000:
            st.caption(
                f"{len(map_df):,} stations would render on the map ; sampling "
                "8,000 for responsiveness."
            )
            map_df = map_df.sample(8000, random_state=2026)

        map_df["colour"] = map_df["audit_confidence"].map(_row_colour)
        # Use capacity_audited if available; otherwise a small default
        # so free-floating anchors still appear.
        map_df["radius"] = (
            map_df["capacity_audited"].fillna(8).clip(lower=8, upper=80) * 4.0
        )

        lat_centre = float(map_df["lat"].mean())
        lon_centre = float(map_df["lon"].mean())

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position=["lon", "lat"],
            get_fill_color="colour",
            get_radius="radius",
            radius_min_pixels=2,
            radius_max_pixels=14,
            pickable=True,
            opacity=0.75,
        )
        view = pdk.ViewState(
            latitude=lat_centre, longitude=lon_centre, zoom=5.2
        )
        tooltip = {
            "html": (
                "<b>{station_name}</b><br/>"
                "Operator: {operator_name}<br/>"
                "City: {city}<br/>"
                "Type: {station_type}<br/>"
                "Capacity (audited): {capacity_audited}<br/>"
                "Confidence: {audit_confidence}"
            ),
            "style": {
                "backgroundColor": "#1B2635",
                "color": "#e0eaf4",
                "fontSize": "0.78rem",
                "padding": "0.4rem 0.6rem",
            },
        }
        st.pydeck_chart(
            pdk.Deck(
                map_style="light",
                initial_view_state=view,
                layers=[layer],
                tooltip=tooltip,
            ),
            use_container_width=True,
        )
        st.caption(
            "Coloured by audit_confidence (blue = high, amber = medium, "
            "red = low). Point radius scales with audited capacity, "
            "clipped at the 99th percentile."
        )

        section(3, "Tabular view")
        cols_show = [
            "uid", "city", "operator_name", "station_type", "station_name",
            "capacity_raw", "capacity_audited",
            "flag_A1", "flag_A2", "flag_A3", "flag_A4", "flag_A5",
            "flag_A6", "flag_A7",
            "audit_confidence", "lat", "lon",
        ]
        cols_show = [c for c in cols_show if c in sub.columns]
        sort_options = [
            c
            for c in [
                "city",
                "operator_name",
                "capacity_audited",
                "station_name",
                "audit_confidence",
            ]
            if c in sub.columns
        ]
        sb1, sb2 = st.columns([1, 4])
        sort_col = sb1.selectbox(
            "Sort by", sort_options, index=0, key="explorer_sort_col"
        )
        sort_asc = (
            sb2.radio(
                "Order",
                ["ascending", "descending"],
                horizontal=True,
                index=0,
                label_visibility="collapsed",
                key="explorer_sort_order",
            )
            == "ascending"
        )
        sub_sorted = sub.sort_values(sort_col, ascending=sort_asc)
        st.dataframe(sub_sorted[cols_show].head(500), height=420, hide_index=True)
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
            key="explorer_download_shown",
        )
        d2.download_button(
            "Download all 46 columns (CSV)",
            data=full_csv,
            file_name=f"gbfs_audit_selection_full_{n_sub}.csv",
            mime="text/csv",
            key="explorer_download_full",
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
