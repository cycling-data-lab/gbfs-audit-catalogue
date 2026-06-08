# -*- coding: utf-8 -*-
"""GBFS Audit — Cascade annotation interface (v2).

Single page, one question at a time. The imagery panel (Leaflet satellite +
operator network + 1 km ring, and a keyless Google Street View tab) is rendered
once at the top; the question flow runs inside an ``@st.fragment`` so answering
a question reloads only the question area, never the imagery.

Routing (conditional cascade, hidden from the annotator — they see one
question at a time):

    Q0  libre-service ?            non/indéterminé -> fin (A1 / indéterminé)
    Q1  docks présents ?           (si Q0=oui)
    Q2  combien de docks ?         (si Q1=oui ; échelle ordinale, anti-ancrage)
    Q3a périmètre valide ?         (si Q0=oui)
    Q3b au contact du réseau ?     (si Q0=oui)

Usage:
    streamlit run experiments/annotation_cascade/annotator_app.py
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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_PATH = Path(__file__).resolve().parent / "sample.csv"
LABELS_DIR = Path(__file__).resolve().parent
CATALOGUE_PATH = REPO_ROOT / "catalogue" / "stations_gold_standard_final.parquet"

ANNOTATORS = {"Rohan": "rohan", "Gaël": "gael"}

# --- Question definitions (one shown at a time) -----------------------------
BIN = [("oui", "OUI"), ("non", "NON"), ("indéterminé", "INDÉTERMINÉ")]
DOCK_CLASSES = ["1–5", "6–10", "11–20", "21–30", "31–50", ">50", "Indéterminé"]

QUESTIONS = {
    "q0": {
        "col": "q0_libre_service",
        "text": "S'agit-il d'un service de vélos ou trottinettes en libre-service ?",
        "sub": "(et NON de l'autopartage de voitures, ou d'un autre objet)",
        "type": "binary",
        "view": "map",
        "hint": "Vérification documentaire : nom de l'opérateur, ville, site.",
    },
    "q1": {
        "col": "q1_docks_presents",
        "text": "À cet endroit, voit-on des docks physiques ?",
        "sub": "borne fixe, points de verrouillage, structure de station matérialisée",
        "type": "binary",
        "view": "street",
        "hint": "Satellite (vue du dessus) + Street View. Station vide mais avec bornes = OUI.",
    },
    "q2": {
        "col": "q2_nb_docks_classe",
        "text": "Combien de points d'ancrage (docks) comptez-vous ?",
        "sub": "comptez ce que vous voyez — ne devinez pas la valeur du flux",
        "type": "ordinal",
        "view": "map",
        "hint": "Satellite vue du dessus. Si non dénombrable → Indéterminé.",
    },
    "q3a": {
        "col": "q3a_perimetre",
        "text": "L'emplacement est-il géographiquement valide ?",
        "sub": "sur la terre ferme ET dans le bon pays / la bonne agglomération",
        "type": "binary",
        "view": "map",
        "hint": "Point en mer / champ / mauvais pays = NON.",
    },
    "q3b": {
        "col": "q3b_proximite",
        "text": "L'emplacement est-il au contact de son réseau ?",
        "sub": "à moins de 1 km d'une autre station du même opérateur, ou dans l'enveloppe du réseau",
        "type": "binary",
        "view": "map",
        "hint": "Stations sœurs en bleu, cercle de 1 km affiché. Isolée au-delà = NON.",
    },
}


def active_sequence(ans: dict) -> list[str]:
    """Ordered list of questions that apply given the answers so far."""
    seq = ["q0"]
    if ans.get("q0_libre_service") == "oui":
        seq.append("q1")
        if ans.get("q1_docks_presents") == "oui":
            seq.append("q2")
        seq += ["q3a", "q3b"]
    return seq


def derive_verdict(ans: dict) -> str:
    q0 = ans.get("q0_libre_service")
    if q0 == "non":
        return "A1"
    if q0 != "oui":
        return "INDET"
    q1 = ans.get("q1_docks_presents")
    if q1 == "oui":
        type_part = "DOCK"
    elif q1 == "non":
        type_part = "NO_DOCKS"
    else:
        type_part = "INDET"
    peri = ans.get("q3a_perimetre")
    prox = ans.get("q3b_proximite")
    if peri == "non":
        place = "A5"
    elif prox == "non":
        place = "A4"
    elif peri == "oui" and prox == "oui":
        place = "PLACED"
    else:
        place = "PLACE_INDET"
    return f"{type_part}|{place}"


# ============================================================================
st.set_page_config(page_title="Annotation GBFS — Cascade", layout="wide")

st.markdown("""
<style>
.block-container { padding-top: 0.6rem !important; max-width: 1500px; }
.qcard { background:#f7f9fc; border:1px solid #e3eaf2; border-radius:8px;
         padding:1.0rem 1.2rem; margin-top:0.4rem; }
.qnum { font-size:0.8rem; color:#6b8299; font-weight:700; letter-spacing:0.03em; }
.qtext { font-size:1.45rem; font-weight:700; color:#1A2332; line-height:1.25;
         margin:0.25rem 0 0.15rem; }
.qsub { font-size:0.92rem; color:#5a6b7b; margin-bottom:0.2rem; }
.qhint { font-size:0.82rem; color:#5a7088; background:#eef3f8;
         border-left:3px solid #1A6FBF; padding:0.35rem 0.7rem;
         border-radius:0 4px 4px 0; margin:0.5rem 0 0.7rem; }
.meta-line { font-size:0.9rem; color:#34495e; }
.stButton button { font-size:1.05rem !important; font-weight:700 !important;
                   padding:0.6rem 0 !important; }
</style>
""", unsafe_allow_html=True)

# --- Session state ----------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:12]
if "start_times" not in st.session_state:
    st.session_state.start_times = {}

# --- Sidebar ----------------------------------------------------------------
with st.sidebar:
    st.markdown("## Annotation cascade")
    annotator_choice = st.selectbox("Annotateur", ["— Sélectionnez —", *ANNOTATORS])
    if annotator_choice not in ANNOTATORS:
        st.warning("Sélectionnez votre nom pour commencer.")
        st.stop()
    annotator_id = ANNOTATORS[annotator_choice]
    revisit_round = st.selectbox(
        "Tour", [0, 1],
        format_func=lambda r: "Tour principal" if r == 0 else "Re-test (fiabilité intra)",
        help="Le re-test (2 semaines après) mesure la stabilité intra-annotateur.",
    )

# --- Data -------------------------------------------------------------------
if not SAMPLE_PATH.exists():
    st.error(f"Échantillon introuvable : {SAMPLE_PATH}. Lancez d'abord "
             "`python -m experiments.annotation_cascade.sample_extractor`.")
    st.stop()

sample = pd.read_csv(SAMPLE_PATH)
sample["_key"] = sample.apply(lambda r: f"{r['system_id']}|{r['station_id']}", axis=1)
if "is_trap" not in sample.columns:
    sample["is_trap"] = 0


@st.cache_data
def _load_catalogue():
    return pd.read_parquet(CATALOGUE_PATH) if CATALOGUE_PATH.exists() else None


full_cat = _load_catalogue()

try:
    store = get_store()
except Exception as exc:  # noqa: BLE001
    st.error(f"Connexion base impossible : {exc}")
    st.stop()

done_keys = store.get_done_keys(annotator_id, revisit_round)
remaining = sample[~sample["_key"].isin(done_keys)]
n_total, n_done = len(sample), len(done_keys)

with st.sidebar:
    st.progress(n_done / n_total if n_total else 0.0)
    st.markdown(f"**{n_done}** / **{n_total}** stations")
    med = store.median_duration(annotator_id)
    if med and len(remaining):
        st.caption(f"~{med:.0f}s/station — reste ~{med*len(remaining)/60:.0f} min")
    if st.button("Exporter mes labels (CSV)", use_container_width=True):
        p = LABELS_DIR / f"labels_{annotator_id}.csv"
        store.export_csv(annotator_id, p)
        st.success(f"Exporté : {p.name}")

if len(remaining) == 0:
    st.title("Annotation terminée")
    st.success(f"Les {n_total} stations sont annotées (tour {revisit_round}).")
    st.stop()

# --- Current station --------------------------------------------------------
row = remaining.iloc[0]
station_key = row["_key"]
lat = float(row["lat"]) if pd.notna(row.get("lat")) else None
lon = float(row["lon"]) if pd.notna(row.get("lon")) else None
st.session_state.start_times.setdefault(station_key, time.time())


# --- Imagery builders -------------------------------------------------------
def _map_html(lat, lon, sid, net):
    net_json = json.dumps(net, ensure_ascii=False)
    return f"""
    <div id="m" style="width:100%;height:560px;border-radius:6px;
         border:1px solid #d0d5dd;"></div>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>(function(){{
      var lat={lat}, lon={lon};
      var sat=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',{{maxZoom:19,attribution:'Esri'}});
      var cyclosm=L.tileLayer('https://{{s}}.tile-cyclosm.openstreetmap.fr/cyclosm/{{z}}/{{x}}/{{y}}.png',{{maxZoom:20,subdomains:'abc',attribution:'CyclOSM | OSM'}});
      var osm=L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'OSM'}});
      var map=L.map('m',{{layers:[sat]}}).setView([lat,lon],17);
      L.circle([lat,lon],{{radius:1000,color:'#1A6FBF',weight:1.5,fillColor:'#1A6FBF',fillOpacity:0.05,dashArray:'6,4'}}).addTo(map);
      L.circleMarker([lat,lon],{{radius:13,color:'#c0392b',weight:3,fillColor:'#e74c3c',fillOpacity:0.85}}).addTo(map).bindPopup('Station évaluée').openPopup();
      var net=L.layerGroup(); {net_json}.forEach(function(p){{
        L.circleMarker([p.lat,p.lon],{{radius:4,color:'#1A6FBF',weight:1,fillColor:'#5dade2',fillOpacity:0.5}}).addTo(net);
      }}); net.addTo(map);
      var osmg=L.layerGroup();
      var q='[out:json][timeout:10];(node["amenity"="bicycle_rental"](around:400,'+lat+','+lon+'););out body;';
      fetch('https://overpass-api.de/api/interpreter?data='+encodeURIComponent(q))
        .then(function(r){{return r.json();}}).then(function(d){{
          d.elements.forEach(function(e){{L.circleMarker([e.lat,e.lon],{{radius:6,color:'#e67e22',weight:2,fillColor:'#e67e22',fillOpacity:0.6}}).addTo(osmg).bindPopup((e.tags.name||'Location vélos (OSM)'));}});
          osmg.addTo(map);
        }}).catch(function(){{}});
      L.control.layers({{'Satellite':sat,'CyclOSM':cyclosm,'OSM':osm}},
        {{'Réseau opérateur':net,'Location vélos OSM':osmg}},{{collapsed:false}}).addTo(map);
      L.control.scale({{metric:true,imperial:false}}).addTo(map);
    }})();</script>"""


def _streetview_html(lat, lon):
    # Keyless interactive Street View (unofficial output=svembed trick).
    url = (f"https://www.google.com/maps?q=&layer=c&cbll={lat},{lon}"
           f"&cbp=11,0,0,0,0&output=svembed")
    return (f'<iframe src="{url}" style="width:100%;height:560px;border:0;'
            f'border-radius:6px;" allowfullscreen loading="lazy"></iframe>')


# --- Imagery panel (rendered once at top; tabs switch client-side) ----------
net_points = []
if full_cat is not None and lat is not None:
    same = full_cat[full_cat["system_id"] == row["system_id"]].copy()
    same = same[same["station_id"].astype(str) != str(row["station_id"])]
    if len(same) > 300:
        same["_d"] = (same["lat"] - lat) ** 2 + (same["lon"] - lon) ** 2
        same = same.nsmallest(300, "_d")
    net_points = same[["lat", "lon"]].dropna().to_dict("records")

col_img, col_q = st.columns([1.45, 1])

with col_img:
    if lat is not None and lon is not None:
        tab_map, tab_sv = st.tabs(["Carte + réseau", "Street View"])
        with tab_map:
            st.iframe(_map_html(lat, lon, str(row["station_id"]), net_points), height=580)
        with tab_sv:
            st.iframe(_streetview_html(lat, lon), height=580)
            st.caption("Street View sans clé (peut être absent hors zone couverte → Indéterminé).")
    else:
        st.warning("Coordonnées indisponibles.")

    with st.expander("Verdict du pipeline (à n'ouvrir qu'après avoir répondu)"):
        flags = [f"A{i}" for i in range(1, 8) if bool(row.get(f"flag_A{i}", False))]
        st.write("Flags actifs :", ", ".join(flags) if flags else "aucun")


# --- Persistence ------------------------------------------------------------
def _persist(ans: dict, note: str, skipped=False):
    elapsed = time.time() - st.session_state.start_times.get(station_key, time.time())
    rec = {
        "session_id": st.session_state.session_id,
        "annotator": annotator_id,
        "system_id": str(row["system_id"]),
        "station_id": str(row["station_id"]),
        "stratum": row.get("stratum"),
        "lat": lat, "lon": lon,
        "q0_libre_service": ans.get("q0_libre_service"),
        "q1_docks_presents": ans.get("q1_docks_presents"),
        "q2_nb_docks_classe": ans.get("q2_nb_docks_classe"),
        "q3a_perimetre": ans.get("q3a_perimetre"),
        "q3b_proximite": ans.get("q3b_proximite"),
        "verdict": "skipped" if skipped else derive_verdict(ans),
        "evidence": json.dumps(ans.get("_evidence", {}), ensure_ascii=False),
        "notes": note.strip(),
        "is_trap": int(row.get("is_trap", 0) or 0),
        "revisit_round": int(revisit_round),
        "duration_s": round(elapsed, 1),
        "created_at": datetime.now(timezone.utc).isoformat(),
        **{f"flag_A{i}": int(bool(row.get(f"flag_A{i}", False)))
           for i in range(1, 8) if f"flag_A{i}" in row.index},
    }
    store.save(rec)
    st.session_state.start_times.pop(station_key, None)
    for k in (f"ans_{station_key}", f"note_{station_key}"):
        st.session_state.pop(k, None)


# --- Question flow (fragment: answering does not reload the imagery) --------
@st.fragment
def _flow():
    ans = st.session_state.setdefault(f"ans_{station_key}", {})
    seq = active_sequence(ans)
    # First unanswered active question:
    current = next((q for q in seq if QUESTIONS[q]["col"] not in ans), None)

    st.markdown(
        f"<div class='meta-line'><b>{row.get('city','?')}</b> · "
        f"{row.get('operator_name','?')} · "
        f"<span style='color:#7a8aa8'>{row['system_id']}/{row['station_id']}</span>"
        f"</div>", unsafe_allow_html=True)

    if current is None:
        # All applicable questions answered -> review + save.
        st.markdown("<div class='qcard'>", unsafe_allow_html=True)
        st.markdown(f"**Verdict dérivé :** `{derive_verdict(ans)}`")
        summary = " · ".join(f"{QUESTIONS[q]['col'].split('_')[0].upper()}={ans[QUESTIONS[q]['col']]}"
                             for q in seq)
        st.caption(summary)
        note = st.text_input("Remarque (facultatif)", key=f"note_{station_key}")
        c1, c2 = st.columns([3, 1])
        if c1.button("Enregistrer et station suivante", type="primary",
                     use_container_width=True):
            _persist(ans, note)
            st.rerun(scope="app")
        if c2.button("Recommencer", use_container_width=True):
            st.session_state.pop(f"ans_{station_key}", None)
            st.rerun(scope="fragment")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    q = QUESTIONS[current]
    answered = [x for x in seq if QUESTIONS[x]["col"] in ans]
    st.markdown(
        f"<div class='qcard'>"
        f"<div class='qnum'>QUESTION {len(answered)+1} / {len(seq)}</div>"
        f"<div class='qtext'>{q['text']}</div>"
        f"<div class='qsub'>{q['sub']}</div>"
        f"<div class='qhint'>{q['hint']}</div>",
        unsafe_allow_html=True)

    if q["type"] == "binary":
        cols = st.columns(3)
        for (val, label), c in zip(BIN, cols):
            if c.button(label, key=f"{current}_{val}_{station_key}",
                        use_container_width=True):
                ans[q["col"]] = val
                st.rerun(scope="fragment")
    else:  # ordinal
        cols = st.columns(len(DOCK_CLASSES))
        for label, c in zip(DOCK_CLASSES, cols):
            if c.button(label, key=f"{current}_{label}_{station_key}",
                        use_container_width=True):
                ans[q["col"]] = "indéterminé" if label == "Indéterminé" else label
                st.rerun(scope="fragment")

    st.markdown("</div>", unsafe_allow_html=True)

    nav1, nav2 = st.columns([1, 1])
    if answered and nav1.button("‹ Question précédente", use_container_width=True):
        ans.pop(QUESTIONS[answered[-1]]["col"], None)
        st.rerun(scope="fragment")
    if nav2.button("Passer la station ›", use_container_width=True):
        _persist(ans, "", skipped=True)
        st.rerun(scope="app")


with col_q:
    _flow()
