"""Fig 08: capacity-field semantic ambiguity across the French
free-floating subset. Title updated to 'four publication conventions
across six operator-city deployments' to match the corrected manuscript.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

NAVY = "#1A6FBF"
NAVY_DARK = "#15538f"
ACCENT = "#C0392B"
AMBER = "#E08E0B"
GREY = "#9AA5B1"
LIGHT = "#F4F6F9"

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Inter", "Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.titlesize": 12,
    }
)

# Convention -> color (4 distinct semantics)
CONVENTIONS = {
    "NaN": ACCENT,
    "Constant placeholder": AMBER,
    "Per-vehicle ratio": NAVY,
    "Conditional fleet profile": NAVY_DARK,
}

# 6 operator-city deployments
DEPLOYMENTS = [
    {
        "operator": "Dott (FR, 8 cities)",
        "convention": "NaN",
        "value": "NaN",
        "stations": "20,224",
        "anomaly": "A7",
    },
    {
        "operator": "Bird (FR, 11 cities)",
        "convention": "NaN",
        "value": "NaN",
        "stations": "4,499",
        "anomaly": "A7",
    },
    {
        "operator": "Pony — Nice",
        "convention": "Constant placeholder",
        "value": "c = 100",
        "stations": "412",
        "anomaly": "A2",
    },
    {
        "operator": "Pony — Paris",
        "convention": "Per-vehicle ratio",
        "value": "c = 1.6",
        "stations": "3,617",
        "anomaly": "A3",
    },
    {
        "operator": "Pony — 12 other cities",
        "convention": "Conditional fleet profile",
        "value": "c = 2 to 15",
        "stations": "7,436",
        "anomaly": "A3",
    },
    {
        "operator": "Voi (FR, 4 cities)",
        "convention": "Conditional fleet profile",
        "value": "c = 5 to 10",
        "stations": "2,816",
        "anomaly": "A3",
    },
]


def main() -> None:
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.4))
    fig.suptitle(
        "Four publication conventions across six operator–city deployments "
        "(French free-floating subset, 39\\,235 stations, 84.7\\,\\% of certified rows)",
        fontsize=11,
        y=0.99,
    )
    for ax, deployment in zip(axes.flat, DEPLOYMENTS):
        color = CONVENTIONS[deployment["convention"]]
        # accent bar on the left
        ax.add_patch(mpatches.Rectangle((0, 0), 0.04, 1, color=color, transform=ax.transAxes))
        # operator
        ax.text(0.08, 0.86, deployment["operator"], transform=ax.transAxes,
                fontsize=11.5, fontweight="bold", color="#1A2332", va="top")
        # anomaly chip
        ax.text(0.92, 0.86, deployment["anomaly"], transform=ax.transAxes,
                fontsize=11, fontweight="bold", color=color, ha="right", va="top")
        # convention label
        ax.text(0.08, 0.58, deployment["convention"], transform=ax.transAxes,
                fontsize=10, color="#404040", va="top")
        # value
        ax.text(0.08, 0.36, deployment["value"], transform=ax.transAxes,
                fontsize=12, color=color, family="monospace", va="top")
        # stations
        ax.text(0.08, 0.12, deployment["stations"] + " stations", transform=ax.transAxes,
                fontsize=9, color=GREY, va="top")
        # frame
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_edgecolor("#D8DEE6")
            spine.set_linewidth(0.6)
        ax.set_facecolor(LIGHT)
    # legend block under the figure: the four conventions
    handles = [
        mpatches.Patch(color=color, label=name) for name, color in CONVENTIONS.items()
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=4,
        bbox_to_anchor=(0.5, -0.04),
        frameon=False,
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    out_dir = Path("paper/figures")
    fig.savefig(out_dir / "fig08_capacity_semantics.pdf", bbox_inches="tight")
    fig.savefig(out_dir / "fig08_capacity_semantics.png", dpi=180, bbox_inches="tight")
    print("wrote fig08")


if __name__ == "__main__":
    main()
