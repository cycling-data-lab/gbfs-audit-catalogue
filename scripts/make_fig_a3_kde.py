"""Generate the A3 capacity-profile-ratio KDE figure for the paper.

Produces paper/figures/fig09_a3_kde_valley.pdf, a single-panel figure
showing the kernel-density estimates of $\\log_{10}(\\bar c_{\\text{profile}}
/ \\bar c_{\\text{actual}})$ on the non-trivial subset (ratio > 1.01,
$n = 98$ systems) at two bandwidths, with the location of $\\tau_{A3}=5$
and the data-driven valley between the near-unity and high-bias modes
explicitly annotated.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.stats import gaussian_kde

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Inter", "Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

NAVY = "#1A6FBF"
ACCENT = "#C0392B"
MUTED = "#9DBADD"


def main() -> None:
    src = Path("experiments/e2_threshold_sensitivity/global_a3_ratio.csv")
    df = pd.read_csv(src)
    ratios = df[df.status == "ok"].ratio.dropna().to_numpy()
    sub = ratios[ratios > 1.01]
    log_sub = np.log10(sub)

    grid = np.linspace(log_sub.min() - 0.1, log_sub.max() + 0.1, 4000)

    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    for bw, color, label in [
        (0.12, NAVY, r"KDE, bw $=0.12$"),
        (0.15, ACCENT, r"KDE, bw $=0.15$"),
    ]:
        kde = gaussian_kde(log_sub, bw_method=bw)
        d = kde(grid)
        ax.plot(grid, d, color=color, lw=1.8, label=label)
        # Annotate peaks
        peaks, _ = find_peaks(d, prominence=0.04 * d.max())
        valleys, _ = find_peaks(-d, prominence=0.01 * d.max())
        for p in peaks:
            ax.scatter(grid[p], d[p], color=color, s=24, marker="o", zorder=5)
        for v in valleys:
            ax.scatter(grid[v], d[v], color=color, s=24, marker="v", zorder=5)

    # tau_A3 = 5 line
    tau_log = np.log10(5)
    ax.axvline(
        tau_log,
        color="#222",
        ls="--",
        lw=1.2,
        label=r"paper threshold $\tau_{A3} = 5$",
    )
    ax.annotate(
        r"$\tau_{A3} = 5$",
        xy=(tau_log, ax.get_ylim()[1] * 0.95),
        xytext=(tau_log + 0.08, 0.55),
        fontsize=8,
        color="#222",
    )

    # x-ticks in linear ratio for readability
    log_ticks = [0, np.log10(2), np.log10(5), 1, np.log10(20), 2, np.log10(500), 3]
    ax.set_xticks(log_ticks)
    ax.set_xticklabels(
        [r"$10^0$", r"$2$", r"$5$", r"$10^1$", r"$20$", r"$10^2$", r"$500$", r"$10^3$"]
    )
    ax.set_xlabel(r"$\bar c_{\mathrm{profile}} / \bar c_{\mathrm{actual}}$  (log$_{10}$ scale)")
    ax.set_ylabel("Kernel density")
    ax.set_title(
        r"A3 ratio distribution on the global subset ($n=98$, ratio $> 1.01$)",
        loc="left",
        fontsize=10,
    )
    ax.legend(loc="upper right", frameon=False)
    ax.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    out = Path("paper/figures/fig09_a3_kde_valley.pdf")
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=200, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
