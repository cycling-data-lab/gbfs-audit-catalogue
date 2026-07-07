#!/usr/bin/env bash
# scripts/setup_fedora_latex.sh
# Install everything needed on Fedora 44+ to compile paper/manuscript.tex.
#
# Covers:
#   - the TeX Live distribution (pdflatex, bibtex, ...)
#   - the LaTeX packages used by the manuscript preamble (lmodern,
#     geometry, microtype, booktabs, algorithm2e, hyperref, enumitem,
#     caption, titlesec, authblk, ...)
#   - latexmk for the modern build flow
#   - Elsevier / IEEE / ACM journal classes (elsarticle, IEEEtran, ...)
#     via texlive-collection-publishers
#   - extra fonts and extra bibtex styles (rarely needed for this paper,
#     but cheap)
#
# Usage (from the repository root):
#     bash scripts/setup_fedora_latex.sh
#
# Disk footprint: ~1.3 GB.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo ">>> Installing TeX Live scheme-medium + collections + latexmk (sudo required)"
sudo dnf install -y \
    texlive-scheme-medium \
    texlive-collection-publishers \
    texlive-collection-bibtexextra \
    texlive-collection-fontsextra \
    texlive-collection-mathscience \
    texlive-algorithm2e \
    texlive-preprint \
    texlive-titlesec \
    texlive-enumitem \
    texlive-microtype \
    latexmk

# Note: on Fedora 44 the LaTeX package "authblk" ships inside the
# texlive-preprint bundle (there is no separate texlive-authblk
# package). dnf provides 'tex(authblk.sty)' confirms this.

echo ""
echo ">>> Verifying the toolchain"
pdflatex --version | head -1
bibtex  --version | head -1
latexmk --version | head -1

echo ""
echo ">>> Compiling paper/manuscript.tex as a smoke test"
cd "$PROJECT_DIR/paper"
# Three-pass build: pdflatex -> bibtex -> pdflatex -> pdflatex.
# latexmk handles the cycle automatically and only re-runs as needed.
latexmk -pdf -interaction=nonstopmode manuscript.tex

echo ""
echo "=== Done ==="
echo "Output PDF: paper/manuscript.pdf"
echo ""
echo "Day-to-day commands:"
echo "    cd paper && latexmk -pdf manuscript.tex     # build"
echo "    cd paper && latexmk -c                       # clean aux files"
echo "    cd paper && latexmk -C                       # clean aux + PDF"
