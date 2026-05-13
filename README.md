# GBFS Audit Catalogue

A reproducible audit of the 1,509 General Bikeshare Feed Specification (GBFS) systems published by municipal bike-sharing operators across 48 countries, together with the resulting 46-column reference dataset for 46,307 certified stations in France.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20125460.svg)](https://doi.org/10.5281/zenodo.20125460)
[![Hugging Face Datasets](https://img.shields.io/badge/Hugging%20Face-Datasets-yellow)](https://huggingface.co/datasets/rohanfosse/gbfs-audit-catalogue)
[![Streamlit demo](https://img.shields.io/badge/Streamlit-Live%20demo-red)](https://gbfs-audit.streamlit.app)
[![Project page](https://img.shields.io/badge/GitHub%20Pages-Project%20page-lightgrey)](https://rohanfosse.github.io/gbfs-audit-catalogue)
[![tests](https://github.com/rohanfosse/gbfs-audit-catalogue/actions/workflows/tests.yml/badge.svg)](https://github.com/rohanfosse/gbfs-audit-catalogue/actions/workflows/tests.yml)
[![Data licence: ODbL v1.0](https://img.shields.io/badge/data-ODbL%20v1.0-blue)](LICENSE-DATA)
[![Code licence: MIT](https://img.shields.io/badge/code-MIT-green)](LICENSE)

## Overview

The 2019 French Mobility Orientation Law (LOM, article L.1115-1) makes
the publication of GBFS feeds on `transport.data.gouv.fr` a regulatory
requirement for bike-sharing operators. The standard guarantees
syntactic interoperability across systems but does not enforce semantic
consistency: identical fields, for instance the
`station_information.capacity` integer, carry mutually incompatible
operational meanings across operators (a physical dock count for
dock-based fleets, a conditional-averaging estimator for free-floating
fleets, an arbitrary placeholder for under-reporting operators, or a
null value on operators that do not populate the field).

The audit reported in the companion paper, applied to the 1,509 GBFS
systems catalogued worldwide by MobilityData, exposes seven recurring
anomaly classes (A1 to A7) that together reclassify 30.9 % of the raw
French stations and flag 215 systems globally that a purely syntactic
validator would not detect.

This repository is the open release of the audit pipeline, the
certified dataset, the companion notebook with eight reproducible
recipes, the manuscript LaTeX source, and the focused Streamlit
dashboard.

## Key figures

| Indicator | Value |
| --- | --- |
| GBFS systems audited worldwide | 1,509 (48 countries) |
| Systems with at least one A1 to A7 flag | 204 (A1 to A5) + 14 (A6) + 215 (A7) |
| French GBFS systems audited | 123 |
| Certified stations released | 46,307 |
| Dock-based subset (fully audited) | 5,442 |
| Cities covered | 97 |
| Raw stations reclassified | 30.9 % (95 % bootstrap CI [30.5, 31.3]) |
| Columns in the released schema | 46 typed columns |
| Parquet file size | 6.6 MB |

## Quick start

### Hugging Face Datasets

```python
from datasets import load_dataset
gs = load_dataset("rohanfosse/gbfs-audit-catalogue", split="train").to_pandas()
```

### Direct from Zenodo (no authentication)

```python
import pandas as pd
gs = pd.read_parquet(
    "https://zenodo.org/records/20125460/files/"
    "stations_gold_standard_final.parquet"
)
```

### Local clone of this repository

```python
from audit_pipeline import load_catalogue, load_summary
gs = load_catalogue()        # the 46-column certified parquet
summary = load_summary()     # one row per audited system
```

### Inspect the audit at the row level

```python
clean = gs[(gs.station_type == "docked_bike")
           & (gs.audit_confidence == "high")]
print(len(clean))           # 5,402

gs.groupby("operator_name").agg(
    n=("uid", "size"),
    A3_rate=("flag_A3", "mean"),
    A7_rate=("flag_A7", "mean"),
).sort_values("n", ascending=False).head(10)
```

A self-contained companion notebook with eight recipes is provided at
[`notebooks/catalogue_recipes.ipynb`](notebooks/catalogue_recipes.ipynb).

## Repository layout

```text
gbfs-audit-catalogue/
├── catalogue/           Certified parquet and per-system summary CSV
├── audit_pipeline/      Standalone Python package (load + enrich API)
├── notebooks/           Companion notebook with 8 reproducible recipes
├── paper/               Manuscript LaTeX, figures, BibTeX (CSI submission)
├── app/                 Focused Streamlit dashboard (4 tabs)
├── docs/                GitHub Pages project page sources
├── huggingface/         Dataset card and Hub publication instructions
├── requirements.txt     Runtime dependencies
├── Dockerfile           Bit-exact reproduction environment
├── pyproject.toml       Python package metadata
├── LICENSE              MIT (code)
├── LICENSE-DATA         ODbL v1.0 (data)
└── CITATION.cff         Machine-readable citation
```

## The seven anomaly classes

The unified taxonomy is built jointly from the French corpus and the
global MobilityData catalogue.

| Class | Name | Signature | FR systems | Global systems |
| --- | --- | --- | --- | --- |
| A1 | Out-of-domain inclusion | Car-sharing advertised as a bike-sharing system | 14 | 46 |
| A2 | Placeholder capacity | Constant non-zero capacity across all stations | 3 | 48 |
| A3 | Structural over-capacity | Conditional averaging on free-floating fleet anchors | 8 | 33 |
| A4 | Geospatial error | Transposed coordinates or stations beyond 3 sigma | 3.8 % stations | 81 |
| A5 | Out-of-perimeter coverage | System area larger than 50,000 km^2 or out-of-jurisdiction | 5 | 17 |
| A6 | Zero-capacity dock | At least 1 % of stations declare capacity = 0 | 0 | 14 |
| A7 | Null capacity field | At least 50 % of stations declare capacity = NaN | 19 (FF) | 215 |

## Schema (46 columns)

Five identifiers, five spatial and administrative fields, four station
descriptors, eleven audit-pipeline outputs (the `station_type` enum,
the `capacity_raw` / `capacity_audited` pair, the seven `flag_Ai`
booleans, the normalised `operator_name` and the `audit_confidence`
ordinal), five network-geometry fields (intra- and inter-system KNN
distances and densities), and the contextual enrichment derived from
INSEE Filosofi, INSEE Recensement, ONISR BAAC, IGN BD ALTI, IGN BD
TOPO, the national GTFS aggregator and the FUB Cycling Barometer.

The eleven audit-pipeline outputs are the novel contribution at the row
level. They expose the audit's verdict per station, so that downstream
consumers can filter by class, by operator or by confidence without
re-running the pipeline. Every column carries a stable name, a declared
dtype, a source pointer and a measured completeness rate. The
machine-readable schema (JSON Schema, DCAT-AP record, Frictionless
Data Package descriptor and Croissant JSON-LD manifest) accompanies
the dataset on Zenodo.

## Reproduction

### Local Python environment

```bash
git clone https://github.com/rohanfosse/gbfs-audit-catalogue.git
cd gbfs-audit-catalogue
pip install -r requirements.txt
python -c "from audit_pipeline import load_catalogue; print(load_catalogue().shape)"
```

### Containerised reproduction

```bash
docker build -t gbfs-audit:1.0 .
docker run --rm gbfs-audit:1.0 \
  python -c "from audit_pipeline import load_catalogue; print(load_catalogue().shape)"
```

### Streamlit dashboard

```bash
streamlit run app/streamlit_app.py
```

The dashboard is deployed publicly at
[gbfs-audit.streamlit.app](https://gbfs-audit.streamlit.app).

## Citation

Please cite both the journal paper and the Zenodo deposit when reusing
the catalogue.

```bibtex
@article{Fosse2026gbfs,
  author  = {Foss\'e, Rohan and Pallares, Ga\"el},
  title   = {Auditing GBFS bike-sharing feeds at country and global scale:
             A reproducible anomaly taxonomy for open mobility data},
  journal = {Computer Standards \& Interfaces},
  year    = {2026},
  note    = {Under review}
}

@dataset{Fosse2026gbfsdata,
  author    = {Foss\'e, Rohan and Pallares, Ga\"el},
  title     = {{GBFS Audit Catalogue} v1.0},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.20125460}
}
```

A `CITATION.cff` file is also provided at the repository root for
GitHub's automatic citation tooling.

## Licences

Code (the `audit_pipeline`, `app`, `notebooks` and `paper` directories)
is released under the MIT licence. Data (the contents of `catalogue/`,
the Zenodo deposit and the Hugging Face dataset mirror) is released
under the Open Data Commons Open Database License (ODbL) v1.0.
Upstream attributions for the data sources used in the contextual
enrichment are listed in [`LICENSE-DATA`](LICENSE-DATA).

## Manuscript and Overleaf

The CSI manuscript LaTeX source lives under [`paper/`](paper/).
A dedicated `overleaf-paper` branch ships the same files flat at the
branch root, which is the layout Overleaf expects. See
[`paper/OVERLEAF.md`](paper/OVERLEAF.md) for the linking instructions
and [`paper/sync_overleaf.sh`](paper/sync_overleaf.sh) for the helper
script that refreshes the side branch after edits.

## Contact

**Rohan Fossé** (lead contact, `rfosse@cesi.fr`) — CESI École d'Ingénieurs, Montpellier, France.

**Gaël Pallares** — CESI LINEACT (EA 7527), Montpellier, France.

Issues and contributions are welcome at
[github.com/rohanfosse/gbfs-audit-catalogue/issues](https://github.com/rohanfosse/gbfs-audit-catalogue/issues).

This repository is the focused publication of one paper in a larger
research programme on French micromobility data quality. The broader
programme (the Soft Mobility Index IMD, the social-equity index IES,
the urban-scale extensions of the Bayesian station-level monitor)
lives at
[github.com/rohanfosse/bikeshare-data-explorer](https://github.com/rohanfosse/bikeshare-data-explorer).
