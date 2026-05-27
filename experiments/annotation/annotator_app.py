"""GBFS Audit — Human Annotation Tool (Ground-Truth Validation).

A research-grade annotation interface for the stratified 175-station
sample. Two independent annotators label each station against the
A1–A7 taxonomy; inter-rater reliability is computed offline via
compute_reliability.py.

Usage:
    streamlit run experiments/annotation/annotator_app.py
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_PATH = Path(__file__).resolve().parent / "sample_200.csv"
LABELS_DIR = Path(__file__).resolve().parent
CATALOGUE_PATH = REPO_ROOT / "catalogue" / "stations_gold_standard_final.parquet"

STRATUM_COLORS = {
    "clean_docked": "#2ecc71",
    "A1_carsharing": "#9b59b6",
    "A2_placeholder": "#e67e22",
    "A3_freefloating": "#3498db",
    "A4_agree_flag": "#e74c3c",
    "A4_discordant_legacy": "#c0392b",
    "A4_discordant_composite": "#2980b9",
    "A6_zero_capacity": "#1abc9c",
    "A7_null_capacity": "#f39c12",
    "A3_boundary": "#7f8c8d",
}

STRATUM_DESCRIPTIONS = {
    "clean_docked": "No flag triggered, high confidence, dock-based. Check for false negatives.",
    "A1_carsharing": "Flagged as car-sharing. Verify: is this a bike-sharing station or a car fleet?",
    "A2_placeholder": "System-wide identical capacity. Verify: is capacity a real dock count or a placeholder?",
    "A3_freefloating": "Flagged as free-floating virtual anchor. Verify: physical docks or GPS waypoint?",
    "A4_agree_flag": "Both legacy centroid and composite detector flag this station as a geospatial outlier.",
    "A4_discordant_legacy": "Legacy centroid flags this station, but the composite does NOT. Is this a true outlier?",
    "A4_discordant_composite": "Composite flags this station, but the legacy centroid does NOT. New finding?",
    "A6_zero_capacity": "Station declares capacity = 0. Does this physical station actually have zero docks?",
    "A7_null_capacity": "Station declares capacity = NaN. Does the operator simply not publish this field?",
    "A3_boundary": "Capacity ratio in [2, 5] — the A3 threshold grey zone. Dock-based or virtual?",
}

FLAG_NAMES = {
    "A1": "Out-of-domain inclusion (car-sharing)",
    "A2": "Placeholder capacity (constant across system)",
    "A3": "Structural over-capacity (free-floating anchor)",
    "A4": "Geospatial outlier (topology-aware composite)",
    "A5": "Out-of-perimeter (bbox > 50,000 km²)",
    "A6": "Zero-capacity dock (semantic warning)",
    "A7": "Null capacity field (semantic warning)",
}

# ─── Page config ─────────────────────────────────────────────────────

st.set_page_config(
    page_title="GBFS Annotation Tool",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    div[data-testid="stRadio"] > label { font-size: 0.88rem; }
    .stratum-badge {
        display: inline-block;
        padding: 0.15rem 0.55rem;
        border-radius: 3px;
        font-size: 0.75rem;
        font-weight: 700;
        color: white;
        letter-spacing: 0.03em;
    }
    .guideline-box {
        background: #f0f4f8;
        border-left: 3px solid #1A6FBF;
        padding: 0.6rem 0.9rem;
        border-radius: 0 4px 4px 0;
        font-size: 0.85rem;
        margin-bottom: 0.8rem;
    }
    .flag-chip {
        display: inline-block;
        padding: 0.1rem 0.45rem;
        border-radius: 3px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-right: 0.3rem;
        margin-bottom: 0.2rem;
    }
    .flag-on { background: #e74c3c; color: white; }
    .flag-off { background: #ecf0f1; color: #95a5a6; }
</style>
""", unsafe_allow_html=True)

# ─── Session state ───────────────────────────────────────────────────

if "annotation_start_times" not in st.session_state:
    st.session_state.annotation_start_times = {}

# ─── Sidebar: annotator + protocol ──────────────────────────────────

with st.sidebar:
    st.markdown("## 🔬 Annotation Session")

    annotator_name = st.text_input(
        "Annotator name",
        value="",
        placeholder="e.g. Rohan",
        key="annotator_name",
    )
    if not annotator_name.strip():
        st.warning("Enter your name to begin.")
        st.stop()

    annotator_id = annotator_name.strip().lower().replace(" ", "_")
    labels_path = LABELS_DIR / f"labels_{annotator_id}.csv"

    st.markdown("---")
    st.markdown("### Protocol summary")
    st.markdown(
        "For each station, you will see:\n"
        "- A **map** with the station's location (+ network context)\n"
        "- **Satellite / Street View** links for visual verification\n"
        "- **Metadata** from the GBFS feed and the audit pipeline\n"
        "- A **guideline** specific to this station's stratum\n\n"
        "Answer the **5 questions** based on what you observe, "
        "then click **Save & Next**."
    )

    st.markdown(
        "<div class='guideline-box'>"
        "<b>Key principle:</b> you are the ground truth. "
        "If the pipeline says 'anomaly' but you see a legitimate station "
        "on Street View, label it <b>pipeline false positive</b>."
        "</div>",
        unsafe_allow_html=True,
    )

# ─── Load data ───────────────────────────────────────────────────────

if not SAMPLE_PATH.exists():
    st.error(f"Sample not found: `{SAMPLE_PATH}`")
    st.stop()

sample = pd.read_csv(SAMPLE_PATH)

if labels_path.exists():
    labels_df = pd.read_csv(labels_path)
    done_keys = set(
        labels_df.apply(lambda r: f"{r['system_id']}|{r['station_id']}", axis=1)
    )
else:
    labels_df = pd.DataFrame()
    done_keys = set()

sample["_key"] = sample.apply(
    lambda r: f"{r['system_id']}|{r['station_id']}", axis=1
)
remaining = sample[~sample["_key"].isin(done_keys)]
n_total = len(sample)
n_done = n_total - len(remaining)

# Load full catalogue for network context
if CATALOGUE_PATH.exists():
    @st.cache_data
    def _load_catalogue():
        return pd.read_parquet(CATALOGUE_PATH)
    full_cat = _load_catalogue()
else:
    full_cat = None

# ─── Sidebar: progress ──────────────────────────────────────────────

with st.sidebar:
    st.markdown("---")
    st.markdown("### Progress")
    st.progress(n_done / n_total if n_total > 0 else 0.0)
    st.markdown(
        f"**{n_done}** / **{n_total}** stations annotated "
        f"({100 * n_done / n_total:.0f}%)"
    )

    if n_done > 0 and labels_path.exists():
        times = pd.read_csv(labels_path)
        non_skip = times[times["Q5_verdict"] != "skipped"]
        if "duration_s" in non_skip.columns and len(non_skip) > 0:
            median_time = non_skip["duration_s"].median()
            remaining_est = median_time * len(remaining) / 60
            st.caption(
                f"Median annotation time: {median_time:.0f}s per station · "
                f"Est. remaining: {remaining_est:.0f} min"
            )

    st.markdown("#### Per-stratum progress")
    by_stratum = sample.copy()
    by_stratum["done"] = by_stratum["_key"].isin(done_keys)
    progress = (
        by_stratum.groupby("stratum")
        .agg(done=("done", "sum"), total=("_key", "count"))
        .reset_index()
    )
    progress["pct"] = (progress["done"] / progress["total"] * 100).astype(int)
    for _, r in progress.iterrows():
        color = STRATUM_COLORS.get(r["stratum"], "#999")
        pct = r["pct"]
        st.markdown(
            f"<span class='stratum-badge' style='background:{color};'>"
            f"{r['stratum']}</span> "
            f"{'█' * (pct // 10)}{'░' * (10 - pct // 10)} "
            f"{r['done']}/{r['total']}",
            unsafe_allow_html=True,
        )

# ─── Done screen ─────────────────────────────────────────────────────

if len(remaining) == 0:
    st.title("🎉 Annotation complete")
    st.success(
        f"All {n_total} stations annotated by **{annotator_name}**. "
        f"Labels saved to `{labels_path.name}`."
    )
    st.markdown(
        "**Next steps:**\n"
        "1. Ask the second annotator to run their session\n"
        "2. Compute inter-rater reliability:\n"
        "```bash\n"
        "python -m experiments.annotation.compute_reliability \\\n"
        f"    --labels1 {labels_path.name} \\\n"
        "    --labels2 labels_<other>.csv \\\n"
        "    --output reliability_report.json\n"
        "```"
    )
    st.stop()

# ─── Current station ─────────────────────────────────────────────────

row = remaining.iloc[0]
station_key = row["_key"]

if station_key not in st.session_state.annotation_start_times:
    st.session_state.annotation_start_times[station_key] = time.time()

lat = float(row["lat"]) if pd.notna(row.get("lat")) else None
lon = float(row["lon"]) if pd.notna(row.get("lon")) else None
stratum = row.get("stratum", "unknown")
stratum_color = STRATUM_COLORS.get(stratum, "#999")
stratum_desc = STRATUM_DESCRIPTIONS.get(stratum, "")

# ─── Header ──────────────────────────────────────────────────────────

st.markdown(
    f"<div style='display:flex; align-items:center; gap:0.8rem; margin-bottom:0.6rem;'>"
    f"<span style='font-size:1.4rem; font-weight:700;'>Station {n_done + 1} / {n_total}</span>"
    f"<span class='stratum-badge' style='background:{stratum_color};'>{stratum}</span>"
    f"<span style='color:#666; font-size:0.85rem;'>"
    f"{row.get('system_id', '')} → {row.get('station_id', '')}</span>"
    f"</div>",
    unsafe_allow_html=True,
)

st.markdown(
    f"<div class='guideline-box'>"
    f"<b>Stratum guideline:</b> {stratum_desc}"
    f"</div>",
    unsafe_allow_html=True,
)

# ─── Three-column layout: Map | Metadata | Flags ────────────────────

col_map, col_meta, col_flags = st.columns([5, 3, 2])

with col_map:
    st.markdown("#### 📍 Location & network context")

    if lat is not None and lon is not None:
        system_id = row.get("system_id")
        map_data = pd.DataFrame({"lat": [lat], "lon": [lon]})

        layers = []

        if full_cat is not None and system_id:
            siblings = full_cat[full_cat["system_id"] == system_id][["lat", "lon"]].dropna()
            if len(siblings) > 1:
                siblings = siblings.copy()
                siblings["color"] = [[180, 200, 220, 120]] * len(siblings)
                siblings["radius"] = 40
                layers.append(pdk.Layer(
                    "ScatterplotLayer",
                    data=siblings,
                    get_position=["lon", "lat"],
                    get_fill_color="color",
                    get_radius="radius",
                    pickable=False,
                ))

        target_df = pd.DataFrame({
            "lat": [lat], "lon": [lon],
            "color": [[231, 76, 60, 255]],
            "radius": [120],
        })
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=target_df,
            get_position=["lon", "lat"],
            get_fill_color="color",
            get_radius="radius",
            pickable=False,
        ))

        view = pdk.ViewState(latitude=lat, longitude=lon, zoom=14, pitch=0)
        st.pydeck_chart(
            pdk.Deck(
                map_style="mapbox://styles/mapbox/satellite-streets-v12",
                initial_view_state=view,
                layers=layers,
            ),
            use_container_width=True,
        )

        st.markdown(
            f"🌍 [Google Maps](https://www.google.com/maps/@{lat},{lon},18z) · "
            f"[Street View](https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}) · "
            f"[OpenStreetMap](https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=18)",
        )
    else:
        st.warning("No coordinates available.")

with col_meta:
    st.markdown("#### 📋 Metadata")
    meta = {
        "Operator": row.get("operator_name", "—"),
        "City": row.get("city", "—"),
        "Station type": row.get("station_type", "—"),
        "Capacity (raw)": row.get("capacity", "—"),
        "Confidence": row.get("audit_confidence", "—"),
        "Latitude": f"{lat:.6f}" if lat else "—",
        "Longitude": f"{lon:.6f}" if lon else "—",
    }
    for k, v in meta.items():
        val = str(v) if pd.notna(v) else "—"
        st.markdown(f"**{k}:** `{val}`")

with col_flags:
    st.markdown("#### 🚩 Audit flags")
    for i in range(1, 8):
        col_name = f"flag_A{i}"
        is_on = bool(row.get(col_name, False)) if col_name in row.index else False
        css_class = "flag-on" if is_on else "flag-off"
        label = f"A{i}"
        tooltip = FLAG_NAMES.get(f"A{i}", "")
        st.markdown(
            f"<span class='flag-chip {css_class}' title='{tooltip}'>"
            f"{label}</span> "
            f"<span style='font-size:0.78rem; color:#666;'>{tooltip}</span>",
            unsafe_allow_html=True,
        )

# ─── Annotation form ─────────────────────────────────────────────────

st.markdown("---")
st.markdown("### ✏️ Your assessment")

q_col1, q_col2 = st.columns(2)

with q_col1:
    a_q1 = st.radio(
        "**Q1.** Is this a bike-sharing station?",
        ["yes", "no", "indeterminate"],
        index=None,
        key="q1",
        help="Check the vehicle type. Bicycles / e-bikes = yes. Cars / scooters only = no.",
    )

    a_q3 = st.radio(
        "**Q3.** Does this station physically exist at these coordinates?",
        ["yes", "no", "indeterminate"],
        index=None,
        key="q3",
        help="Use satellite imagery or Street View. Look for bike docks, racks, or signage.",
    )

    a_q5 = st.radio(
        "**Q5.** Overall verdict:",
        ["clean", "anomaly confirmed", "pipeline false positive", "indeterminate"],
        index=None,
        key="q5",
    )

with q_col2:
    a_q2 = st.radio(
        "**Q2.** Does the declared capacity reflect a physical dock count?",
        ["yes", "no", "NaN", "indeterminate"],
        index=None,
        key="q2",
        help="A real dock count (e.g. 20 slots) = yes. Placeholder (e.g. 100 everywhere) = no. Missing = NaN.",
    )

    a_q4 = st.radio(
        "**Q4.** Are these coordinates within the network's operating area?",
        ["yes", "no"],
        index=None,
        key="q4",
        help="Is this station geographically consistent with its siblings (shown in grey on the map)?",
    )

    notes = st.text_area(
        "Notes (optional)",
        value="",
        placeholder="Street View date, construction, unclear imagery...",
        key="notes",
        height=100,
    )

# ─── Save / Skip ─────────────────────────────────────────────────────

all_answered = all([a_q1, a_q2, a_q3, a_q4, a_q5])

col_a, col_b, col_c = st.columns([2, 1, 1])

with col_a:
    if st.button(
        "✅  Save & Next",
        type="primary",
        disabled=not all_answered,
        use_container_width=True,
    ):
        elapsed = time.time() - st.session_state.annotation_start_times.get(station_key, time.time())

        new_row = {
            "system_id": row["system_id"],
            "station_id": row["station_id"],
            "stratum": stratum,
            "lat": lat,
            "lon": lon,
            "Q1_is_bikeshare": a_q1,
            "Q2_capacity_physical": a_q2,
            "Q3_exists_at_coords": a_q3,
            "Q4_within_perimeter": a_q4,
            "Q5_verdict": a_q5,
            "annotator": annotator_id,
            "notes": notes,
            "duration_s": round(elapsed, 1),
            "annotated_at": datetime.now(timezone.utc).isoformat(),
        }

        if labels_path.exists():
            existing = pd.read_csv(labels_path)
            updated = pd.concat([existing, pd.DataFrame([new_row])], ignore_index=True)
        else:
            updated = pd.DataFrame([new_row])
        updated.to_csv(labels_path, index=False)

        st.session_state.annotation_start_times.pop(station_key, None)
        st.rerun()

with col_b:
    if st.button("⏭️  Skip", use_container_width=True):
        skip_row = {
            "system_id": row["system_id"],
            "station_id": row["station_id"],
            "stratum": stratum,
            "lat": lat,
            "lon": lon,
            "Q1_is_bikeshare": "skipped",
            "Q2_capacity_physical": "skipped",
            "Q3_exists_at_coords": "skipped",
            "Q4_within_perimeter": "skipped",
            "Q5_verdict": "skipped",
            "annotator": annotator_id,
            "notes": "SKIPPED",
            "duration_s": 0,
            "annotated_at": datetime.now(timezone.utc).isoformat(),
        }
        if labels_path.exists():
            existing = pd.read_csv(labels_path)
            updated = pd.concat([existing, pd.DataFrame([skip_row])], ignore_index=True)
        else:
            updated = pd.DataFrame([skip_row])
        updated.to_csv(labels_path, index=False)
        st.session_state.annotation_start_times.pop(station_key, None)
        st.rerun()

with col_c:
    if n_done > 0 and st.button("📊  My stats", use_container_width=True):
        st.session_state["show_stats"] = not st.session_state.get("show_stats", False)

if not all_answered:
    st.caption("Answer all 5 questions to enable Save.")

# ─── Stats panel ─────────────────────────────────────────────────────

if st.session_state.get("show_stats", False) and labels_path.exists():
    st.markdown("---")
    st.markdown("### 📊 Session analytics")
    stats_df = pd.read_csv(labels_path)
    non_skip = stats_df[stats_df["Q5_verdict"] != "skipped"]

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Annotated", len(non_skip))
    s2.metric("Skipped", len(stats_df) - len(non_skip))
    if "duration_s" in non_skip.columns and len(non_skip) > 0:
        s3.metric("Median time", f"{non_skip['duration_s'].median():.0f}s")
        s4.metric("Total time", f"{non_skip['duration_s'].sum() / 60:.0f} min")

    if len(non_skip) > 0:
        verdict_counts = non_skip["Q5_verdict"].value_counts()
        st.markdown("**Verdict distribution:**")
        for v, c in verdict_counts.items():
            pct = 100 * c / len(non_skip)
            st.markdown(f"- **{v}**: {c} ({pct:.0f}%)")
