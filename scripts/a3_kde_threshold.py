"""Data-driven A3 threshold via kernel density estimation +
valley-finding on the global ratio distribution.

KDE is the appropriate technique here because the empirical
distribution of $\\bar c_{\\text{profile}} / \\bar c_{\\text{actual}}$ is
neither a mixture of Gaussians (it contains a delta at exactly 1.0)
nor a single-component unimodal distribution. The natural object
to inspect is the kernel-smoothed density on $\\log_{10}$(ratio)
and to locate the valleys (local minima) between its modes : a
valley is, by construction, the lowest-density boundary between
two empirical clusters of systems.

Output : printed table of (mode_location, valley_location) pairs
plus the recommended A3 threshold (the valley separating the
"clean / mildly elevated" mode from the "biased FF" mode).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.stats import gaussian_kde


def main() -> None:
    src = Path("experiments/e2_threshold_sensitivity/global_a3_ratio.csv")
    df = pd.read_csv(src)
    ratios = df[df.status == "ok"].ratio.dropna().to_numpy()
    print(f"n total: {len(ratios)}")
    print(f"n with ratio > 1.001 (drop the delta-at-1): {(ratios > 1.001).sum()}")

    # ---- Full set on log10(ratio) ----
    log_r = np.log10(ratios)
    grid = np.linspace(log_r.min() - 0.1, log_r.max() + 0.1, 10000)
    # Silverman's rule of thumb for the bandwidth
    bw = 0.9 * min(np.std(log_r), (np.percentile(log_r, 75) - np.percentile(log_r, 25)) / 1.34) * (len(log_r) ** -0.2)
    kde = gaussian_kde(log_r, bw_method=bw / np.std(log_r))
    density = kde(grid)

    # Find peaks (modes) and valleys (local minima)
    peaks, _ = find_peaks(density, prominence=0.05 * density.max())
    valleys, _ = find_peaks(-density, prominence=0.01 * density.max())

    print("\n== KDE on full log10(ratio) ==")
    print(f"  bandwidth (Silverman scaled): {bw:.3f} (log10 units)")
    print(f"  peaks: {[round(10**grid[p], 3) for p in peaks]}")
    print(f"  valleys: {[round(10**grid[v], 3) for v in valleys]}")

    # ---- Subset: ratio > 1.01 ----
    sub = ratios[ratios > 1.01]
    log_sub = np.log10(sub)
    grid2 = np.linspace(log_sub.min() - 0.1, log_sub.max() + 0.1, 10000)
    bw2 = 0.9 * min(np.std(log_sub), (np.percentile(log_sub, 75) - np.percentile(log_sub, 25)) / 1.34) * (len(log_sub) ** -0.2)
    kde2 = gaussian_kde(log_sub, bw_method=bw2 / np.std(log_sub))
    density2 = kde2(grid2)
    peaks2, _ = find_peaks(density2, prominence=0.05 * density2.max())
    valleys2, _ = find_peaks(-density2, prominence=0.01 * density2.max())

    print("\n== KDE on log10(ratio > 1.01) ==")
    print(f"  bandwidth (Silverman scaled): {bw2:.3f}")
    print(f"  peaks at ratio = {[round(10**grid2[p], 3) for p in peaks2]}")
    print(f"  valleys at ratio = {[round(10**grid2[v], 3) for v in valleys2]}")

    # Save the density curves for reference
    out_dir = Path("experiments/e2_threshold_sensitivity")
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"log10_ratio": grid, "density": density}).to_csv(
        out_dir / "kde_full.csv", index=False
    )
    pd.DataFrame({"log10_ratio": grid2, "density": density2}).to_csv(
        out_dir / "kde_subset.csv", index=False
    )

    # ---- Verdict ----
    if valleys2.size:
        candidate_thresholds = sorted([10 ** grid2[v] for v in valleys2])
        print()
        print("Data-driven A3 threshold candidates (KDE valleys on subset):")
        for t in candidate_thresholds:
            print(f"  ratio = {t:.2f}")
        print()
        print(
            "Compared to the conservative paper threshold tau_A3 = 5, "
            f"the lowest KDE valley sits at ratio {candidate_thresholds[0]:.2f}."
        )


if __name__ == "__main__":
    main()
