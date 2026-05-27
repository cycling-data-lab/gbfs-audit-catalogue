# -*- coding: utf-8 -*-
"""GBFS Audit Catalogue -- Outil d'annotation humaine.

Validation ground-truth sur un échantillon stratifié de 175 stations.
Deux annotateurs indépendants évaluent chaque station ; la fiabilité
inter-annotateurs est calculée ensuite via compute_reliability.py.

Usage :
    python -m streamlit run experiments/annotation/annotator_app.py
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_PATH = Path(__file__).resolve().parent / "sample_200.csv"
LABELS_DIR = Path(__file__).resolve().parent
CATALOGUE_PATH = REPO_ROOT / "catalogue" / "stations_gold_standard_final.parquet"

STRATUM_COLORS = {
    "clean_docked": "#27ae60",
    "A1_carsharing": "#8e44ad",
    "A2_placeholder": "#d35400",
    "A3_freefloating": "#2980b9",
    "A4_agree_flag": "#c0392b",
    "A4_discordant_legacy": "#e74c3c",
    "A4_discordant_composite": "#2471a3",
    "A6_zero_capacity": "#16a085",
    "A7_null_capacity": "#f39c12",
    "A3_boundary": "#7f8c8d",
}

STRATUM_GUIDELINES = {
    "clean_docked": (
        "Cette station n'a déclenché aucun flag et a été classée en haute "
        "confiance. Votre rôle est de vérifier qu'il ne s'agit pas d'un "
        "faux négatif : la station est-elle réellement un dock vélo "
        "fonctionnel aux coordonnées indiquées ?"
    ),
    "A1_carsharing": (
        "Le pipeline a détecté un système d'autopartage (voitures) "
        "publié sous le schéma GBFS vélo. Vérifiez sur la carte et "
        "via Street View : voyez-vous des bornes de vélos ou des places "
        "de stationnement automobile ?"
    ),
    "A2_placeholder": (
        "Toutes les stations de ce système déclarent exactement la "
        "même capacité (ex : 100 partout). Vérifiez : est-ce un vrai "
        "nombre de bornes physiques, ou un placeholder inséré par "
        "l'opérateur ?"
    ),
    "A3_freefloating": (
        "Cette station est identifiée comme un ancrage virtuel de "
        "flotte free-floating. Vérifiez sur la carte : y a-t-il des "
        "bornes physiques visibles, ou s'agit-il simplement d'un "
        "point GPS où un véhicule a été garé ?"
    ),
    "A4_agree_flag": (
        "Les DEUX détecteurs (centroïde legacy et composite topologique) "
        "considèrent cette station comme un outlier géospatial. "
        "Vérifiez : la station est-elle réellement isolée du reste "
        "du réseau, ou appartient-elle à une extension légitime "
        "(gare, campus, zone d'activité) ?"
    ),
    "A4_discordant_legacy": (
        "C'est la strate la plus importante de l'annotation. Le "
        "centroïde legacy flag cette station comme outlier, mais le "
        "détecteur composite (HDBSCAN + spectral) la considère comme "
        "normale. Votre verdict détermine directement si les 8 005 "
        "stations discordantes sont de vrais faux positifs du legacy."
    ),
    "A4_discordant_composite": (
        "Le détecteur composite flag cette station, mais le centroïde "
        "legacy ne la détecte pas. C'est une nouvelle détection. "
        "Vérifiez : la station est-elle réellement problématique ?"
    ),
    "A6_zero_capacity": (
        "La station déclare une capacité de zéro bornes. Vérifiez sur "
        "la carte : la station existe-t-elle physiquement ? A-t-elle "
        "été désinstallée ou est-elle en travaux ?"
    ),
    "A7_null_capacity": (
        "La station déclare capacity = NaN (champ vide). C'est le "
        "pattern typique de Dott et Bird. Vérifiez simplement que "
        "la station existe bien à ces coordonnées."
    ),
    "A3_boundary": (
        "Le ratio de capacité de ce système est entre 2 et 5 -- la zone "
        "grise du seuil A3. Vérifiez : s'agit-il d'un système de "
        "bornes physiques avec des capacités hétérogènes, ou d'un "
        "système free-floating avec un estimateur de profil ?"
    ),
}

FLAG_LABELS = {
    "A1": "Inclusion hors domaine (autopartage)",
    "A2": "Capacité placeholder (constante sur tout le système)",
    "A3": "Sur-capacité structurelle (ancrage free-floating)",
    "A4": "Outlier géospatial (détecteur topologique composite)",
    "A5": "Hors périmètre (surface > 50 000 km²)",
    "A6": "Dock à zéro capacité (avertissement sémantique)",
    "A7": "Champ capacité nul / NaN (avertissement sémantique)",
}


# =====================================================================
# Configuration de la page
# =====================================================================

st.set_page_config(
    page_title="Annotation GBFS -- Ground Truth",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 0.5rem; max-width: 1400px; }
    section[data-testid="stSidebar"] > div { padding-top: 0.8rem; }
    .stratum-badge {
        display: inline-block; padding: 0.12rem 0.5rem;
        border-radius: 3px; font-size: 0.73rem; font-weight: 700;
        color: white; letter-spacing: 0.02em;
    }
    .guideline-box {
        background: #f0f4f8; border-left: 3px solid #1A6FBF;
        padding: 0.5rem 0.85rem; border-radius: 0 4px 4px 0;
        font-size: 0.84rem; margin-bottom: 0.4rem; line-height: 1.45;
    }
    .legend-box {
        background: #fafbfc; border: 1px solid #e0e4e8;
        padding: 0.5rem 0.75rem; border-radius: 4px;
        font-size: 0.78rem; line-height: 1.55; margin-top: 0.3rem;
    }
    .legend-box b { font-size: 0.8rem; }
    .legend-item { margin-bottom: 0.15rem; }
    .links-bar {
        display: flex; gap: 0.5rem; flex-wrap: wrap;
        margin-top: 0.25rem; margin-bottom: 0.15rem;
    }
    .links-bar a {
        display: inline-block; padding: 0.22rem 0.55rem;
        border-radius: 4px; font-size: 0.76rem; font-weight: 600;
        text-decoration: none; border: 1px solid #ccc; color: #333;
    }
    .links-bar a:hover { background: #eee; }
    .links-bar a.primary {
        background: #1A6FBF; color: white; border-color: #1A6FBF;
    }
    .links-bar a.primary:hover { background: #155a8a; }
    .flag-row { font-size: 0.82rem; margin-bottom: 0.12rem; }
    .flag-on { color: #c0392b; font-weight: 700; }
    .flag-off { color: #bdc3c7; }
    .meta-label { font-size: 0.74rem; color: #777; margin-top: 0.2rem; }
    .meta-value { font-size: 0.86rem; font-weight: 600; color: #222; }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# Session state
# =====================================================================

if "start_times" not in st.session_state:
    st.session_state.start_times = {}


# =====================================================================
# Sidebar : identité, protocole, progression
# =====================================================================

with st.sidebar:
    st.markdown("## Session d'annotation")

    annotator_name = st.text_input(
        "Votre nom",
        value="",
        placeholder="ex : Rohan",
        key="annotator_name",
    )
    if not annotator_name.strip():
        st.warning("Entrez votre nom pour commencer.")
        st.stop()

    annotator_id = annotator_name.strip().lower().replace(" ", "_")
    labels_path = LABELS_DIR / f"labels_{annotator_id}.csv"

    st.markdown("---")
    st.markdown("### Protocole")
    st.markdown(
        "Pour chaque station, vous disposez de :\n\n"
        "- Une **carte CyclOSM** centrée sur la station "
        "(infrastructure cyclable en surbrillance)\n"
        "- Des **liens directs** vers Street View, OpenStreetMap "
        "et Google Maps\n"
        "- Les **métadonnées GBFS** et le **verdict du pipeline**\n"
        "- Une **consigne spécifique** à la strate de cette station\n\n"
        "Répondez aux 5 questions, puis cliquez sur Enregistrer."
    )
    st.markdown(
        "<div class='guideline-box'>"
        "<b>Principe fondamental :</b> vous êtes la vérité terrain. "
        "Si le pipeline signale une anomalie mais que vous constatez "
        "une station vélo légitime sur Street View ou sur la carte, "
        "répondez <b>faux positif du pipeline</b>. Inversement, si "
        "le pipeline ne signale rien mais que la station vous semble "
        "suspecte, notez-le dans les remarques."
        "</div>",
        unsafe_allow_html=True,
    )


# =====================================================================
# Chargement des données
# =====================================================================

if not SAMPLE_PATH.exists():
    st.error(f"Fichier échantillon introuvable : {SAMPLE_PATH}")
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

if CATALOGUE_PATH.exists():
    @st.cache_data
    def _load_catalogue():
        return pd.read_parquet(CATALOGUE_PATH)
    full_cat = _load_catalogue()
else:
    full_cat = None


# =====================================================================
# Sidebar : progression
# =====================================================================

with st.sidebar:
    st.markdown("---")
    st.markdown("### Progression")
    st.progress(n_done / n_total if n_total > 0 else 0.0)
    st.markdown(f"**{n_done}** / **{n_total}** stations annotées")

    if n_done > 0 and labels_path.exists():
        tmp = pd.read_csv(labels_path)
        non_skip = tmp[tmp["Q5_verdict"] != "skipped"]
        if "duration_s" in non_skip.columns and len(non_skip) > 0:
            med = non_skip["duration_s"].median()
            rest_min = med * len(remaining) / 60
            st.caption(
                f"Temps médian : {med:.0f}s par station -- "
                f"Temps restant estimé : ~{rest_min:.0f} min"
            )

    st.markdown("#### Par strate")
    by_str = sample.copy()
    by_str["done"] = by_str["_key"].isin(done_keys)
    prog = by_str.groupby("stratum").agg(
        fait=("done", "sum"), total=("_key", "count")
    ).reset_index()
    for _, r in prog.iterrows():
        color = STRATUM_COLORS.get(r["stratum"], "#999")
        pct = int(100 * r["fait"] / r["total"]) if r["total"] > 0 else 0
        bar = "|" * (pct // 10) + "." * (10 - pct // 10)
        st.markdown(
            f"<span class='stratum-badge' style='background:{color};'>"
            f"{r['stratum']}</span> "
            f"<code>{bar}</code> {r['fait']}/{r['total']}",
            unsafe_allow_html=True,
        )


# =====================================================================
# Écran de fin
# =====================================================================

if len(remaining) == 0:
    st.title("Annotation terminée")
    st.success(
        f"L'ensemble des {n_total} stations a été annoté par "
        f"{annotator_name}. Les labels sont sauvegardés dans "
        f"`{labels_path.name}`."
    )
    st.markdown(
        "**Étape suivante** : demandez au second annotateur de lancer "
        "sa propre session, puis calculez la fiabilité inter-annotateurs :\n\n"
        "```bash\n"
        "python -m experiments.annotation.compute_reliability \\\n"
        f"    --labels1 {labels_path.name} \\\n"
        "    --labels2 labels_<autre>.csv \\\n"
        "    --output reliability_report.json\n"
        "```"
    )
    st.stop()


# =====================================================================
# Station courante
# =====================================================================

row = remaining.iloc[0]
station_key = row["_key"]

if station_key not in st.session_state.start_times:
    st.session_state.start_times[station_key] = time.time()

lat = float(row["lat"]) if pd.notna(row.get("lat")) else None
lon = float(row["lon"]) if pd.notna(row.get("lon")) else None
stratum = row.get("stratum", "unknown")
stratum_color = STRATUM_COLORS.get(stratum, "#999")
guideline = STRATUM_GUIDELINES.get(stratum, "")


# =====================================================================
# En-tête
# =====================================================================

st.markdown(
    f"<div style='display:flex; align-items:center; gap:0.6rem; "
    f"margin-bottom:0.15rem;'>"
    f"<span style='font-size:1.15rem; font-weight:700;'>"
    f"Station {n_done + 1} sur {n_total}</span>"
    f"<span class='stratum-badge' style='background:{stratum_color};'>"
    f"{stratum}</span>"
    f"<span style='color:#888; font-size:0.8rem;'>"
    f"{row.get('system_id', '')} / {row.get('station_id', '')}</span>"
    f"</div>",
    unsafe_allow_html=True,
)

st.markdown(
    f"<div class='guideline-box'>{guideline}</div>",
    unsafe_allow_html=True,
)


# =====================================================================
# Deux colonnes : Carte | Métadonnées + Flags
# =====================================================================

col_left, col_right = st.columns([3, 2])

with col_left:
    if lat is not None and lon is not None:
        # Carte CyclOSM via iframe Leaflet inline
        # Les tuiles CyclOSM montrent l'infrastructure cyclable en détail :
        # pistes en bleu, bandes en pointillés, stationnements vélo, etc.
        leaflet_html = f"""
        <div id="map" style="width:100%;height:430px;border-radius:4px;border:1px solid #ddd;"></div>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
        var map = L.map('map').setView([{lat}, {lon}], 17);
        L.tileLayer('https://a.tile-cyclosm.openstreetmap.fr/cyclosm/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 20,
            attribution: '<a href="https://www.cyclosm.org">CyclOSM</a> | <a href="https://www.openstreetmap.org/copyright">OSM</a>'
        }}).addTo(map);
        L.circleMarker([{lat}, {lon}], {{
            radius: 10, color: '#c0392b', weight: 3,
            fillColor: '#e74c3c', fillOpacity: 0.7
        }}).addTo(map).bindPopup('<b>Station à évaluer</b><br>{row.get("station_id", "")}');
        </script>
        """
        st.components.v1.html(leaflet_html, height=445, scrolling=False)

        # Liens
        streetview_url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"
        cyclosm_url = f"https://www.cyclosm.org/#map=17/{lat}/{lon}/cyclosm"
        osm_url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}"
        osm_query_url = f"https://www.openstreetmap.org/query?lat={lat}&lon={lon}#map=18/{lat}/{lon}"
        gmaps_url = f"https://www.google.com/maps/@{lat},{lon},18z"

        st.markdown(
            f"<div class='links-bar'>"
            f"<a class='primary' href='{streetview_url}' target='_blank'>"
            f"Street View (vérification terrain)</a>"
            f"<a href='{cyclosm_url}' target='_blank'>CyclOSM plein écran</a>"
            f"<a href='{osm_url}' target='_blank'>OpenStreetMap standard</a>"
            f"<a href='{osm_query_url}' target='_blank'>Interroger les objets OSM</a>"
            f"<a href='{gmaps_url}' target='_blank'>Google Maps</a>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Légende CyclOSM
        st.markdown(
            "<div class='legend-box'>"
            "<b>Légende CyclOSM (éléments pertinents pour l'annotation)</b>"
            "<div class='legend-item'>"
            "<span style='color:#0000ff; font-weight:700;'>---</span> "
            "Piste cyclable séparée (<code>highway=cycleway</code>)</div>"
            "<div class='legend-item'>"
            "<span style='color:#0000ff;'>- - -</span> "
            "Bande cyclable sur chaussée (<code>cycleway=lane</code>)</div>"
            "<div class='legend-item'>"
            "<span style='color:#00aa00; font-weight:700;'>---</span> "
            "Voie verte / voie partagée piétons-vélos</div>"
            "<div class='legend-item'>"
            "<span style='color:#0092da; font-weight:700;'>&#9679;</span> "
            "Station de vélos en libre-service "
            "(<code>amenity=bicycle_rental</code>)</div>"
            "<div class='legend-item'>"
            "<span style='color:#0092da;'>P</span> "
            "Stationnement vélo / arceaux "
            "(<code>amenity=bicycle_parking</code>)</div>"
            "<div class='legend-item'>"
            "<span style='color:#ac39ac;'>&#9679;</span> "
            "Magasin / atelier vélo (<code>shop=bicycle</code>)</div>"
            "<div class='legend-item'>"
            "<span style='color:#fa8072;'>---</span> "
            "Chemin piéton, pas de vélo "
            "(<code>highway=footway</code>)</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("Coordonnées indisponibles pour cette station.")


with col_right:
    st.markdown("**Métadonnées GBFS**")

    meta_pairs = [
        ("Opérateur", row.get("operator_name")),
        ("Ville", row.get("city")),
        ("Type déclaré", row.get("station_type")),
        ("Capacité brute", row.get("capacity")),
        ("Confiance audit", row.get("audit_confidence")),
        ("Coordonnées", f"{lat:.5f}, {lon:.5f}" if lat and lon else None),
    ]
    for label, val in meta_pairs:
        v = str(val) if pd.notna(val) else "---"
        st.markdown(
            f"<div><span class='meta-label'>{label}</span><br>"
            f"<span class='meta-value'>{v}</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("")
    st.markdown("**Verdict du pipeline (flags A1--A7)**")
    any_flag = False
    for i in range(1, 8):
        col_name = f"flag_A{i}"
        is_on = bool(row.get(col_name, False)) if col_name in row.index else False
        if is_on:
            any_flag = True
        css = "flag-on" if is_on else "flag-off"
        marker = "ACTIF" if is_on else "---"
        desc = FLAG_LABELS.get(f"A{i}", "")
        st.markdown(
            f"<div class='flag-row'>"
            f"<span class='{css}'>A{i} [{marker}]</span> "
            f"<span style='color:#999; font-size:0.76rem;'>{desc}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    if not any_flag:
        st.markdown(
            "<div style='color:#27ae60; font-size:0.84rem; "
            "font-weight:600; margin-top:0.3rem;'>"
            "Aucun flag déclenché -- le pipeline considère cette station "
            "comme propre.</div>",
            unsafe_allow_html=True,
        )


# =====================================================================
# Formulaire d'annotation
# =====================================================================

st.markdown("---")
st.markdown("### Votre évaluation")

qa, qb = st.columns(2)

with qa:
    a_q1 = st.radio(
        "**Q1.** S'agit-il bien d'une station de vélos en libre-service ?",
        ["oui", "non", "indéterminé"],
        index=None,
        key="q1",
        help=(
            "Oui : vous identifiez un système de vélos ou VAE "
            "(bornes, arceaux, vélos visibles). "
            "Non : il s'agit d'un service d'autopartage (voitures), "
            "de trottinettes sans vélo, ou d'un point sans rapport "
            "avec le vélo-partage. "
            "Indéterminé : les éléments disponibles ne permettent "
            "pas de trancher."
        ),
    )

    a_q3 = st.radio(
        "**Q3.** Voyez-vous une infrastructure vélo à cet emplacement ?",
        ["oui", "non", "indéterminé"],
        index=None,
        key="q3",
        help=(
            "Consultez Street View et la carte CyclOSM. Cherchez : "
            "des bornes de vélos, des arceaux, un totem d'opérateur, "
            "ou de la signalétique vélo-partage. "
            "Si rien n'est visible et que l'imagerie est récente "
            "(vérifiez la date Street View), répondez non."
        ),
    )

    a_q5 = st.radio(
        "**Q5.** Au vu de tous ces éléments, quel est votre verdict ?",
        [
            "propre (station légitime)",
            "anomalie confirmée (le pipeline a raison)",
            "faux positif du pipeline (la station est légitime malgré le flag)",
            "indéterminé (impossible de trancher)",
        ],
        index=None,
        key="q5",
    )

with qb:
    a_q2 = st.radio(
        "**Q2.** La capacité déclarée est-elle un vrai nombre de bornes physiques ?",
        ["oui", "non", "NaN (champ vide)", "indéterminé"],
        index=None,
        key="q2",
        help=(
            "Oui : la valeur (ex : 20) correspond à un nombre réel "
            "d'emplacements physiques que l'on pourrait compter "
            "sur le terrain. "
            "Non : c'est un placeholder (ex : 100 sur toutes les "
            "stations du système) ou un estimateur statistique. "
            "NaN : le champ est vide dans le flux GBFS."
        ),
    )

    a_q4 = st.radio(
        "**Q4.** La station est-elle géographiquement cohérente avec son réseau ?",
        ["oui", "non"],
        index=None,
        key="q4",
        help=(
            "Regardez la carte : la station se trouve-t-elle dans "
            "la même zone urbaine que les autres stations du système, "
            "ou est-elle complètement isolée (autre ville, autre pays, "
            "milieu de nulle part) ?"
        ),
    )

    notes = st.text_area(
        "Remarques (facultatif)",
        value="",
        placeholder=(
            "Observations utiles : date de l'imagerie Street View, "
            "station visiblement en travaux, bornes retirées, "
            "doute sur le type de véhicule..."
        ),
        key="notes",
        height=100,
    )


# =====================================================================
# Boutons
# =====================================================================

all_answered = all([a_q1, a_q2, a_q3, a_q4, a_q5])

btn_save, btn_skip = st.columns([2, 1])

with btn_save:
    if st.button(
        "Enregistrer et passer à la suivante",
        type="primary",
        disabled=not all_answered,
        use_container_width=True,
    ):
        elapsed = time.time() - st.session_state.start_times.get(
            station_key, time.time()
        )
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
            updated = pd.concat(
                [existing, pd.DataFrame([new_row])], ignore_index=True
            )
        else:
            updated = pd.DataFrame([new_row])
        updated.to_csv(labels_path, index=False)
        st.session_state.start_times.pop(station_key, None)
        st.rerun()

with btn_skip:
    if st.button("Passer cette station", use_container_width=True):
        skip_row = {
            "system_id": row["system_id"],
            "station_id": row["station_id"],
            "stratum": stratum,
            "lat": lat, "lon": lon,
            "Q1_is_bikeshare": "passé",
            "Q2_capacity_physical": "passé",
            "Q3_exists_at_coords": "passé",
            "Q4_within_perimeter": "passé",
            "Q5_verdict": "skipped",
            "annotator": annotator_id,
            "notes": "",
            "duration_s": 0,
            "annotated_at": datetime.now(timezone.utc).isoformat(),
        }
        if labels_path.exists():
            existing = pd.read_csv(labels_path)
            updated = pd.concat(
                [existing, pd.DataFrame([skip_row])], ignore_index=True
            )
        else:
            updated = pd.DataFrame([skip_row])
        updated.to_csv(labels_path, index=False)
        st.session_state.start_times.pop(station_key, None)
        st.rerun()

if not all_answered:
    st.caption(
        "Répondez aux cinq questions ci-dessus pour activer "
        "le bouton Enregistrer."
    )
