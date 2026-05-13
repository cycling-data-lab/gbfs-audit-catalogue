"""Inline matplotlib figures for the Streamlit dashboard.

All figures share the academic palette declared in ``app.styles`` and
are decorated with ``st.cache_data`` so they are computed once per
data version. Inputs are passed explicitly (rather than read from
module globals) so the figures are easy to test offline.
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from .styles import ACCENT, MUTED, NAVY, NAVY_DARK


def configure_matplotlib() -> None:
    """Apply the academic rcParams. Idempotent."""
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Inter",
                "Helvetica Neue",
                "Helvetica",
                "Arial",
                "DejaVu Sans",
            ],
            "font.size": 9,
            "axes.titlesize": 9.5,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#404040",
            "axes.linewidth": 0.6,
            "axes.labelcolor": "#404040",
            "xtick.color": "#404040",
            "ytick.color": "#404040",
            "grid.color": "#E5E5E5",
            "grid.linewidth": 0.5,
            "figure.dpi": 110,
        }
    )


# Global counts from the MobilityData canonical-catalogue audit
# reported in the paper. The French counts are recomputed from the
# released summary at call time so they always match the on-disk
# parquet ; the global counts cover the 1,509-system sweep and are
# not present in the released artefacts.
GLOBAL_COUNTS: dict[str, int] = {
    "A1": 46,
    "A2": 48,
    "A3": 33,
    "A4": 81,
    "A5": 17,
    "A6": 14,
    "A7": 215,
}


def _fr_system_counts(summary: pd.DataFrame) -> dict[str, int]:
    """Number of French systems flagged on each anomaly class, computed
    from the per-system summary CSV. Falls back to the paper's static
    counts for any class that is not in the summary (older CSV layouts
    do not carry A4/A5)."""
    static_fallback = {"A1": 14, "A2": 3, "A3": 8, "A4": 4, "A5": 5, "A6": 0, "A7": 19}
    out: dict[str, int] = {}
    for k in range(1, 8):
        col = f"flag_A{k}"
        if col in summary.columns:
            out[f"A{k}"] = int((summary[col] > 0).sum())
        else:
            out[f"A{k}"] = static_fallback[f"A{k}"]
    return out


@st.cache_data(ttl=3600)
def fig_anomaly_incidence(fr_counts: dict[str, int]) -> plt.Figure:
    """Side-by-side bars: FR vs Global incidence per class A1..A7.

    ``fr_counts`` is the FR system-level count per class, typically
    obtained from ``_fr_system_counts(summary)``. The global counts are
    the paper's static reference values (the 1,509-system sweep is not
    bundled with the released artefacts)."""
    classes = ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    fr = [fr_counts.get(c, 0) for c in classes]
    glob = [GLOBAL_COUNTS[c] for c in classes]
    x = np.arange(len(classes))
    w = 0.38
    fig, ax = plt.subplots(figsize=(6.4, 2.7))
    b1 = ax.bar(
        x - w / 2,
        fr,
        width=w,
        color=NAVY,
        edgecolor="white",
        linewidth=0.5,
        label="French corpus (123 systems)",
    )
    b2 = ax.bar(
        x + w / 2,
        glob,
        width=w,
        color=MUTED,
        edgecolor="white",
        linewidth=0.5,
        label="Global catalogue (1,509 systems)",
    )
    for rect, v in zip(b1, fr):
        if v:
            ax.text(
                rect.get_x() + w / 2,
                v + 5,
                str(v),
                ha="center",
                va="bottom",
                fontsize=7,
                color=NAVY_DARK,
            )
    for rect, v in zip(b2, glob):
        ax.text(
            rect.get_x() + w / 2,
            v + 5,
            str(v),
            ha="center",
            va="bottom",
            fontsize=7,
            color="#5a7a96",
        )
    ax.set_xticks(x)
    ax.set_xticklabels(classes)
    ax.set_ylabel("Systems flagged")
    ax.set_ylim(0, max(glob) * 1.18)
    ax.grid(True, axis="y", alpha=0.45)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2)
    fig.tight_layout()
    return fig


@st.cache_data(ttl=3600)
def fig_confidence_distribution(audit_confidence: pd.Series) -> plt.Figure:
    """Stacked horizontal bar of audit_confidence proportions."""
    counts = audit_confidence.value_counts().reindex(
        ["high", "medium", "low"], fill_value=0
    )
    total = counts.sum()
    fig, ax = plt.subplots(figsize=(6.4, 0.9))
    palette = {"high": NAVY, "medium": MUTED, "low": "#D7E3F2"}
    left = 0
    for tier in ("high", "medium", "low"):
        v = int(counts[tier])
        ax.barh(
            0,
            v,
            left=left,
            color=palette[tier],
            edgecolor="white",
            linewidth=0.6,
            label=f"{tier} ({v:,}, {100 * v / total:.1f}%)",
        )
        if v / total > 0.04:
            ax.text(
                left + v / 2,
                0,
                f"{tier}\n{100 * v / total:.1f}%",
                ha="center",
                va="center",
                color="white",
                fontsize=8,
                fontweight=600,
            )
        left += v
    ax.set_xlim(0, total)
    ax.set_yticks([])
    ax.set_xlabel("Stations")
    ax.spines["left"].set_visible(False)
    ax.grid(False)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.55), ncol=3, fontsize=8)
    fig.tight_layout()
    return fig


@st.cache_data(ttl=3600)
def fig_operator_anomaly_rates(gs_df: pd.DataFrame) -> plt.Figure:
    """Top-10 operators by station count, with A3 / A7 rates."""
    op = (
        gs_df.groupby("operator_name")
        .agg(n=("uid", "size"), A3=("flag_A3", "mean"), A7=("flag_A7", "mean"))
        .sort_values("n", ascending=False)
        .head(10)
        .sort_values("n", ascending=True)
    )
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    y = np.arange(len(op))
    h = 0.38
    ax.barh(
        y + h / 2,
        op["A3"] * 100,
        height=h,
        color=NAVY,
        edgecolor="white",
        linewidth=0.5,
        label="A3 (structural over-capacity)",
    )
    ax.barh(
        y - h / 2,
        op["A7"] * 100,
        height=h,
        color=ACCENT,
        edgecolor="white",
        linewidth=0.5,
        alpha=0.85,
        label="A7 (null capacity field)",
    )
    for yi, (a3, a7) in enumerate(zip(op["A3"], op["A7"])):
        if a3 > 0.02:
            ax.text(
                a3 * 100 + 1.5,
                yi + h / 2,
                f"{a3*100:.0f}%",
                va="center",
                fontsize=7,
                color=NAVY_DARK,
            )
        if a7 > 0.02:
            ax.text(
                a7 * 100 + 1.5,
                yi - h / 2,
                f"{a7*100:.0f}%",
                va="center",
                fontsize=7,
                color=ACCENT,
            )
    ax.set_yticks(y)
    ax.set_yticklabels(
        [f"{name}  (n={int(n):,})" for name, n in zip(op.index, op["n"])],
        fontsize=8,
    )
    ax.set_xlabel("Anomaly rate (% of operator's stations)")
    ax.set_xlim(0, 110)
    ax.grid(True, axis="x", alpha=0.45)
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    fig.tight_layout()
    return fig


__all__ = [
    "configure_matplotlib",
    "GLOBAL_COUNTS",
    "_fr_system_counts",
    "fig_anomaly_incidence",
    "fig_confidence_distribution",
    "fig_operator_anomaly_rates",
]
