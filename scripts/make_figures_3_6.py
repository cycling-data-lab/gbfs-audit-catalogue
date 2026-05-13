"""fig03 (regions) and fig06 (mobility deserts), reproducible from parquet."""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

NAVY = "#1A6FBF"
NAVY_DARK = "#15538f"
ACCENT = "#C0392B"
MUTED = "#9DBADD"
GREY = "#9AA5B1"
OUT_DIR = Path("paper/figures")

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Inter", "Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": "#E5E5E5",
        "grid.linewidth": 0.5,
        "figure.dpi": 110,
    }
)


# Map of French département prefix (first 2-3 digits of INSEE code_commune)
# to métropolitaine région administrative name (post-2016 reform).
DEPT_TO_REGION = {
    # Île-de-France
    "75": "Île-de-France", "77": "Île-de-France", "78": "Île-de-France",
    "91": "Île-de-France", "92": "Île-de-France", "93": "Île-de-France",
    "94": "Île-de-France", "95": "Île-de-France",
    # Auvergne-Rhône-Alpes
    "01": "Auvergne-Rhône-Alpes", "03": "Auvergne-Rhône-Alpes",
    "07": "Auvergne-Rhône-Alpes", "15": "Auvergne-Rhône-Alpes",
    "26": "Auvergne-Rhône-Alpes", "38": "Auvergne-Rhône-Alpes",
    "42": "Auvergne-Rhône-Alpes", "43": "Auvergne-Rhône-Alpes",
    "63": "Auvergne-Rhône-Alpes", "69": "Auvergne-Rhône-Alpes",
    "73": "Auvergne-Rhône-Alpes", "74": "Auvergne-Rhône-Alpes",
    # Provence-Alpes-Côte d'Azur
    "04": "PACA", "05": "PACA", "06": "PACA",
    "13": "PACA", "83": "PACA", "84": "PACA",
    # Occitanie
    "09": "Occitanie", "11": "Occitanie", "12": "Occitanie",
    "30": "Occitanie", "31": "Occitanie", "32": "Occitanie",
    "34": "Occitanie", "46": "Occitanie", "48": "Occitanie",
    "65": "Occitanie", "66": "Occitanie", "81": "Occitanie",
    "82": "Occitanie",
    # Nouvelle-Aquitaine
    "16": "Nouvelle-Aquitaine", "17": "Nouvelle-Aquitaine",
    "19": "Nouvelle-Aquitaine", "23": "Nouvelle-Aquitaine",
    "24": "Nouvelle-Aquitaine", "33": "Nouvelle-Aquitaine",
    "40": "Nouvelle-Aquitaine", "47": "Nouvelle-Aquitaine",
    "64": "Nouvelle-Aquitaine", "79": "Nouvelle-Aquitaine",
    "86": "Nouvelle-Aquitaine", "87": "Nouvelle-Aquitaine",
    # Bretagne
    "22": "Bretagne", "29": "Bretagne", "35": "Bretagne", "56": "Bretagne",
    # Pays de la Loire
    "44": "Pays de la Loire", "49": "Pays de la Loire",
    "53": "Pays de la Loire", "72": "Pays de la Loire",
    "85": "Pays de la Loire",
    # Normandie
    "14": "Normandie", "27": "Normandie", "50": "Normandie",
    "61": "Normandie", "76": "Normandie",
    # Hauts-de-France
    "02": "Hauts-de-France", "59": "Hauts-de-France",
    "60": "Hauts-de-France", "62": "Hauts-de-France",
    "80": "Hauts-de-France",
    # Grand Est
    "08": "Grand Est", "10": "Grand Est", "51": "Grand Est",
    "52": "Grand Est", "54": "Grand Est", "55": "Grand Est",
    "57": "Grand Est", "67": "Grand Est", "68": "Grand Est",
    "88": "Grand Est",
    # Centre-Val de Loire
    "18": "Centre-Val de Loire", "28": "Centre-Val de Loire",
    "36": "Centre-Val de Loire", "37": "Centre-Val de Loire",
    "41": "Centre-Val de Loire", "45": "Centre-Val de Loire",
    # Bourgogne-Franche-Comté
    "21": "Bourgogne-Franche-Comté", "25": "Bourgogne-Franche-Comté",
    "39": "Bourgogne-Franche-Comté", "58": "Bourgogne-Franche-Comté",
    "70": "Bourgogne-Franche-Comté", "71": "Bourgogne-Franche-Comté",
    "89": "Bourgogne-Franche-Comté", "90": "Bourgogne-Franche-Comté",
    # Corse
    "2A": "Corse", "2B": "Corse",
    # DOM-TOM (3-letter codes)
    "971": "Guadeloupe", "972": "Martinique", "973": "Guyane",
    "974": "La Réunion", "976": "Mayotte",
}


def _region_of(code: str) -> str:
    if not code:
        return "Unknown"
    code = str(code).strip()
    # DOM/TOM (3-letter codes start with 97)
    if code.startswith("97") and len(code) >= 3:
        return DEPT_TO_REGION.get(code[:3], "DOM/TOM")
    pref = code[:2]
    return DEPT_TO_REGION.get(pref, "Unknown")


def fig03_region_stations(df: pd.DataFrame) -> None:
    """Certified stations by région, split by station_type so the audit's
    central message (FF/carsharing inflate dock counts) is visible."""
    df = df.copy()
    df["region"] = df["code_commune"].apply(_region_of)

    pivot = (
        df.groupby(["region", "station_type"]).size().unstack(fill_value=0)
    )
    for col in ("docked_bike", "free_floating", "carsharing"):
        if col not in pivot.columns:
            pivot[col] = 0
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total", ascending=True)
    # Drop "Unknown" if small
    if "Unknown" in pivot.index and pivot.loc["Unknown", "total"] < 50:
        pivot = pivot.drop("Unknown")

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    y = np.arange(len(pivot))
    left = np.zeros(len(pivot))
    cats = [
        ("docked_bike", "Dock-based (certified)", NAVY),
        ("free_floating", "Free-floating (relabelled)", GREY),
        ("carsharing", "Car-sharing (A1)", MUTED),
    ]
    for key, label, color in cats:
        ax.barh(y, pivot[key].values, left=left, color=color, label=label, edgecolor="white", linewidth=0.4)
        left = left + pivot[key].values
    for yi, region in zip(y, pivot.index):
        total = pivot.loc[region, "total"]
        dock = pivot.loc[region, "docked_bike"]
        ax.text(
            total + max(left) * 0.005,
            yi,
            f"{total:,} ({dock:,} dock)",
            va="center",
            fontsize=8,
            color="#404040",
        )
    ax.set_yticks(y)
    ax.set_yticklabels(pivot.index, fontsize=9)
    ax.set_xlabel("Certified stations by region (split by station\\_type)")
    ax.set_xlim(0, max(left) * 1.18)
    ax.grid(True, axis="x", alpha=0.4)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig03_region_stations.pdf", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig03_region_stations.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig06_mobility_deserts(df: pd.DataFrame) -> None:
    """Top 15 French cities by mobility-desert station count."""
    docked = df[df.station_type == "docked_bike"].copy()
    q1 = float(docked["revenu_median_uc"].quantile(0.25))
    deserts = docked[
        (docked["revenu_median_uc"] < q1)
        & (docked["gtfs_heavy_stops_300m"] == 0)
    ]
    total = len(deserts)
    share = 100 * total / len(docked)
    top = deserts["city"].value_counts().head(15).sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    y = np.arange(len(top))
    ax.barh(y, top.values, color=NAVY, edgecolor="white", linewidth=0.5)
    for yi, v in zip(y, top.values):
        ax.text(v + max(top) * 0.01, yi, f"{v}", va="center", fontsize=8, color=NAVY_DARK)
    ax.set_yticks(y)
    ax.set_yticklabels(top.index, fontsize=9)
    ax.set_xlabel("Mobility-desert stations")
    ax.text(
        0.98,
        0.06,
        f"total = {total:,}  ({share:.1f}\\,\\% of dock-based)\nQ1 income = {q1:,.0f} EUR / CU",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#404040",
    )
    ax.grid(True, axis="x", alpha=0.4)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig06_mobility_deserts.pdf", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig06_mobility_deserts.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    df = pd.read_parquet("catalogue/stations_gold_standard_final.parquet")
    fig03_region_stations(df)
    print("wrote fig03")
    fig06_mobility_deserts(df)
    print("wrote fig06")


if __name__ == "__main__":
    main()
