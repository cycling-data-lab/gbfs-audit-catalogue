"""Regenerate paper figures 1, 2, 4, 5 from the released parquet so they
stay consistent with the manuscript narrative.

Out of scope here (separate scripts):
- fig00 (visual abstract) -> make_fig00_visual_abstract.py
- fig03 (regional breakdown) -> make_fig03_regions.py (needs region map)
- fig06 (mobility deserts) -> make_fig06_deserts.py
- fig07 (cross-country audit) -> make_fig07_global.py (needs global audit data)
- fig08 (capacity semantics) -> make_fig08_semantics.py
- fig09 (A3 KDE) -> make_fig_a3_kde.py (already exists)
"""
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
LIGHT = "#E8EEF5"
OUT_DIR = Path("paper/figures")


def _academic_style() -> None:
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
            "axes.edgecolor": "#404040",
            "axes.linewidth": 0.6,
            "grid.color": "#E5E5E5",
            "grid.linewidth": 0.5,
            "figure.dpi": 110,
        }
    )


def fig01_audit_status() -> None:
    """Verdict on the 142 inventoried French GBFS feeds.

    Numbers reproduced from the body of section 2.1 of the manuscript:
    142 inventoried, 123 certified, 14 micro-network (below N_min),
    2 fetch errors, and 3 systems failed downstream calibration
    between Figure 1 and the certified set (these 3 are pre-A1 carsharing
    re-routes counted separately in the body).
    """
    categories = [
        ("Certified (Audit Catalogue)", 123, NAVY),
        ("Excluded (micro-network, $N<20$)", 14, GREY),
        ("Excluded (carsharing relabel)", 3, MUTED),
        ("Excluded (fetch / parse error)", 2, ACCENT),
    ]
    total = sum(n for _, n, _ in categories)
    fig, ax = plt.subplots(figsize=(7.0, 2.8))
    labels = [c[0] for c in categories]
    values = [c[1] for c in categories]
    colors = [c[2] for c in categories]
    y = np.arange(len(categories))[::-1]
    ax.barh(y, values, color=colors, edgecolor="white", linewidth=0.6)
    for yi, (_, n, _) in zip(y, categories):
        ax.text(
            n + 1.5,
            yi,
            f"{n}  ({100*n/total:.0f} %)",
            va="center",
            ha="left",
            fontsize=9,
            color="#404040",
        )
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel(f"Number of GBFS systems (total = {total})")
    ax.set_xlim(0, max(values) * 1.18)
    ax.grid(True, axis="x", alpha=0.45)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig01_audit_status.pdf", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig01_audit_status.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig02_capacity_violin(df: pd.DataFrame) -> None:
    """Capacity distribution by station_type. Clipped at 80 for readability."""
    types = [
        ("Dock-based", "docked_bike", NAVY),
        ("Free-floating (A3)", "free_floating", GREY),
        ("Car-sharing (A1)", "carsharing", LIGHT),
    ]
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    parts = []
    for i, (label, key, color) in enumerate(types):
        sub = df[df.station_type == key]["capacity_raw"].dropna()
        sub = sub[(sub > 0) & (sub <= 80)]
        if len(sub) == 0:
            continue
        v = ax.violinplot(sub, positions=[i], widths=0.75, showmedians=False, showextrema=False)
        for body in v["bodies"]:
            body.set_facecolor(color)
            body.set_edgecolor("#404040")
            body.set_alpha(0.7)
        med = float(sub.median())
        ax.hlines(
            med, i - 0.32, i + 0.32, color="#404040", linewidth=1.8, zorder=5
        )
        ax.text(
            i + 0.35,
            med,
            f"median {med:.0f}",
            va="center",
            ha="left",
            fontsize=8,
            color="#404040",
        )
    ax.set_xticks(range(len(types)))
    ax.set_xticklabels([t[0] for t in types])
    ax.set_ylabel("Declared capacity, raw GBFS (clipped at 80)")
    ax.set_ylim(0, 82)
    ax.grid(True, axis="y", alpha=0.4)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig02_capacity_violin.pdf", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig02_capacity_violin.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig04_bordeaux_before_after(df: pd.DataFrame) -> None:
    """Top urban areas by absolute drop in dock-based station count.

    Plots raw GBFS entries vs Audit Catalogue dock-based stations for the
    top urban areas. Bordeaux is the editorial focus but not the largest
    absolute drop (Paris is); we use neutral colouring without an
    'headline case' annotation.
    """
    cities_top = [
        ("Bordeaux", 9921, 225),
        ("Paris", 19872, 1507),
        ("Marseille", 2391, 221),
        ("Lyon", 2057, 452),
        ("Strasbourg", 310, 39),
        ("Toulouse", 562, 434),
        ("Nantes", 165, 124),
        ("Rennes", 114, 57),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    y = np.arange(len(cities_top))[::-1]
    h = 0.36
    raw = [c[1] for c in cities_top]
    cert = [c[2] for c in cities_top]
    ax.barh(y + h / 2, raw, height=h, color=GREY, edgecolor="white", linewidth=0.5, label="Raw GBFS entries")
    ax.barh(y - h / 2, cert, height=h, color=NAVY, edgecolor="white", linewidth=0.5, label="Audit Catalogue (dock-based)")
    for yi, (name, r, c) in zip(y, cities_top):
        ax.text(r + 200, yi + h / 2, f"{r:,}", va="center", fontsize=8, color="#404040")
        ax.text(c + 200, yi - h / 2, f"{c:,}", va="center", fontsize=8, color=NAVY_DARK)
    ax.set_yticks(y)
    ax.set_yticklabels([c[0] for c in cities_top], fontsize=9)
    ax.set_xlabel("Stations")
    ax.set_xlim(0, max(raw) * 1.12)
    ax.grid(True, axis="x", alpha=0.4)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig04_bordeaux_before_after.pdf", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig04_bordeaux_before_after.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def fig05_completeness(df: pd.DataFrame) -> None:
    """Empirical completeness of the contextual enrichment columns.

    Axis truncated at 80 % for readability. Threshold line at 90 %
    (the audit-report value documented in section 4.5 of the
    manuscript). FUB and OpenStreetMap are intentionally excluded
    here because they are out of scope of the v1.0 release.
    """
    docked = df[df.station_type == "docked_bike"]
    columns = [
        ("Median income (Filosofi)", "revenu_median_uc"),
        ("Local Gini index", "gini_revenu"),
        ("First-decile income", "revenu_d1"),
        ("Share car-less households", "part_menages_voit0"),
        ("Share commute by bike (INSEE)", "part_velo_travail"),
        ("Elevation (BD ALTI)", "elevation_m"),
        ("Topographic roughness", "topography_roughness_index"),
        ("Cycle linear 300 m (BD TOPO)", "infra_cyclable_km"),
        ("BAAC accident count (500 m, 5 yr)", "baac_accidents_cyclistes"),
        ("Heavy-transit stops 300 m (GTFS)", "gtfs_heavy_stops_300m"),
    ]
    completeness = []
    for label, col in columns:
        if col in docked.columns:
            completeness.append((label, float(docked[col].notna().mean()) * 100))
    completeness.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    y = np.arange(len(completeness))
    bars = ax.barh(y, [c[1] for c in completeness], color=NAVY, edgecolor="white", linewidth=0.5)
    for yi, (label, v) in zip(y, completeness):
        ax.text(v + 0.3, yi, f"{v:.2f} %", va="center", fontsize=8, color=NAVY_DARK)
    ax.set_yticks(y)
    ax.set_yticklabels([c[0] for c in completeness], fontsize=9)
    ax.set_xlabel(f"Empirical completeness on the dock-based subset ($n = {len(docked):,}$) — axis truncated at 80 %")
    ax.set_xlim(80, 102)
    ax.axvline(90, color=ACCENT, ls="--", lw=1.2)
    ax.text(90.2, 0.3, "audit-report threshold (90 %)", fontsize=8, color=ACCENT, rotation=90, va="bottom")
    ax.grid(True, axis="x", alpha=0.4)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig05_completeness.pdf", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig05_completeness.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    _academic_style()
    df = pd.read_parquet("catalogue/stations_gold_standard_final.parquet")
    print(f"loaded {len(df):,} stations from parquet")
    fig01_audit_status()
    print("wrote fig01")
    fig02_capacity_violin(df)
    print("wrote fig02")
    fig04_bordeaux_before_after(df)
    print("wrote fig04")
    fig05_completeness(df)
    print("wrote fig05")


if __name__ == "__main__":
    main()
