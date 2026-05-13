"""Fig 00 visual abstract -- minimalist, research-paper style.

Single accent colour (NAVY), monochrome elsewhere, typography-driven
layout. Designed to read like a graphical abstract in a journal:
input -> framework -> output flow, no decorative ornament.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

INK = "#1A2332"
GREY = "#5A6470"
LIGHTGREY = "#B0BCCB"
LINE = "#D8DEE6"
NAVY = "#1A6FBF"
WHITE = "#FFFFFF"

mpl.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Liberation Serif", "DejaVu Serif"],
    }
)


def _hline(ax, x0, x1, y, color=LINE, lw=0.6):
    ax.plot([x0, x1], [y, y], color=color, lw=lw, transform=ax.transAxes,
            solid_capstyle="butt")


def _arrow_down(ax, x, y0, y1):
    ax.annotate(
        "", xy=(x, y0), xytext=(x, y1),
        arrowprops=dict(arrowstyle="->", color=GREY, lw=0.9),
        xycoords="axes fraction",
    )


def main() -> None:
    fig = plt.figure(figsize=(7.0, 9.5))  # portrait, fits a single column
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_axis_off()

    # ===== Title =====
    ax.text(0.5, 0.965,
            "Auditing GBFS bike-sharing feeds at country and global scale",
            ha="center", fontsize=13, color=INK, fontweight="bold",
            transform=ax.transAxes)
    ax.text(0.5, 0.945,
            "A reproducible data-quality taxonomy for open mobility feeds",
            ha="center", fontsize=10, color=GREY, style="italic",
            transform=ax.transAxes)
    _hline(ax, 0.10, 0.90, 0.928, color=NAVY, lw=1.0)

    # ===== Input =====
    ax.text(0.5, 0.895, "INPUT", ha="center", fontsize=8.5, color=NAVY,
            fontweight="bold", transform=ax.transAxes,
            family="sans-serif")
    ax.text(0.5, 0.875,
            "1,509 GBFS systems across 48 countries",
            ha="center", fontsize=10.5, color=INK, fontweight="bold",
            transform=ax.transAxes)
    ax.text(0.5, 0.855,
            "transport.data.gouv.fr  ·  MobilityData canonical catalogue",
            ha="center", fontsize=9, color=GREY,
            transform=ax.transAxes)
    ax.text(0.5, 0.838,
            "~67,000 French station entries, no semantic audit applied upstream",
            ha="center", fontsize=8.5, color=GREY, style="italic",
            transform=ax.transAxes)

    _arrow_down(ax, 0.5, 0.810, 0.830)

    # ===== Framework =====
    ax.text(0.5, 0.790, "FRAMEWORK", ha="center", fontsize=8.5, color=NAVY,
            fontweight="bold", transform=ax.transAxes,
            family="sans-serif")
    ax.text(0.5, 0.770,
            "Seven-class data-quality taxonomy",
            ha="center", fontsize=11, color=INK, fontweight="bold",
            transform=ax.transAxes)
    ax.text(0.5, 0.751,
            "five structural errors (A1–A5)  +  two semantic warnings (A6–A7)",
            ha="center", fontsize=9, color=GREY, style="italic",
            transform=ax.transAxes)

    # Two columns of class labels
    structural = [
        ("A1", "Out-of-domain inclusion"),
        ("A2", "Placeholder capacity"),
        ("A3", "Structural over-capacity"),
        ("A4", "Geospatial outlier"),
        ("A5", "Out-of-perimeter coverage"),
    ]
    warnings_list = [
        ("A6", "Zero-capacity dock"),
        ("A7", "Null-capacity field"),
    ]
    # Structural column at left
    for i, (code, name) in enumerate(structural):
        y = 0.720 - i * 0.022
        ax.text(0.16, y, code, fontsize=9, color=NAVY, fontweight="bold",
                transform=ax.transAxes)
        ax.text(0.20, y, name, fontsize=9, color=INK,
                transform=ax.transAxes)
    # Warnings column at right
    for i, (code, name) in enumerate(warnings_list):
        y = 0.720 - i * 0.022
        ax.text(0.58, y, code, fontsize=9, color=NAVY, fontweight="bold",
                transform=ax.transAxes)
        ax.text(0.62, y, name, fontsize=9, color=INK,
                transform=ax.transAxes)
    # Column headers
    ax.text(0.16, 0.736, "structural errors", fontsize=7.5, color=GREY,
            style="italic", transform=ax.transAxes)
    ax.text(0.58, 0.736, "semantic warnings", fontsize=7.5, color=GREY,
            style="italic", transform=ax.transAxes)

    _arrow_down(ax, 0.5, 0.580, 0.604)

    # ===== Method =====
    ax.text(0.5, 0.564, "METHOD", ha="center", fontsize=8.5, color=NAVY,
            fontweight="bold", transform=ax.transAxes,
            family="sans-serif")
    ax.text(0.5, 0.544,
            "Nine-step idempotent purging pipeline",
            ha="center", fontsize=11, color=INK, fontweight="bold",
            transform=ax.transAxes)
    method_lines = [
        "reversible · logged · unit-tested (n=24, 85% coverage)",
        "kD-tree network geometry, robust 3-sigma statistics, six contextual hybridisations",
        "out-of-sample validation: 12-month MobilityData hold-out (H1, H2 pass)",
    ]
    for i, line in enumerate(method_lines):
        ax.text(0.5, 0.522 - i * 0.020, line, ha="center", fontsize=9,
                color=GREY, transform=ax.transAxes)

    _arrow_down(ax, 0.5, 0.430, 0.455)

    # ===== Output =====
    ax.text(0.5, 0.412, "RELEASED ARTEFACT", ha="center", fontsize=8.5, color=NAVY,
            fontweight="bold", transform=ax.transAxes,
            family="sans-serif")
    ax.text(0.5, 0.392, "GBFS Audit Catalogue v1.0",
            ha="center", fontsize=11.5, color=INK, fontweight="bold",
            transform=ax.transAxes)
    ax.text(0.5, 0.373,
            "DOI 10.5281/zenodo.20125460  ·  ODbL  ·  Croissant + DCAT-AP + JSON Schema",
            ha="center", fontsize=8.5, color=GREY, style="italic",
            transform=ax.transAxes)

    # Headline metrics row
    metrics = [
        ("46,307", "certified stations"),
        ("46", "typed columns"),
        ("123", "audited systems"),
        ("97", "cities"),
        ("30.9%", "removed by audit"),
    ]
    for i, (val, lab) in enumerate(metrics):
        x = 0.13 + i * 0.18
        ax.text(x, 0.328, val, fontsize=12, fontweight="bold", color=NAVY,
                ha="center", transform=ax.transAxes)
        ax.text(x, 0.307, lab, fontsize=8, color=GREY,
                ha="center", transform=ax.transAxes)

    _hline(ax, 0.10, 0.90, 0.275, color=LINE, lw=0.6)

    # ===== Headline finding =====
    ax.text(0.5, 0.250, "HEADLINE FINDING", ha="center", fontsize=8.5, color=NAVY,
            fontweight="bold", transform=ax.transAxes,
            family="sans-serif")
    headline_lines = [
        "Across the global catalogue, 17 deployments of a single operator publish",
        "c = NaN on every station and would pass any syntactic validator unchanged,",
        "yet collectively account for the largest single-operator capacity blackout in",
        "the audited corpus (A7 semantic warning, Italy case study).",
    ]
    for i, line in enumerate(headline_lines):
        ax.text(0.5, 0.228 - i * 0.020, line, ha="center", fontsize=9.5,
                color=INK, transform=ax.transAxes)

    # ===== Closing line =====
    ax.text(0.5, 0.115,
            "Syntactic standardisation is necessary but not sufficient.",
            ha="center", fontsize=10, color=INK, style="italic", fontweight="bold",
            transform=ax.transAxes)
    ax.text(0.5, 0.094,
            "An open mobility feed is a starting point for research, not a substitute for one.",
            ha="center", fontsize=9, color=GREY,
            transform=ax.transAxes)

    _hline(ax, 0.10, 0.90, 0.066, color=LINE, lw=0.6)
    ax.text(0.5, 0.040,
            "Fossé & Pallares  ·  CESI LINEACT, Montpellier  ·  2026  ·  Submitted to Computer Standards & Interfaces",
            ha="center", fontsize=7.5, color=GREY, transform=ax.transAxes)

    out_dir = Path("paper/figures")
    fig.savefig(out_dir / "fig00_visual_abstract.pdf", bbox_inches="tight", facecolor=WHITE)
    fig.savefig(out_dir / "fig00_visual_abstract.png", dpi=220, bbox_inches="tight", facecolor=WHITE)
    print("wrote fig00 visual abstract (minimalist, research style)")


if __name__ == "__main__":
    main()
