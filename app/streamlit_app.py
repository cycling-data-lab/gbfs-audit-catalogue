"""GBFS Audit Catalogue -- interactive companion to the dataset.

Four pages :
  - Overview          : statistics, download, citation
  - Anomaly browser   : filter by class, operator, station type
  - Operator audit    : per-operator anomaly profile
  - Schema reference  : 46-column documentation

Run locally :
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit_pipeline import ANOMALY_CLASSES, load_catalogue, load_summary  # noqa: E402

st.set_page_config(
    page_title="GBFS Audit Catalogue",
    page_icon=None,
    layout="wide",
)


@st.cache_data(ttl=3600)
def _load() -> tuple[pd.DataFrame, pd.DataFrame]:
    return load_catalogue(), load_summary()


gs, summary = _load()


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

st.title("GBFS Audit Catalogue")
st.markdown(
    "**A reproducible audit of 1,509 open bike-sharing feeds across 48 countries.**  \n"
    "Companion to Fossé & Pallares (2026), *Computer Standards & Interfaces*.  \n"
    "Zenodo DOI : [10.5281/zenodo.20125460](https://doi.org/10.5281/zenodo.20125460)  ·  "
    "Hugging Face : [rohanfosse/gbfs-audit-catalogue](https://huggingface.co/datasets/rohanfosse/gbfs-audit-catalogue)  ·  "
    "Source : [GitHub](https://github.com/rohanfosse/gbfs-audit-catalogue)"
)
st.divider()

n_total = len(gs)
n_dock = int((gs.station_type == "docked_bike").sum())
n_systems = gs["system_id"].nunique()
n_cities = gs["city"].nunique()
n_high = int((gs.audit_confidence == "high").sum())

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Certified stations", f"{n_total:,}")
m2.metric("Dock-based", f"{n_dock:,}")
m3.metric("Audited systems", f"{n_systems}")
m4.metric("Cities", f"{n_cities}")
m5.metric("High-confidence", f"{n_high:,}")

tab1, tab2, tab3, tab4 = st.tabs(
    ["Overview", "Anomaly browser", "Operator audit", "Schema"]
)


# ---------------------------------------------------------------------------
# Tab 1 -- Overview
# ---------------------------------------------------------------------------

with tab1:
    st.subheader("What is this catalogue?")
    st.markdown(
        "The General Bikeshare Feed Specification (GBFS) is the open "
        "standard that French bike-sharing operators must publish on "
        "`transport.data.gouv.fr` under the 2019 Mobility Orientation "
        "Law. The standard guarantees syntactic interoperability but "
        "**not** semantic consistency: identical fields cover "
        "incompatible meanings across operators.\n\n"
        "This dataset is the output of a systematic audit of the "
        "1,509 GBFS systems catalogued by MobilityData worldwide. "
        "Seven recurring anomaly classes (A1--A7) are detected at the "
        "row level; 30.9% of the raw French stations are reclassified, "
        "removed or relabelled. The remaining 46,307 stations are "
        "released here with per-row anomaly flags and contextual "
        "enrichment so that researchers can reuse the audited data "
        "without rerunning the pipeline."
    )

    st.subheader("Reuse")
    st.code(
        '# Direct from Zenodo\n'
        'import pandas as pd\n'
        'gs = pd.read_parquet(\n'
        '    "https://zenodo.org/records/20125460/files/"\n'
        '    "stations_gold_standard_final.parquet")\n\n'
        '# Or via Hugging Face Datasets\n'
        'from datasets import load_dataset\n'
        'gs = load_dataset("rohanfosse/gbfs-audit-catalogue",\n'
        '                  split="train").to_pandas()\n',
        language="python",
    )

    st.subheader("Citation")
    st.code(
        '@article{Fosse2026gbfs,\n'
        '  author  = {Foss\\\'e, Rohan and Pallares, Ga\\"el},\n'
        '  title   = {Auditing GBFS bike-sharing feeds at country and global scale},\n'
        '  journal = {Computer Standards \\& Interfaces},\n'
        '  year    = {2026}\n'
        '}',
        language="bibtex",
    )


# ---------------------------------------------------------------------------
# Tab 2 -- Anomaly browser
# ---------------------------------------------------------------------------

with tab2:
    st.subheader("Browse the audit at the row level")
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
        "Operator (optional filter)",
        op_options,
        default=[],
    )

    flag_filters = st.multiselect(
        "Require at least one of these anomaly flags",
        [f"flag_A{i}" for i in range(1, 8)],
        default=[],
    )

    mask = (
        gs.station_type.isin(types)
        & gs.audit_confidence.isin(conf)
    )
    if operator:
        mask &= gs.operator_name.isin(operator)
    if flag_filters:
        any_flag = gs[flag_filters].any(axis=1)
        mask &= any_flag

    sub = gs[mask]
    st.caption(f"{len(sub):,} stations match the current filter (of {len(gs):,} total).")

    cols_show = [
        "uid", "city", "operator_name", "station_type",
        "capacity_raw", "capacity_audited",
        "flag_A1", "flag_A2", "flag_A3", "flag_A6", "flag_A7",
        "audit_confidence",
    ]
    st.dataframe(sub[cols_show].head(500), height=400, hide_index=True)

    csv = sub[cols_show].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered subset (CSV)",
        data=csv,
        file_name="filtered_subset.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Tab 3 -- Operator audit
# ---------------------------------------------------------------------------

with tab3:
    st.subheader("Per-operator anomaly profile")
    st.caption(
        "Operator-driven hotspots are the central finding of the paper :"
        " *Pony* propagates A3 across France, *Dott* and *Bird* propagate"
        " A7, *nextbike* propagates A2/A3 across the Czech Republic."
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
              high_confidence=(
                  "audit_confidence",
                  lambda s: float((s == "high").mean()),
              ),
          )
          .reset_index()
          .sort_values("n", ascending=False)
    )
    st.dataframe(
        op.style.format({
            "A1_rate": "{:.1%}",
            "A2_rate": "{:.1%}",
            "A3_rate": "{:.1%}",
            "A6_rate": "{:.1%}",
            "A7_rate": "{:.1%}",
            "high_confidence": "{:.1%}",
        }),
        height=440,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# Tab 4 -- Schema reference
# ---------------------------------------------------------------------------

with tab4:
    st.subheader("46-column schema")
    st.markdown(
        "Every column carries a stable name, a declared dtype, a source "
        "pointer and an empirical completeness rate. The full "
        "machine-readable schema (JSON Schema, DCAT-AP, Frictionless "
        "Data Package, Croissant JSON-LD) ships with the Zenodo deposit."
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
        height=540,
        hide_index=True,
    )

    st.subheader("The seven anomaly classes")
    for code, info in ANOMALY_CLASSES.items():
        st.markdown(f"**{code} -- {info['name']}** : {info['signature']}")
