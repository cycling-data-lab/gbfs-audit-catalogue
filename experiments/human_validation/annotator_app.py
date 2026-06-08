# -*- coding: utf-8 -*-
"""GBFS Audit - Human-validation annotation interface (v2).

Single page, no sidebar, one question at a time. Imagery stays on top
(full width, sticky) with client-side tabs (Street View / Carte and
satellite); switching tabs is pure JS so it never triggers a Streamlit
rerun. The question flow runs inside an @st.fragment, so answering a
question re-renders only the question block, never the imagery.

Instrument (infrastructure-based first node):

    Q0  Que voyez-vous sur cet emplacement ?  (1 reponse)
        1) Docks pour velos (bornes physiques)     -> Q2 -> Q3a/Q3b
        2) Zone de stationnement au sol (sans borne) -> Q3a/Q3b   [= A3]
        3) Trottinettes (uniquement)               -> Q3a/Q3b   [hors-domaine]
        4) Emplacement d'autopartage (voitures)    -> Q3a/Q3b   [= A1]
        5) Aucune trace de service                 -> STOP  [zombie]
        6) Indetermine                             -> STOP
    Q2  Nombre de docks (saisie numerique)         (si 1)
    Q3a Perimetre geographique valide ?            (si quelque chose est trouve)
    Q3b Au contact de son reseau ?                 (si quelque chose est trouve)

Usage:
    streamlit run experiments/human_validation/annotator_app.py
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import streamlit.components.v1 as components

from storage import get_store

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_PATH = Path(__file__).resolve().parent / "sample.csv"
LABELS_DIR = Path(__file__).resolve().parent
CATALOGUE_PATH = REPO_ROOT / "catalogue" / "stations_gold_standard_final.parquet"

ANNOTATORS = {"Rohan": "rohan", "Gaël": "gael"}

BIN = [("oui", "OUI"), ("non", "NON"), ("indéterminé", "INDÉTERMINÉ")]

# Q0 type options: (canonical value stored, display label). Infrastructure-based.
TYPE_OPTIONS = [
    ("vls_borne",      "Des bornes d'attache pour vélos (station physique)"),
    ("vls_sans_borne", "Une zone de dépose au sol, sans borne (free-floating)"),
    ("trottinettes",   "Des trottinettes en libre-service uniquement"),
    ("autopartage",    "Une station d'autopartage (voitures)"),
    ("rien",           "Aucune infrastructure visible à cet endroit"),
    ("indéterminé",    "Indéterminé (image floue, masquée ou trop ancienne)"),
]
# types for which something physical is found -> placement questions apply
FOUND_TYPES = {"vls_borne", "vls_sans_borne", "trottinettes", "autopartage"}

QUESTIONS = {
    "q0": {
        "col": "q0_type", "type": "choice",
        "text": "Qu'observez-vous physiquement à cet emplacement ?",
        "sub": "Jugez l'infrastructure au sol (bornes, marquage), pas les "
               "véhicules présents sur la photo.",
        "hint": "Repère : bornes ou racks fixes = station ; vélos posés sans "
                "matériel = free-floating ; voitures = autopartage.",
        "aide": (
            "Jugez l'**infrastructure physique présente**, pas la présence "
            "éphémère de véhicules (un emplacement peut être vide le jour de la "
            "capture) :\n\n"
            "- **Docks pour vélos** : bornes, racks ou points d'ancrage fixes "
            "visibles, même sans vélo.\n"
            "- **Zone de stationnement au sol (sans borne)** : marquage / arceaux "
            "génériques pour une flotte free-floating, aucun matériel d'ancrage dédié.\n"
            "- **Trottinettes (uniquement)** : opérateur de trottinettes ; hors "
            "périmètre de l'étude (vélos seulement).\n"
            "- **Autopartage de voitures** : emplacement de voitures partagées "
            "(ex. Citiz) listé par erreur comme vélo-partage.\n"
            "- **Aucune trace de service** : rien de visible à cet endroit précis "
            "(infrastructure démontée, emplacement vide).\n"
            "- **Indéterminé** : image floue, en intérieur, vue bloquée, trop "
            "ancienne.\n\n"
            "En cas de doute entre deux entrées, choisissez **Indéterminé**."),
    },
    "q2": {
        "col": "q2_nb_docks_classe", "type": "numeric",
        "text": "Combien de docks (points d'attache) comptez-vous ?",
        "sub": "Comptez tous les emplacements, même vides. Ne devinez pas la "
               "valeur du flux.",
        "hint": "Au besoin, passez sur l'onglet « Carte et satellite » (vue du dessus).",
        "aide": (
            "Comptez le nombre de **points d'ancrage** (emplacements de "
            "verrouillage), et non le nombre de vélos : une station peut être vide "
            "mais comporter de nombreux docks.\n\n"
            "Passez par l'onglet **Carte et satellite** (vue du dessus) pour les "
            "grandes stations : Street View sous-estime au-delà de ~10 docks "
            "(camionnettes, angles morts, distorsion). Si le comptage est "
            "réellement impossible, cochez la case dédiée."),
    },
    "q3a": {
        "col": "q3a_perimetre", "type": "binary",
        "text": "L'emplacement est-il géographiquement plausible ?",
        "sub": "Sur la terre ferme, dans le bon pays et la bonne agglomération.",
        "hint": "En mer, en plein champ ou dans le mauvais pays : répondre NON.",
        "aide": (
            "Le point GPS tombe-t-il à un endroit plausible : sur la terre ferme, "
            "dans le bon pays et l'agglomération desservie, hors zone manifestement "
            "interdite (autoroute, voie ferrée) ?\n\n"
            "Répondez **NON** si le point est en mer, en plein champ loin de toute "
            "ville, ou dans une autre région/pays que le réseau. En limite "
            "côtière/administrative ambiguë, répondez **Indéterminé**."),
    },
    "q3b": {
        "col": "q3b_proximite", "type": "binary",
        "text": "L'emplacement est-il rattaché à son réseau ?",
        "sub": "À moins de 1 km d'une station sœur, ou dans l'enveloppe du réseau.",
        "hint": "Onglet « Carte » : stations sœurs en bleu, cercle de 1 km affiché.",
        "aide": (
            "Avec les stations sœurs (en bleu) et le cercle de 1 km de l'onglet "
            "**Carte** : la station est-elle rattachée à son réseau ?\n\n"
            "Répondez **OUI** si elle est à moins de 1 km d'au moins une station "
            "sœur, ou dans l'enveloppe (contour) du réseau. **NON** si isolée à "
            "plus de 1 km ET hors enveloppe. Si les sœurs ne se chargent pas, "
            "**Indéterminé**. Le ressenti ne suffit pas : critère 1 km / enveloppe."),
    },
}


def active_sequence(ans: dict) -> list[str]:
    seq = ["q0"]
    t = ans.get("q0_type")
    if t == "vls_borne":
        seq += ["q2", "q3a", "q3b"]
    elif t in FOUND_TYPES:
        seq += ["q3a", "q3b"]
    return seq


def derive_verdict(ans: dict) -> str:
    t = ans.get("q0_type")
    if t == "rien":
        return "ZOMBIE"
    if t in (None, "indéterminé"):
        return "INDET"
    type_part = {"vls_borne": "DOCK", "vls_sans_borne": "FLOAT",
                 "trottinettes": "TROT", "autopartage": "A1"}[t]
    peri, prox = ans.get("q3a_perimetre"), ans.get("q3b_proximite")
    if peri == "non":
        place = "A5"
    elif prox == "non":
        place = "A4"
    elif peri == "oui" and prox == "oui":
        place = "PLACED"
    else:
        place = "PLACE_INDET"
    return f"{type_part}|{place}"


# --- Street View capture date (free metadata API; needs a key) --------------
def _gmaps_key():
    k = os.environ.get("GOOGLE_MAPS_API_KEY")
    if k:
        return k.strip()
    try:
        if "GOOGLE_MAPS_API_KEY" in st.secrets:
            return str(st.secrets["GOOGLE_MAPS_API_KEY"]).strip()
    except Exception:  # noqa: BLE001
        pass
    return None


@st.cache_data(show_spinner=False)
def _sv_meta(lat, lon):
    key = _gmaps_key()
    if not key:
        return {"status": "NO_KEY", "date": None, "pano_id": None}
    try:
        url = ("https://maps.googleapis.com/maps/api/streetview/metadata?"
               + urllib.parse.urlencode({"location": f"{lat},{lon}", "key": key}))
        with urllib.request.urlopen(url, timeout=6) as r:
            d = json.load(r)
        return {"status": d.get("status"), "date": d.get("date"),
                "pano_id": d.get("pano_id")}
    except Exception:  # noqa: BLE001
        return {"status": "ERROR", "date": None, "pano_id": None}


def _bind_shortcuts(mapping, nonce):
    """Map keyboard keys to button clicks for the CURRENT screen only.

    Re-binds on every render: the nonce in the markup forces the component to
    re-mount, the previous listener is removed, and only the current question's
    keys are active. This avoids the stale-binding shadowing (e.g. a leftover
    '1'->type-1 mapping intercepting '1'->OUI) and lets digits type normally in
    the count field (inputs pass through, except Enter)."""
    js = (
        "<script>/*" + str(nonce) + "*/(function(){"
        "var doc=window.parent.document, w=window.parent.window;"
        "var M=" + json.dumps(mapping) + ";"
        "if(w.__kb){doc.removeEventListener('keydown',w.__kb);}"
        "w.__kb=function(e){"
        "var tag=(e.target.tagName||'').toUpperCase();"
        "if((tag==='INPUT'||tag==='TEXTAREA')&&e.key!=='Enter')return;"
        "var k=e.key.toLowerCase();"
        "for(var key in M){if(k===String(M[key]).toLowerCase()){"
        "var el=doc.querySelector('.st-key-'+key+' button');"
        "if(el){e.preventDefault();el.click();}return;}}"
        "};"
        "doc.addEventListener('keydown',w.__kb);"
        "})();</script>"
    )
    components.html(js, height=0, width=0)


# ============================================================================
st.set_page_config(page_title="Validation humaine de l'audit GBFS",
                   layout="centered")

st.markdown("""
<style>
:root {
  --ink:#0f2942; --ink2:#3d5874; --muted:#6b7f95; --line:#e3e9f1;
  --surface:#f7fafc; --accent:#1f6feb; --accent-d:#16529e;
}
header[data-testid="stHeader"] { background:transparent; }
#MainMenu, footer { visibility:hidden; }
section[data-testid="stSidebar"] { display:none; }
.block-container { padding-top: 1.6rem !important; max-width: 1120px; }
/* imagery stays visible while answering below */
div[data-testid="stIFrame"]:first-of-type { position: sticky; top: 0.4rem;
  z-index: 20; background:#fff; }
.topcount { font-size:0.74rem; font-weight:700; color:var(--muted);
  text-align:right; margin:0 0 2px; }
.appbar { display:flex; align-items:center; justify-content:space-between;
  gap:1rem; border-bottom:2px solid var(--line); padding-bottom:0.6rem;
  margin-bottom:0.5rem; }
.appbar .title { font-size:1.2rem; font-weight:800; color:var(--ink);
  letter-spacing:-0.01em; line-height:1.15; }
.appbar .title small { display:block; font-size:0.76rem; font-weight:600;
  color:var(--muted); margin-top:3px; }
.badge { white-space:nowrap; font-size:0.68rem; font-weight:800;
  text-transform:uppercase; letter-spacing:0.06em; color:var(--accent-d);
  background:#e9f1fe; border:1px solid #cfe0fb; border-radius:999px;
  padding:0.28rem 0.75rem; }
.pbar { height:6px; background:var(--line); border-radius:3px; overflow:hidden;
  margin:0.5rem 0 0.2rem; }
.pbar > span { display:block; height:100%; background:var(--accent); }
.pbar-cap { font-size:0.78rem; color:var(--muted); margin:0.15rem 0 0.5rem; }
.station-chip { display:flex; gap:0.55rem; align-items:baseline; flex-wrap:wrap;
  background:#fff; border:1px solid var(--line); border-radius:10px;
  padding:0.55rem 0.9rem; margin:0.5rem 0 0.2rem; }
.station-chip .city { font-weight:800; color:var(--ink); font-size:1.02rem; }
.station-chip .op { color:var(--ink2); font-weight:600; }
.station-chip .id { color:var(--muted); font-size:0.8rem; margin-left:auto;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
.svdate { font-size:0.78rem; color:var(--ink2); }
.svdate b { color:var(--ink); }
.stepper { display:flex; gap:5px; margin:0.3rem 0 0.3rem; }
.step { flex:1; height:5px; border-radius:3px; background:var(--line); }
.step.done { background:var(--accent); }
.step.now  { background:var(--accent-d); box-shadow:0 0 0 2px #cfe0fb; }
.qcard { background:var(--surface); border:1px solid var(--line);
  border-radius:12px; padding:0.7rem 0.9rem 0.5rem; margin-top:0.2rem; }
.qnum { font-size:0.7rem; color:var(--accent-d); font-weight:800;
  letter-spacing:0.08em; text-transform:uppercase; }
.qtext { font-size:1.28rem; font-weight:800; color:var(--ink); line-height:1.2;
  margin:0.15rem 0 0.15rem; }
.qsub { font-size:0.9rem; color:var(--ink2); margin-bottom:0.2rem; }
.qkbd { font-size:0.74rem; color:var(--muted); margin-top:0.2rem; }
.qhint { font-size:0.82rem; color:var(--ink2); margin:0.1rem 0 0.35rem; }
/* Uniform, neutral answer buttons (no colour coding: this is a measurement
   instrument; colour would add cognitive load and break neutrality). */
.stButton button { font-size:1.0rem !important; font-weight:700 !important;
  padding:0.42rem 0.7rem !important; border-radius:9px !important;
  border:1px solid #c9d6e5 !important; transition:all .1s ease;
  text-align:left !important; }
.stButton button:hover { border-color:var(--accent) !important;
  color:var(--accent-d) !important; background:#f2f7fe !important; }
/* Dense right column: shrink vertical gaps so the 6 options are taken in at
   a single glance, with minimal eye travel from the image. */
div[data-testid="stVerticalBlock"] { gap:0.3rem !important; }
details[data-testid="stExpander"] summary { font-size:0.8rem; padding:0.2rem 0.5rem; }
</style>
""", unsafe_allow_html=True)

# --- Session state ----------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:12]
if "start_times" not in st.session_state:
    st.session_state.start_times = {}

# --- Very light counter at the very top (filled after data load) ------------
top_count = st.empty()

# --- Session chooser: prominent until chosen, then collapsed to one line -----
_sel = st.session_state.get("annot_sel", "Sélectionnez votre nom")
if _sel not in ANNOTATORS:
    # First launch only: show the chooser, then stop. Once a session is active
    # the selectors live in the bottom footer (they no longer occupy the top).
    cc1, cc2 = st.columns(2)
    cc1.selectbox("Annotateur", ["Sélectionnez votre nom", *ANNOTATORS], key="annot_sel")
    cc2.selectbox("Tour", [0, 1], key="round_sel",
                  format_func=lambda r: "Tour principal" if r == 0 else "Re-test (fiabilité intra)")
    st.info("Choisissez votre nom pour commencer (annotation en aveugle).")
    st.stop()
annotator_id = ANNOTATORS[_sel]
revisit_round = int(st.session_state.get("round_sel", 0))

# --- Data -------------------------------------------------------------------
if not SAMPLE_PATH.exists():
    st.error(f"Échantillon introuvable : {SAMPLE_PATH}.")
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
remaining = sample[~sample["_key"].isin(done_keys)].copy()

# Re-randomise the presentation order per round (round 1 differs from round 0)
# so the re-test does not replay round-0 order from memory. Deterministic.
def _order_key(key):
    return hashlib.md5(f"{key}|{revisit_round}".encode()).hexdigest()


remaining["_ord"] = remaining["_key"].map(_order_key)
remaining = remaining.sort_values("_ord")
n_total, n_done = len(sample), len(done_keys)

# --- Fill the top counter placeholder (rendered visually at the very top) ---
_pct = (n_done / n_total * 100) if n_total else 0
_rlbl = "Tour principal" if revisit_round == 0 else "Re-test"
top_count.markdown(
    f"<div class='topcount'>{_sel} . {_rlbl} . {n_done} / {n_total}</div>"
    f"<div class='pbar'><span style='width:{_pct:.1f}%'></span></div>",
    unsafe_allow_html=True)


def _footer():
    """Low-frequency actions rendered at the very bottom: change session,
    export, undo. Kept off the top so they never push the questions down."""
    st.divider()
    with st.expander("Changer d'annotateur / de tour"):
        st.selectbox("Annotateur", ["Sélectionnez votre nom", *ANNOTATORS],
                     key="annot_sel")
        st.selectbox("Tour", [0, 1], key="round_sel",
                     format_func=lambda r: "Tour principal" if r == 0 else "Re-test (fiabilité intra)")
    if n_done > 0 and st.button("Annuler la dernière station enregistrée",
                                use_container_width=True):
        store.delete_last(annotator_id, revisit_round)
        st.rerun()


if len(remaining) == 0:
    st.success(f"Les {n_total} stations sont annotées (tour {revisit_round}). "
               "Validation terminée, merci !")
    _footer()
    st.stop()

# --- Current station --------------------------------------------------------
row = remaining.iloc[0]
station_key = row["_key"]
lat = float(row["lat"]) if pd.notna(row.get("lat")) else None
lon = float(row["lon"]) if pd.notna(row.get("lon")) else None
st.session_state.start_times.setdefault(station_key, time.time())

sv = _sv_meta(lat, lon) if lat is not None else {"status": "NO_COORDS", "date": None, "pano_id": None}


# --- Imagery: ONE component with client-side tabs (no Streamlit rerun) ------
def _imagery_html(lat, lon, net):
    net_json = json.dumps(net, ensure_ascii=False)
    sv_url = (f"https://www.google.com/maps?q=&layer=c&cbll={lat},{lon}"
              f"&cbp=11,0,0,0,0&output=svembed")
    return f"""
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
      .tabs{{display:flex;gap:6px;margin-bottom:6px;font-family:system-ui,sans-serif}}
      .tab{{flex:1;padding:8px;border:1px solid #c9d6e5;border-radius:8px;
            background:#fff;font-weight:700;font-size:13px;color:#3d5874;
            cursor:pointer;text-align:center}}
      .tab.active{{background:#1f6feb;color:#fff;border-color:#1f6feb}}
      .pane{{display:none}} .pane.active{{display:block}}
    </style>
    <div class="tabs">
      <div class="tab active" id="tb_sv" onclick="show('sv')">Street View (vue au sol)</div>
      <div class="tab" id="tb_map" onclick="show('map')">Carte et satellite (vue du dessus)</div>
    </div>
    <div id="p_sv" class="pane active">
      <iframe src="{sv_url}" loading="lazy" allowfullscreen
        style="width:100%;height:470px;border:1px solid #d0d5dd;border-radius:8px"></iframe>
    </div>
    <div id="p_map" class="pane">
      <div id="m" style="width:100%;height:470px;border:1px solid #d0d5dd;border-radius:8px"></div>
    </div>
    <script>(function(){{
      var map=null;
      window.show=function(k){{
        document.getElementById('tb_sv').classList.toggle('active',k==='sv');
        document.getElementById('tb_map').classList.toggle('active',k==='map');
        document.getElementById('p_sv').classList.toggle('active',k==='sv');
        document.getElementById('p_map').classList.toggle('active',k==='map');
        if(k==='map'){{ if(!map){{build();}} setTimeout(function(){{map.invalidateSize();}},60); }}
      }};
      function build(){{
        var lat={lat}, lon={lon};
        var sat=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',{{maxZoom:19,attribution:'Esri'}});
        var cyclosm=L.tileLayer('https://{{s}}.tile-cyclosm.openstreetmap.fr/cyclosm/{{z}}/{{x}}/{{y}}.png',{{maxZoom:20,subdomains:'abc',attribution:'CyclOSM'}});
        var osm=L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'OSM'}});
        map=L.map('m',{{layers:[sat]}}).setView([lat,lon],18);
        L.circle([lat,lon],{{radius:1000,color:'#1A6FBF',weight:1.5,fillColor:'#1A6FBF',fillOpacity:0.05,dashArray:'6,4'}}).addTo(map);
        L.circleMarker([lat,lon],{{radius:11,color:'#c0392b',weight:3,fillColor:'#e74c3c',fillOpacity:0.85}}).addTo(map);
        var net=L.layerGroup(); {net_json}.forEach(function(p){{
          L.circleMarker([p.lat,p.lon],{{radius:4,color:'#1A6FBF',weight:1,fillColor:'#5dade2',fillOpacity:0.6}}).addTo(net);
        }}); net.addTo(map);
        L.control.layers({{'Satellite':sat,'CyclOSM':cyclosm,'OSM':osm}},{{'Réseau opérateur':net}},{{collapsed:false}}).addTo(map);
        L.control.scale({{metric:true,imperial:false}}).addTo(map);
      }}
    }})();</script>"""


net_points = []
if full_cat is not None and lat is not None:
    same = full_cat[full_cat["system_id"] == row["system_id"]].copy()
    same = same[same["station_id"].astype(str) != str(row["station_id"])]
    if len(same) > 300:
        same["_d"] = (same["lat"] - lat) ** 2 + (same["lon"] - lon) ** 2
        same = same.nsmallest(300, "_d")
    net_points = same[["lat", "lon"]].dropna().to_dict("records")

# Station identity, full width just under the session line (lifts the questions).
st.markdown(
    "<div class='station-chip'>"
    f"<span class='city'>{row.get('city','?')}</span>"
    f"<span class='op'>{row.get('operator_name','?')}</span>"
    f"<span class='id'>{row['system_id']}/{row['station_id']}</span>"
    "</div>", unsafe_allow_html=True)

# Split-screen: imagery fixed on the left (sticky), questions on the right.
col_img, col_q = st.columns([1.35, 1], gap="medium")
with col_img:
    if lat is not None and lon is not None:
        st.iframe(_imagery_html(lat, lon, net_points), height=560)
        sv_fallback = (f"https://www.google.com/maps/@?api=1&map_action=pano"
                       f"&viewpoint={lat},{lon}")
        _pe = (f"<a href='{sv_fallback}' target='_blank' "
               "style='color:#1f6feb;text-decoration:none;font-weight:700'>plein écran</a>")
        if sv["status"] == "OK":
            _d = sv.get("date") or "date inconnue"
            st.markdown(f"<div class='svdate'>Capture : <b>{_d}</b> "
                        f"(si &gt; 2 ans ou changement radical, privilégier "
                        f"Indéterminé) &nbsp;.&nbsp; {_pe}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='svdate'>{_pe}</div>", unsafe_allow_html=True)
    else:
        st.warning("Coordonnées indisponibles.")


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
        "q0_type": ans.get("q0_type"),
        "q2_nb_docks_classe": ans.get("q2_nb_docks_classe"),
        "q3a_perimetre": ans.get("q3a_perimetre"),
        "q3b_proximite": ans.get("q3b_proximite"),
        "sv_date": sv.get("date"),
        "sv_pano_id": sv.get("pano_id"),
        "sv_status": sv.get("status"),
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
    current = next((q for q in seq if QUESTIONS[q]["col"] not in ans), None)

    kbmap = {}  # keyboard shortcuts active on the current screen only

    if current is None:  # review + save
        st.markdown("<div class='qcard'>", unsafe_allow_html=True)
        st.markdown(f"**Verdict dérivé :** `{derive_verdict(ans)}`")
        summary = " . ".join(f"{QUESTIONS[q]['col']}={ans[QUESTIONS[q]['col']]}" for q in seq)
        st.caption(summary)
        note = st.text_input("Remarque (facultatif)", key=f"note_{station_key}")
        c_save, c_reset = st.columns([3, 1])
        if c_save.button("Enregistrer et station suivante", type="primary",
                         use_container_width=True):
            _persist(ans, note)
            st.rerun(scope="app")
        if c_reset.button("Recommencer", use_container_width=True):
            st.session_state.pop(f"ans_{station_key}", None)
            st.rerun(scope="fragment")
        st.markdown("</div>", unsafe_allow_html=True)
        _bind_shortcuts({}, f"{station_key}|review")
        return

    q = QUESTIONS[current]
    answered = [x for x in seq if QUESTIONS[x]["col"] in ans]
    steps = "".join(
        "<div class='step {}'></div>".format(
            "done" if QUESTIONS[s]["col"] in ans else ("now" if s == current else ""))
        for s in seq)
    st.markdown(f"<div class='stepper'>{steps}</div>", unsafe_allow_html=True)

    _qt = q["text"].replace(" ?", "\u00a0?").replace(" :", "\u00a0:")
    st.markdown(
        f"<div class='qcard'>"
        f"<div class='qnum'>QUESTION {len(answered)+1} / {len(seq)}</div>"
        f"<div class='qtext'>{_qt}</div>"
        f"<div class='qsub'>{q['sub']}</div>"
        f"<div class='qhint'>{q['hint']}</div>",
        unsafe_allow_html=True)

    # Fixed ASCII widget keys (only one question is on screen at a time) so the
    # streamlit-shortcuts selector .st-key-<key> resolves; per-station keys with
    # "|"/accents produced invalid selectors and silently broke the shortcuts.
    if q["type"] == "choice":            # Q0 - one full-width button per type
        keymap = {}
        for i, (val, label) in enumerate(TYPE_OPTIONS, start=1):
            k = f"q0type{i}"
            keymap[k] = str(i)
            if st.button(f"[{i}]  {label}", key=k, use_container_width=True):
                ans[q["col"]] = val
                st.rerun(scope="fragment")
        kbmap.update(keymap)
    elif q["type"] == "numeric":         # Q2 - raw count (enables A2 +/-50%)
        nb = st.number_input("Nombre de docks comptés", min_value=0, max_value=2000,
                             step=1, key=f"num_{station_key}")
        imposs = st.checkbox("Comptage impossible (Indéterminé)",
                             key=f"imp_{station_key}")
        if st.button("Valider le comptage  (Entrée)", key="q2valider", type="primary",
                     use_container_width=True):
            ans[q["col"]] = "indéterminé" if imposs else str(int(nb))
            st.rerun(scope="fragment")
        kbmap["q2valider"] = "enter"
    else:                                 # binary - OUI / NON, Indéterminé détaché
        oui, non = st.columns(2)
        if oui.button("[1]  OUI", key="ansoui", use_container_width=True):
            ans[q["col"]] = "oui"; st.rerun(scope="fragment")
        if non.button("[2]  NON", key="ansnon", use_container_width=True):
            ans[q["col"]] = "non"; st.rerun(scope="fragment")
        st.caption("ou, si vous ne pouvez pas trancher :")
        if st.button("[3]  INDÉTERMINÉ", key="ansind", use_container_width=True):
            ans[q["col"]] = "indéterminé"; st.rerun(scope="fragment")
        kbmap.update({"ansoui": "1", "ansnon": "2", "ansind": "3"})

    st.markdown("</div>", unsafe_allow_html=True)

    nav1, nav2 = st.columns([1, 1])
    if answered and nav1.button("‹ Question précédente", key="navprev",
                                use_container_width=True):
        ans.pop(QUESTIONS[answered[-1]]["col"], None)
        st.rerun(scope="fragment")
    if nav2.button("Passer la station ›", use_container_width=True):
        _persist(ans, "", skipped=True)
        st.rerun(scope="app")
    if answered:
        kbmap["navprev"] = "arrowleft"

    _bind_shortcuts(kbmap, f"{station_key}|{current}|{len(answered)}")

    with st.expander("Explication détaillée de cette question (optionnel)"):
        st.markdown(q["aide"])


# Questions in the right column; keyboard shortcuts bound per question by
# streamlit-shortcuts (reliable, replaces the former parent-DOM hook).
with col_q:
    _flow()

# --- Low-frequency actions, at the very bottom (export + undo) ---------------
_footer()
