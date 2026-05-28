# -*- coding: utf-8 -*-
"""GBFS Audit Catalogue — Interface d'annotation humaine v2.

Outil de validation ground-truth sur un échantillon stratifié de
175 stations.  Deux annotateurs indépendants évaluent chaque station
en trois phases (observation terrain, évaluation technique, verdict).
La fiabilité inter-annotateurs est calculée ensuite par
``compute_reliability.py``.

Usage :
    streamlit run experiments/annotation/annotator_app.py
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from storage import get_store

# =====================================================================
# Paths
# =====================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_PATH = Path(__file__).resolve().parent / "sample_200.csv"
LABELS_DIR = Path(__file__).resolve().parent
CATALOGUE_PATH = REPO_ROOT / "catalogue" / "stations_gold_standard_final.parquet"

# =====================================================================
# Evaluation options (key, display label)
# =====================================================================

GROUND_OPTIONS = [
    ("station_vls", "Vélos en libre-service"),
    ("trottinettes", "Trottinettes / motorisés"),
    ("autopartage", "Autopartage (voitures)"),
    ("aucune_infrastructure", "Rien de visible"),
    ("indetermine", "Incertain"),
]

INFRA_OPTIONS = [
    ("bornes_docks", "Bornes / docks"),
    ("velos_visibles", "Vélos ou VAE"),
    ("totem_signaletique", "Signalétique opérateur"),
    ("arceaux", "Arceaux vélo"),
    ("rien_visible", "Rien de visible"),
]

CAPACITY_OPTIONS = [
    ("coherente", "Oui, cohérente"),
    ("placeholder", "Placeholder (constante)"),
    ("champ_vide", "NaN (champ vide)"),
    ("zero_suspect", "Zéro suspect"),
    ("impossible", "Impossible à évaluer"),
]

LOCATION_OPTIONS = [
    ("integree_reseau", "Intégrée au réseau"),
    ("isolee_legitime", "Isolée mais légitime"),
    ("isolee_suspecte", "Isolée et suspecte"),
    ("coordonnees_erronees", "Coordonnées erronées"),
]

# Verdict is strictly pipeline-agnostic: the annotator judges the real-world
# state of the station, never whether "the pipeline is right". TP/FP/FN are
# derived a posteriori in compute_reliability.py by joining these factual
# answers with the pipeline flags.
VERDICT_OPTIONS = [
    ("legitime", "Oui — vraie station, correctement décrite"),
    ("problematique", "Non — absente, mal décrite, ou autre service"),
    ("indetermine", "Indéterminé"),
]

CONFIDENCE_OPTIONS = [1, 2, 3, 4, 5]

# Shown identically for every station — no per-stratum hint (anti-bias).
UNIVERSAL_RUBRIC = (
    "À partir de la carte, du satellite et de Street View, jugez "
    "l'<b>état réel du terrain</b> : (1) le type d'installation réellement "
    "présent, (2) l'infrastructure physique visible, (3) la cohérence de "
    "la capacité déclarée, (4) la cohérence de la position dans le réseau. "
    "Formez votre jugement <b>indépendamment de tout traitement "
    "automatique</b> — vous décrivez la réalité, vous n'évaluez aucun "
    "algorithme."
)

# =====================================================================
# Stratum colours and per-stratum guidelines
# =====================================================================

STRATUM_COLORS = {
    "clean_docked": "#27ae60",
    "A1_carsharing": "#8e44ad",
    "A2_placeholder": "#d35400",
    "A3_freefloating": "#2980b9",
    "A4_agree_flag": "#c0392b",
    "A4_discordant_legacy": "#e74c3c",
    "A4_discordant_composite": "#2471a3",
    "A5_out_of_perimeter": "#1a5276",
    "A6_zero_capacity": "#16a085",
    "A7_null_capacity": "#f39c12",
    "A3_boundary": "#7f8c8d",
}

FLAG_LABELS = {
    "A1": "Inclusion hors domaine (autopartage)",
    "A2": "Capacité placeholder (constante système)",
    "A3": "Sur-capacité structurelle (free-floating)",
    "A4": "Outlier géospatial (topologique composite)",
    "A5": "Hors périmètre (surface > 50 000 km²)",
    "A6": "Dock à zéro capacité",
    "A7": "Champ capacité nul / NaN",
}


# =====================================================================
# Helpers
# =====================================================================

def _opt_labels(options: list[tuple[str, str]]) -> list[str]:
    return [o[1] for o in options]


def _opt_key(options: list[tuple[str, str]], label: str | None) -> str | None:
    if label is None:
        return None
    for k, lbl in options:
        if lbl == label:
            return k
    return None


def _opt_index(options: list[tuple[str, str]], key: str | None) -> int | None:
    if key is None:
        return None
    keys = [o[0] for o in options]
    return keys.index(key) if key in keys else None


def _opt_default_labels(
    options: list[tuple[str, str]], keys: list[str] | None,
) -> list[str]:
    if not keys:
        return []
    key_to_label = {o[0]: o[1] for o in options}
    return [key_to_label[k] for k in keys if k in key_to_label]


def _format_elapsed(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}" if m else f"{s}s"


# =====================================================================
# Page config
# =====================================================================

st.set_page_config(
    page_title="Annotation GBFS — Ground Truth",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# =====================================================================
# Styles
# =====================================================================

st.markdown("""
<style>
/* Layout */
.block-container { padding-top: 0.4rem !important; max-width: 1440px; }
section[data-testid="stSidebar"] > div { padding-top: 0.7rem; }

/* Station header */
.station-header {
    display: flex; align-items: center; gap: 0.6rem;
    padding-bottom: 0.35rem; border-bottom: 2px solid #1A6FBF;
    margin-bottom: 0.35rem;
}
.station-num { font-size: 1.15rem; font-weight: 700; color: #1A2332; }
.station-ids { font-size: 0.78rem; color: #7a9bb8; }
.station-timer {
    margin-left: auto; font-size: 0.72rem; color: #b0bccb;
    font-variant-numeric: tabular-nums; font-family: monospace;
}

/* Badges */
.stratum-badge {
    display: inline-block; padding: 0.12rem 0.55rem;
    border-radius: 3px; font-size: 0.72rem; font-weight: 700;
    color: white; letter-spacing: 0.02em;
}
.status-badge {
    display: inline-block; padding: 0.08rem 0.4rem;
    border-radius: 3px; font-size: 0.66rem; font-weight: 600;
}
.status-done { background: #d5f5e3; color: #1e8449; }
.status-pending { background: #fdebd0; color: #d35400; }

/* Guideline box */
.guideline-box {
    background: #f0f4f8; border-left: 3px solid #1A6FBF;
    padding: 0.5rem 0.9rem; border-radius: 0 5px 5px 0;
    font-size: 0.84rem; margin-bottom: 0.4rem; line-height: 1.5;
    color: #2c3e50;
}

/* Form section headers */
[data-testid="stForm"] h3,
[data-testid="stForm"] strong {
    font-size: 0.9rem !important;
    color: #1A2332 !important;
    margin-top: 0.5rem !important;
}

/* Horizontal radio pills */
[data-testid="stForm"] [role="radiogroup"] {
    gap: 0.3rem !important;
}
[data-testid="stForm"] [role="radiogroup"] label {
    font-size: 0.84rem !important;
}

/* Links bar */
.links-bar {
    display: flex; gap: 0.4rem; flex-wrap: wrap;
    margin: 0.35rem 0 0.2rem;
}
.links-bar a {
    display: inline-block; padding: 0.22rem 0.55rem;
    border-radius: 4px; font-size: 0.74rem; font-weight: 600;
    text-decoration: none; border: 1px solid #ccc; color: #333;
    transition: background 0.15s;
}
.links-bar a:hover { background: #eee; }
.links-bar a.primary {
    background: #1A6FBF; color: white; border-color: #1A6FBF;
}
.links-bar a.primary:hover { background: #155a8a; }

/* Metadata grid */
.meta-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 0.25rem 0.8rem;
}
.meta-lbl {
    font-size: 0.68rem; color: #7a9bb8; text-transform: uppercase;
    letter-spacing: 0.04em;
}
.meta-val { font-size: 0.86rem; font-weight: 600; color: #1A2332; }

/* Map legend */
.map-legend {
    background: #fafbfc; border: 1px solid #e4ecf3;
    padding: 0.4rem 0.65rem; border-radius: 4px;
    font-size: 0.72rem; line-height: 1.6; margin-top: 0.25rem;
    columns: 2; column-gap: 1.2rem;
}
.map-legend b {
    font-size: 0.74rem; display: block;
    column-span: all; margin-bottom: 0.15rem;
}

/* Flag display */
.flag-active { color: #c0392b; font-weight: 700; }
.flag-inactive { color: #bdc3c7; }
.flag-row { font-size: 0.82rem; margin-bottom: 0.1rem; }

/* Transition message */
.transition-msg {
    background: #eafaf1; border-left: 3px solid #27ae60;
    padding: 0.35rem 0.8rem; border-radius: 0 4px 4px 0;
    font-size: 0.84rem; margin-bottom: 0.35rem;
}

/* Protocol card */
.protocol-card {
    background: #f8f9fb; border: 1px solid #e4ecf3;
    border-radius: 5px; padding: 0.5rem 0.7rem;
    font-size: 0.78rem; line-height: 1.55; color: #2c3e50;
    margin-top: 0.25rem;
}
.protocol-card h4 {
    font-size: 0.8rem; margin: 0.3rem 0 0.1rem; color: #1A6FBF;
}

/* Sidebar */
.sidebar-section {
    font-size: 0.62rem; text-transform: uppercase;
    letter-spacing: 0.12em; color: #5a7a96; font-weight: 600;
    margin: 0.8rem 0 0.25rem;
}
</style>
""", unsafe_allow_html=True)


# =====================================================================
# Session state
# =====================================================================

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:12]
if "start_times" not in st.session_state:
    st.session_state.start_times = {}
if "just_saved" not in st.session_state:
    st.session_state.just_saved = False
if "last_saved_station" not in st.session_state:
    st.session_state.last_saved_station = ""
if "session_count" not in st.session_state:
    st.session_state.session_count = 0


# =====================================================================
# Data loading
# =====================================================================

if not SAMPLE_PATH.exists():
    st.error(f"Fichier échantillon introuvable : `{SAMPLE_PATH}`")
    st.stop()

sample = pd.read_csv(SAMPLE_PATH)
sample["_key"] = sample.apply(
    lambda r: f"{r['system_id']}|{r['station_id']}", axis=1,
)

if CATALOGUE_PATH.exists():
    @st.cache_data
    def _load_catalogue():
        return pd.read_parquet(CATALOGUE_PATH)
    full_cat = _load_catalogue()
else:
    full_cat = None


# =====================================================================
# Sidebar — Session
# =====================================================================

with st.sidebar:
    st.markdown("## Annotation GBFS")

    # Predefined annotators (display name -> ASCII id used for DB / filenames).
    ANNOTATORS = {"Rohan": "rohan", "Gaël": "gael"}
    _PROMPT = "— Sélectionnez —"

    annotator_choice = st.selectbox(
        "Annotateur",
        [_PROMPT, *ANNOTATORS.keys()],
        index=0,
        key="annotator_name",
    )
    if annotator_choice not in ANNOTATORS:
        st.warning("Sélectionnez votre nom pour commencer l'annotation.")
        st.stop()

    annotator_name = annotator_choice
    annotator_id = ANNOTATORS[annotator_choice]


# =====================================================================
# Storage init + legacy migration
# =====================================================================

try:
    store = get_store()
except Exception as exc:  # noqa: BLE001
    st.error(
        "Connexion à la base de données impossible. Vérifiez "
        "`ANNOTATION_DB_URL` dans les secrets Streamlit.\n\n"
        f"Détail : {exc}"
    )
    st.stop()

legacy_path = LABELS_DIR / f"labels_{annotator_id}.csv"
if store.count(annotator_id) == 0 and legacy_path.exists():
    n_imported = store.import_legacy_csv(legacy_path, session_id="migration")
    if n_imported > 0:
        st.toast(f"{n_imported} annotations importées depuis {legacy_path.name}")

done_keys = store.get_done_keys(annotator_id)
remaining = sample[~sample["_key"].isin(done_keys)]
n_total = len(sample)
n_done = len(done_keys)


# =====================================================================
# Sidebar — Protocole expérimental
# =====================================================================

with st.sidebar:
    with st.expander("Protocole expérimental", expanded=False):
        st.markdown(
            "<div class='protocol-card'>"
            "<h4>Objectif</h4>"
            "Valider la taxonomie de 7 classes d'anomalies du pipeline "
            "GBFS via un jugement humain indépendant sur un échantillon "
            "stratifié de 175 stations (10 strates, échantillonnage "
            "proportionnel, SEED = 42)."
            "<h4>Design</h4>"
            "Deux annotateurs aveugles (indépendants, sans communication). "
            "Chaque annotateur évalue chaque station en 3 phases : "
            "observation terrain (imagerie), évaluation technique "
            "(cohérence des données), verdict final (avec confiance 1–5)."
            "<h4>Anti-biais</h4>"
            "Le verdict du pipeline est masqué par défaut dans un "
            "panneau rétractable. L'annotateur doit former son opinion "
            "à partir de la carte et de l'imagerie <i>avant</i> de "
            "consulter les flags du pipeline."
            "<h4>Fiabilité cible</h4>"
            "Kappa de Cohen &ge; 0.70 (accord substantiel) sur le verdict "
            "final. Si &kappa; &lt; 0.70, adjudication par un "
            "troisième expert."
            "<h4>Métriques calculées</h4>"
            "Kappa de Cohen par question, taux d'accord brut, "
            "précision / rappel / F1 par classe A1–A7 avec IC Wilson "
            "95 %, taux de faux positifs sur les strates discordantes."
            "<h4>Procédure</h4>"
            "<ol style='margin:0.2rem 0 0 1.1rem; padding:0;'>"
            "<li>Observez la carte CyclOSM et l'imagerie satellite</li>"
            "<li>Consultez Street View pour la vérification terrain</li>"
            "<li>Évaluez les données GBFS par rapport à vos observations</li>"
            "<li>Rendez votre verdict <b>indépendamment</b> du pipeline</li>"
            "<li>Notez votre niveau de confiance (1–5)</li>"
            "</ol>"
            "</div>",
            unsafe_allow_html=True,
        )


# =====================================================================
# Sidebar — Progression
# =====================================================================

with st.sidebar:
    st.markdown(
        "<div class='sidebar-section'>Progression</div>",
        unsafe_allow_html=True,
    )
    st.progress(n_done / n_total if n_total > 0 else 0.0)
    st.markdown(f"**{n_done}** / **{n_total}** stations annotées")

    med = store.median_duration(annotator_id)
    if med is not None and len(remaining) > 0:
        rest_min = med * len(remaining) / 60
        st.caption(
            f"Temps médian : {med:.0f}s/station — "
            f"Restant estimé : ~{rest_min:.0f} min"
        )
    elif n_done == 0:
        st.caption("Temps estimé : ~35s/station (baseline)")

    st.markdown(
        "<div class='sidebar-section'>Par strate</div>",
        unsafe_allow_html=True,
    )
    by_str = sample.copy()
    by_str["done"] = by_str["_key"].isin(done_keys)
    prog = (
        by_str.groupby("stratum")
        .agg(fait=("done", "sum"), total=("_key", "count"))
        .reset_index()
        .sort_values("total", ascending=False)
    )
    for _, r in prog.iterrows():
        color = STRATUM_COLORS.get(r["stratum"], "#999")
        pct = int(100 * r["fait"] / r["total"]) if r["total"] > 0 else 0
        bar_done = pct // 10
        bar = "█" * bar_done + "░" * (10 - bar_done)
        st.markdown(
            f"<span class='stratum-badge' style='background:{color};'>"
            f"{r['stratum']}</span> "
            f"<code style='font-size:0.72rem;'>{bar}</code> "
            f"<span style='font-size:0.78rem;'>"
            f"{int(r['fait'])}/{int(r['total'])}</span>",
            unsafe_allow_html=True,
        )


# =====================================================================
# Sidebar — Navigation (sans stratum pour éviter le biais)
# =====================================================================

with st.sidebar:
    st.markdown(
        "<div class='sidebar-section'>Navigation</div>",
        unsafe_allow_html=True,
    )

    first_pending_idx = 0
    for i in range(len(sample)):
        if sample.iloc[i]["_key"] not in done_keys:
            first_pending_idx = i
            break

    def _nav_label(idx: int) -> str:
        r = sample.iloc[idx]
        done = r["_key"] in done_keys
        city = str(r.get("city", ""))[:18]
        operator = str(r.get("operator_name", ""))[:15]
        tag = "OK" if done else "  "
        return f"[{tag}] {idx + 1}. {city} ({operator})"

    nav_idx = st.selectbox(
        "Aller à une station",
        range(len(sample)),
        index=first_pending_idx,
        format_func=_nav_label,
        key="nav_select",
        help="[OK] = déjà annotée (modifiable).",
    )


# =====================================================================
# Sidebar — Export
# =====================================================================

with st.sidebar:
    st.markdown(
        "<div class='sidebar-section'>Export</div>",
        unsafe_allow_html=True,
    )
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        if st.button(
            "Export CSV v2",
            use_container_width=True,
            help="Format 3 phases",
        ):
            export_path = LABELS_DIR / f"labels_v2_{annotator_id}.csv"
            store.export_csv(annotator_id, export_path)
            st.success(f"Exporté : {export_path.name}")
    with col_e2:
        if st.button(
            "Export legacy",
            use_container_width=True,
            help="Format Q1–Q5",
        ):
            export_path = LABELS_DIR / f"labels_{annotator_id}.csv"
            store.export_legacy_csv(annotator_id, export_path)
            st.success(f"Exporté : {export_path.name}")


# =====================================================================
# Completion screen
# =====================================================================

if len(remaining) == 0 and nav_idx == first_pending_idx:
    st.title("Annotation terminée")
    st.success(
        f"L'ensemble des {n_total} stations a été annoté par "
        f"**{annotator_name}**. Les labels sont dans la base SQLite "
        f"(`annotations.db`) et exportables en CSV."
    )
    st.markdown(
        "**Étape suivante** : exportez au format legacy (bouton dans la "
        "sidebar), puis calculez la fiabilité inter-annotateurs :\n\n"
        "```bash\n"
        "python -m experiments.annotation.compute_reliability \\\n"
        f"    --labels1 labels_{annotator_id}.csv \\\n"
        "    --labels2 labels_<autre>.csv \\\n"
        "    --output reliability_report.json\n"
        "```"
    )
    if nav_idx == first_pending_idx:
        st.stop()


# =====================================================================
# Current station
# =====================================================================

row = sample.iloc[nav_idx]
station_key = row["_key"]

if station_key not in st.session_state.start_times:
    st.session_state.start_times[station_key] = time.time()

lat = float(row["lat"]) if pd.notna(row.get("lat")) else None
lon = float(row["lon"]) if pd.notna(row.get("lon")) else None
stratum = row.get("stratum", "unknown")
is_revisit = station_key in done_keys

existing = store.get_annotation(
    annotator_id,
    str(row["system_id"]),
    str(row["station_id"]),
) if is_revisit else None


# =====================================================================
# Station header (sans stratum — anti-biais)
# =====================================================================

status_html = (
    "<span class='status-badge status-done'>"
    "Déjà annotée — modification</span>"
    if is_revisit
    else "<span class='status-badge status-pending'>En attente</span>"
)

elapsed = time.time() - st.session_state.start_times.get(
    station_key, time.time(),
)
timer_html = (
    f"<span class='station-timer'>{_format_elapsed(elapsed)}</span>"
)

st.markdown(
    f"<div class='station-header'>"
    f"  <span class='station-num'>Station {nav_idx + 1} / {n_total}</span>"
    f"  {status_html}"
    f"  <span class='station-ids'>"
    f"    {row.get('system_id', '')} / {row.get('station_id', '')}"
    f"  </span>"
    f"  {timer_html}"
    f"</div>",
    unsafe_allow_html=True,
)

if st.session_state.just_saved:
    prev = st.session_state.last_saved_station
    st.toast(f"Station {prev} enregistrée", icon="✅")
    st.session_state.just_saved = False

st.markdown(
    f"<div class='guideline-box'>{UNIVERSAL_RUBRIC}</div>",
    unsafe_allow_html=True,
)


# =====================================================================
# Map builder
# =====================================================================

def _build_map_html(
    lat: float,
    lon: float,
    station_id: str,
    network_points: list[dict],
) -> str:
    net_json = json.dumps(network_points, ensure_ascii=False)
    sid_safe = json.dumps(str(station_id))
    return f"""
    <div id="annomap" style="width:100%;height:600px;border-radius:6px;
         border:1px solid #d0d5dd;"></div>
    <link rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
    (function() {{
        var lat = {lat}, lon = {lon};

        var cyclosm = L.tileLayer(
            'https://{{s}}.tile-cyclosm.openstreetmap.fr/cyclosm/{{z}}/{{x}}/{{y}}.png',
            {{ maxZoom: 20, subdomains: 'abc',
               attribution: '<a href="https://cyclosm.org">CyclOSM</a> | OSM' }});
        var osm = L.tileLayer(
            'https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
            {{ maxZoom: 19, attribution: 'OSM' }});
        var satellite = L.tileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/' +
            'World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
            {{ maxZoom: 19, attribution: 'Esri World Imagery' }});

        var map = L.map('annomap', {{ layers: [cyclosm] }})
                   .setView([lat, lon], 17);

        L.circleMarker([lat, lon], {{
            radius: 13, color: '#c0392b', weight: 3,
            fillColor: '#e74c3c', fillOpacity: 0.85
        }}).addTo(map)
          .bindPopup('<b>Station à évaluer</b><br>' + {sid_safe})
          .openPopup();

        // Radius ring is available via the layer control but off by
        // default to reduce visual noise.
        var radius300 = L.circle([lat, lon], {{
            radius: 300, color: '#1A6FBF', weight: 1.5,
            fillColor: '#1A6FBF', fillOpacity: 0.04,
            dashArray: '6,4'
        }});

        var netGroup = L.layerGroup();
        var netData = {net_json};
        netData.forEach(function(pt) {{
            L.circleMarker([pt.lat, pt.lon], {{
                radius: 4, color: '#1A6FBF', weight: 1,
                fillColor: '#5dade2', fillOpacity: 0.45
            }}).addTo(netGroup);
        }});
        netGroup.addTo(map);

        var osmGroup = L.layerGroup();
        var q = '[out:json][timeout:10];(' +
            'node["amenity"="bicycle_rental"](around:400,' + lat + ',' + lon + ');' +
            'node["amenity"="bicycle_parking"](around:400,' + lat + ',' + lon + ');' +
            'node["amenity"="bicycle_repair_station"](around:400,' + lat + ',' + lon + ');' +
            ');out body;';
        fetch('https://overpass-api.de/api/interpreter?data=' + encodeURIComponent(q))
            .then(function(r) {{ return r.json(); }})
            .then(function(data) {{
                data.elements.forEach(function(el) {{
                    var isRental = el.tags.amenity === 'bicycle_rental';
                    var isRepair = el.tags.amenity === 'bicycle_repair_station';
                    var color = isRental ? '#e67e22' : isRepair ? '#8e44ad' : '#27ae60';
                    var rad = isRental ? 7 : 5;
                    var label = isRental ? 'Location vélos'
                              : isRepair ? 'Atelier vélo' : 'Parking vélos';
                    var name = (el.tags.name || label);
                    L.circleMarker([el.lat, el.lon], {{
                        radius: rad, color: color, weight: 2,
                        fillColor: color, fillOpacity: 0.6
                    }}).addTo(osmGroup).bindPopup(
                        '<b>' + name + '</b><br><i>' + label + '</i>'
                    );
                }});
                osmGroup.addTo(map);
            }})
            .catch(function() {{}});

        L.control.layers(
            {{ 'CyclOSM (infra cyclable)': cyclosm,
               'OpenStreetMap': osm,
               'Satellite (Esri)': satellite }},
            {{ 'Réseau opérateur': netGroup,
               'Infra OSM (Overpass)': osmGroup,
               'Rayon 300 m': radius300 }},
            {{ collapsed: false }}
        ).addTo(map);

        L.control.scale({{ metric: true, imperial: false }}).addTo(map);
    }})();
    </script>
    """


# =====================================================================
# Annotation panel (isolated fragment + persistence)
# =====================================================================

def _existing_label(options, existing_rec, field):
    """Display label for a previously stored option key (prefill helper)."""
    if not existing_rec:
        return None
    key = existing_rec.get(field)
    for k, lbl in options:
        if k == key:
            return lbl
    return None


def _persist(
    row, station_key, stratum, lat, lon,
    ground_label, infra_labels, sv_date,
    cap_label, loc_label, verdict_label, confidence, notes,
    is_skip=False,
):
    elapsed_s = time.time() - st.session_state.start_times.get(
        station_key, time.time(),
    )
    if is_skip:
        ground_key, infra_keys = "indetermine", []
        cap_key, loc_key, verdict_key = (
            "impossible", "integree_reseau", "skipped",
        )
        conf_val, sv, nt = 0, "", ""
    else:
        ground_key = _opt_key(GROUND_OPTIONS, ground_label) or "indetermine"
        infra_keys = [
            k for k in (
                _opt_key(INFRA_OPTIONS, l) for l in (infra_labels or [])
            ) if k
        ]
        cap_key = _opt_key(CAPACITY_OPTIONS, cap_label) or "impossible"
        loc_key = _opt_key(LOCATION_OPTIONS, loc_label) or "integree_reseau"
        verdict_key = _opt_key(VERDICT_OPTIONS, verdict_label) or "indetermine"
        conf_val = confidence or 3
        sv = (sv_date or "").strip()
        nt = (notes or "").strip()

    store.save({
        "session_id": st.session_state.session_id,
        "annotator": annotator_id,
        "system_id": str(row["system_id"]),
        "station_id": str(row["station_id"]),
        "stratum": stratum,
        "lat": lat,
        "lon": lon,
        "ground_reality": ground_key,
        "infrastructure_elements": infra_keys,
        "streetview_date": sv,
        "capacity_assessment": cap_key,
        "location_assessment": loc_key,
        "verdict": verdict_key,
        "confidence": conf_val,
        "notes": nt,
        "duration_s": round(elapsed_s, 1),
        "created_at": datetime.now(timezone.utc).isoformat(),
        **{
            f"flag_A{i}": int(bool(row.get(f"flag_A{i}", False)))
            for i in range(1, 8)
            if f"flag_A{i}" in row.index
        },
    })
    st.session_state.start_times.pop(station_key, None)
    st.session_state.just_saved = True
    st.session_state.last_saved_station = str(row.get("station_id", ""))
    if not is_skip:
        st.session_state.session_count += 1
    if "nav_select" in st.session_state:
        del st.session_state["nav_select"]


@st.fragment
def _annotation_panel(row, station_key, existing, cap_val, stratum, lat, lon):
    """Annotation controls isolated in a fragment: interacting with a
    widget reruns only this panel, so the Leaflet map never reloads."""
    st.markdown("**1 · Observation**")
    ground = st.segmented_control(
        "Type d'installation",
        _opt_labels(GROUND_OPTIONS),
        default=_existing_label(GROUND_OPTIONS, existing, "ground_reality"),
        key=f"ground_{station_key}",
    )
    infra = st.pills(
        "Éléments visibles sur le terrain",
        _opt_labels(INFRA_OPTIONS),
        selection_mode="multi",
        default=_opt_default_labels(
            INFRA_OPTIONS,
            existing.get("infrastructure_elements") if existing else None,
        ),
        key=f"infra_{station_key}",
    )
    sv_date = st.text_input(
        "Date imagerie Street View (facultatif)",
        value=(existing or {}).get("streetview_date", "") or "",
        placeholder="ex : juin 2024",
        key=f"svdate_{station_key}",
    )

    st.markdown("**2 · Évaluation**")
    cap_display = (
        cap_val if pd.notna(cap_val) and str(cap_val) != "nan" else "NaN"
    )
    cap = st.segmented_control(
        f"Capacité = {cap_display}. Cohérente ?",
        _opt_labels(CAPACITY_OPTIONS),
        default=_existing_label(
            CAPACITY_OPTIONS, existing, "capacity_assessment",
        ),
        key=f"cap_{station_key}",
    )
    loc = st.segmented_control(
        "Position dans le réseau de l'opérateur",
        _opt_labels(LOCATION_OPTIONS),
        default=_existing_label(
            LOCATION_OPTIONS, existing, "location_assessment",
        ),
        key=f"loc_{station_key}",
    )

    st.markdown("**3 · Synthèse**")
    verdict = st.segmented_control(
        "Vraie station vélo, présente et correctement décrite ?",
        _opt_labels(VERDICT_OPTIONS),
        default=_existing_label(VERDICT_OPTIONS, existing, "verdict"),
        key=f"verdict_{station_key}",
    )
    conf = st.pills(
        "Confiance (1 = incertain · 5 = très sûr)",
        CONFIDENCE_OPTIONS,
        default=(existing or {}).get("confidence", 3),
        key=f"conf_{station_key}",
    )
    notes = st.text_area(
        "Remarques (facultatif)",
        value=(existing or {}).get("notes", "") or "",
        placeholder="Date imagerie, station en travaux, doute...",
        key=f"notes_{station_key}",
        height=70,
    )

    missing = []
    if ground is None:
        missing.append("Installation")
    if cap is None:
        missing.append("Capacité")
    if loc is None:
        missing.append("Position")
    if verdict is None:
        missing.append("Synthèse")
    all_ok = not missing

    b1, b2 = st.columns([3, 1])
    save = b1.button(
        "Enregistrer et continuer",
        type="primary",
        disabled=not all_ok,
        use_container_width=True,
        key=f"save_{station_key}",
    )
    skip = b2.button(
        "Passer", use_container_width=True, key=f"skip_{station_key}",
    )
    if missing:
        st.caption("À compléter : " + ", ".join(missing))

    if save and all_ok:
        _persist(
            row, station_key, stratum, lat, lon,
            ground, infra, sv_date, cap, loc, verdict, conf, notes,
            is_skip=False,
        )
        st.rerun(scope="app")
    if skip:
        _persist(
            row, station_key, stratum, lat, lon,
            None, None, None, None, None, None, None, None,
            is_skip=True,
        )
        st.rerun(scope="app")


# =====================================================================
# Split-screen : dominant map (left) | annotation panel (right)
# =====================================================================

col_map, col_panel = st.columns([1.4, 1])

with col_map:
    if lat is not None and lon is not None:
        network_points: list[dict] = []
        if full_cat is not None:
            same = full_cat[full_cat["system_id"] == row["system_id"]].copy()
            same = same[
                same["station_id"].astype(str) != str(row["station_id"])
            ]
            if len(same) > 300:
                same["_d"] = (
                    (same["lat"] - lat) ** 2 + (same["lon"] - lon) ** 2
                )
                same = same.nsmallest(300, "_d")
            network_points = (
                same[["lat", "lon"]].dropna().to_dict("records")
            )

        # st.iframe replaces the deprecated st.components.v1.html
        # (removed after 2026-06-01); it embeds the HTML string in a
        # sandboxed iframe that runs the Leaflet scripts.
        st.iframe(
            _build_map_html(
                lat, lon, str(row["station_id"]), network_points,
            ),
            height=620,
        )

        sv_url = (
            f"https://www.google.com/maps/@?api=1"
            f"&map_action=pano&viewpoint={lat},{lon}"
        )
        cyclosm_url = f"https://www.cyclosm.org/#map=17/{lat}/{lon}/cyclosm"
        osm_url = (
            f"https://www.openstreetmap.org/"
            f"?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}"
        )
        osm_query = (
            f"https://www.openstreetmap.org/query"
            f"?lat={lat}&lon={lon}#map=18/{lat}/{lon}"
        )
        gmaps = f"https://www.google.com/maps/@{lat},{lon},18z"

        st.markdown(
            f"<div class='links-bar'>"
            f"<a class='primary' href='{sv_url}' target='_blank'>"
            f"Street View</a>"
            f"<a href='{cyclosm_url}' target='_blank'>"
            f"CyclOSM plein écran</a>"
            f"<a href='{osm_url}' target='_blank'>OpenStreetMap</a>"
            f"<a href='{osm_query}' target='_blank'>Interroger OSM</a>"
            f"<a href='{gmaps}' target='_blank'>Google Maps</a>"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='map-legend'>"
            "<b>Légende carte</b>"
            "<div><span style='color:#e74c3c;font-weight:700;'>"
            "&#9679;</span> Station à évaluer</div>"
            "<div><span style='color:#5dade2;'>"
            "&#9679;</span> Autres stations du réseau</div>"
            "<div><span style='color:#e67e22;'>"
            "&#9679;</span> Location vélos (OSM)</div>"
            "<div><span style='color:#27ae60;'>"
            "&#9679;</span> Parking vélos (OSM)</div>"
            "<div><span style='color:#8e44ad;'>"
            "&#9679;</span> Atelier vélo (OSM)</div>"
            "<div><span style='color:#1A6FBF;opacity:0.5;'>"
            "- - -</span> Rayon 300 m</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("Coordonnées indisponibles pour cette station.")


with col_panel:
    st.markdown("**Métadonnées GBFS**")
    cap_val = row.get("capacity", "?")
    meta_pairs = [
        ("Opérateur", row.get("operator_name")),
        ("Ville", row.get("city")),
        ("Capacité brute", cap_val),
        ("Coordonnées", f"{lat:.5f}, {lon:.5f}" if lat and lon else None),
    ]

    meta_html = "<div class='meta-grid'>"
    for label, val in meta_pairs:
        v = str(val) if pd.notna(val) else "<i>non renseigné</i>"
        meta_html += (
            f"<div><span class='meta-lbl'>{label}</span>"
            f"<div class='meta-val'>{v}</div></div>"
        )
    meta_html += "</div>"
    st.markdown(meta_html, unsafe_allow_html=True)

    if full_cat is not None:
        same_sys = full_cat[full_cat["system_id"] == row["system_id"]]
        n_sys = len(same_sys)
        if lat and lon and len(same_sys) > 1:
            dists = np.sqrt(
                (same_sys["lat"].values - lat) ** 2
                + (same_sys["lon"].values - lon) ** 2
            ) * 111_000
            dists = dists[dists > 1]
            nearest_m = int(np.min(dists)) if len(dists) > 0 else None
            n_500 = int((dists < 500).sum()) if len(dists) > 0 else 0
        else:
            nearest_m, n_500 = None, 0

        st.markdown("")
        st.markdown("**Contexte réseau**")
        ctx_html = "<div class='meta-grid'>"
        ctx_html += (
            f"<div><span class='meta-lbl'>Stations dans le système</span>"
            f"<div class='meta-val'>{n_sys}</div></div>"
        )
        if nearest_m is not None:
            ctx_html += (
                f"<div><span class='meta-lbl'>Station la plus proche</span>"
                f"<div class='meta-val'>{nearest_m} m</div></div>"
            )
        ctx_html += (
            f"<div><span class='meta-lbl'>Stations dans 500 m</span>"
            f"<div class='meta-val'>{n_500}</div></div>"
        )
        ctx_html += "</div>"
        st.markdown(ctx_html, unsafe_allow_html=True)

    st.markdown("")
    with st.expander(
        "Verdict du pipeline (peut biaiser votre jugement)",
        expanded=False,
    ):
        st.caption(
            "Consultez ces informations uniquement après avoir "
            "formé votre propre opinion à partir de la carte "
            "et de l'imagerie."
        )

        audit_conf = row.get("audit_confidence")
        station_type = row.get("station_type")
        if pd.notna(audit_conf) or pd.notna(station_type):
            st.markdown(
                f"<div style='font-size:0.82rem; margin-bottom:0.3rem;'>"
                f"Type audité : <b>{station_type}</b> · "
                f"Confiance : <b>{audit_conf}</b>"
                f"</div>",
                unsafe_allow_html=True,
            )

        any_flag = False
        for i in range(1, 8):
            col_name = f"flag_A{i}"
            is_on = (
                bool(row.get(col_name, False))
                if col_name in row.index
                else False
            )
            if is_on:
                any_flag = True
            css = "flag-active" if is_on else "flag-inactive"
            marker = "ACTIF" if is_on else "inactif"
            desc = FLAG_LABELS.get(f"A{i}", "")
            st.markdown(
                f"<div class='flag-row'>"
                f"<span class='{css}'>A{i} [{marker}]</span> "
                f"<span style='color:#999; font-size:0.76rem;'>"
                f"{desc}</span></div>",
                unsafe_allow_html=True,
            )
        if not any_flag:
            st.markdown(
                "<div style='color:#27ae60; font-size:0.84rem; "
                "font-weight:600; margin-top:0.2rem;'>"
                "Aucun flag déclenché — station considérée propre "
                "par le pipeline.</div>",
                unsafe_allow_html=True,
            )


    # Annotation form (isolated fragment — the map never reloads on input)
    _annotation_panel(row, station_key, existing, cap_val, stratum, lat, lon)
