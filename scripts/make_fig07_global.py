"""Fig 07: cross-country incidence of A1-A5 structural classes
from the live global audit (with operator-name type inference).

Reads experiments/e2_threshold_sensitivity/global_audit_results_typed.csv
produced by `audit_live_systems.py --infer-type`. Aggregates per
country, plots a stacked horizontal bar of the top countries by
total flagged systems, with the four colours mapping to A1, A2, A3,
A4. A5 is reported separately in the body of the manuscript.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

NAVY = "#1A6FBF"
NAVY_LIGHT = "#9DBADD"
ACCENT = "#C0392B"
GREY = "#9AA5B1"
LINE = "#404040"

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
    }
)


def _to_int(v) -> int:
    if pd.isna(v):
        return 0
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def _to_bool(v) -> bool:
    return str(v).strip().lower() in {"true", "1"}


def main() -> None:
    src = Path("experiments/e2_threshold_sensitivity/global_audit_results_typed.csv")
    if not src.exists():
        raise SystemExit(f"missing {src} — run audit_live_systems.py --infer-type first")

    df = pd.read_csv(src)
    ok = df[df["status"] == "ok"].copy()
    print(f"audited successfully: {len(ok)} / {len(df)}")

    # Flag presence per system. A4 uses the paper's qualifying rule
    # (share > 5 % of stations AND >= 5 absolute outliers) so it does
    # not fire on every system that has a single isolated outlier.
    def _a4_qualifies(row) -> bool:
        n = _to_int(row.get("A4_n_stations"))
        try:
            share = float(row.get("A4_share_pct", 0.0))
        except (ValueError, TypeError):
            share = 0.0
        return n >= 5 and share > 5.0

    ok["A1"] = ok["A1_n_stations"].apply(_to_int) > 0
    ok["A2"] = ok["A2_flagged"].apply(_to_bool)
    ok["A3"] = ok["A3_n_stations"].apply(_to_int) > 0
    ok["A4"] = ok.apply(_a4_qualifies, axis=1)
    ok["A5"] = ok["A5_flagged"].apply(_to_bool)
    ok["any_A1_A5"] = ok[["A1", "A2", "A3", "A4", "A5"]].any(axis=1)

    # Aggregate per country
    per_country = (
        ok.groupby("country").agg(
            audited=("name", "size"),
            flagged=("any_A1_A5", "sum"),
            A1=("A1", "sum"),
            A2=("A2", "sum"),
            A3=("A3", "sum"),
            A4=("A4", "sum"),
            A5=("A5", "sum"),
        ).reset_index()
    )
    per_country = per_country.sort_values("flagged", ascending=True)
    # Keep countries with at least 1 flagged (top 18)
    per_country = per_country[per_country["flagged"] > 0].tail(18)

    print("\nPer-country breakdown of A1-A5 hits (top 18 by flagged):")
    print(per_country.to_string(index=False))

    fig, ax = plt.subplots(figsize=(7.6, 5.4))
    y = np.arange(len(per_country))
    classes = [
        ("A1", NAVY, "A1 carsharing"),
        ("A2", NAVY_LIGHT, "A2 placeholder"),
        ("A3", ACCENT, "A3 over-capacity"),
        ("A4", GREY, "A4 geospatial"),
    ]
    left = np.zeros(len(per_country))
    for code, color, label in classes:
        vals = per_country[code].to_numpy()
        ax.barh(y, vals, left=left, color=color, edgecolor="white", linewidth=0.5, label=label)
        left = left + vals
    # Total annotation
    totals = per_country["flagged"].to_numpy()
    for yi, total in zip(y, totals):
        ax.text(total + 0.4, yi, f"{int(total)}", va="center", fontsize=8, color=LINE)
    ax.set_yticks(y)
    ax.set_yticklabels(per_country["country"].tolist(), fontsize=9)
    ax.set_xlabel("Systems flagged on at least one of A1-A4 (A5 reported separately)")
    ax.set_xlim(0, max(totals) * 1.15 if len(totals) else 1)
    ax.grid(True, axis="x", alpha=0.4)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    out_dir = Path("paper/figures")
    fig.savefig(out_dir / "fig07_global_audit.pdf", bbox_inches="tight")
    fig.savefig(out_dir / "fig07_global_audit.png", dpi=180, bbox_inches="tight")
    print("wrote fig07")


if __name__ == "__main__":
    main()
