# GBFS Audit Catalogue

**A reproducible audit of 1,509 open bike-sharing feeds across 48 countries.**

The General Bikeshare Feed Specification (GBFS) is the open standard published by municipal bike-sharing operators on national open-data portals. The standard guarantees syntactic interoperability — but not semantic consistency. The audit reported here exposes **seven recurring anomaly classes (A1–A7)** that together reclassify **30.9 %** of the raw French stations and flag 215 systems worldwide that the v1.0 taxonomy would otherwise miss.

The result is the **GBFS Audit Catalogue v1.0**, a 46-column reference dataset for 46,307 certified stations across 123 French operators, with per-row anomaly flags and contextual enrichment from INSEE, BAAC, BD TOPO, BD ALTI and the national GTFS aggregator.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20125460.svg)](https://doi.org/10.5281/zenodo.20125460)
[![Hugging Face](https://img.shields.io/badge/dataset-Hugging%20Face-yellow)](https://huggingface.co/datasets/rohanfosse/gbfs-audit-catalogue)
[![Streamlit](https://img.shields.io/badge/demo-Streamlit-red)](https://gbfs-audit.streamlit.app)
[![Licence ODbL](https://img.shields.io/badge/data-ODbL%20v1.0-blue)](LICENSE-DATA)
[![Licence MIT](https://img.shields.io/badge/code-MIT-green)](LICENSE)

---

## Quick start

### 1. Load via Hugging Face Datasets

```python
from datasets import load_dataset
gs = load_dataset("rohanfosse/gbfs-audit-catalogue", split="train").to_pandas()
```

### 2. Load via Zenodo (no auth, one HTTPS fetch)

```python
import pandas as pd
gs = pd.read_parquet(
    "https://zenodo.org/records/20125460/files/"
    "stations_gold_standard_final.parquet"
)
```

### 3. Load from a local clone of this repo

```python
from audit_pipeline import load_catalogue
gs = load_catalogue()      # reads catalogue/stations_gold_standard_final.parquet
```

### 4. Inspect the audit at the row level

```python
# High-confidence dock-based stations
clean = gs[(gs.station_type == "docked_bike") & (gs.audit_confidence == "high")]
print(len(clean))     # 5,402

# Operator-driven anomaly profile
gs.groupby("operator_name").agg(
    n=("uid", "size"),
    A3_rate=("flag_A3", "mean"),
    A7_rate=("flag_A7", "mean"),
).sort_values("n", ascending=False).head(10)
```

A complete companion notebook with 8 recipes is at
[`notebooks/catalogue_recipes.ipynb`](notebooks/catalogue_recipes.ipynb).

---

## Repository layout

```
gbfs-audit-catalogue/
├── catalogue/                  Production data (parquet + summary CSV)
├── audit_pipeline/             Standalone Python package
├── notebooks/                  Reproducible companion notebook
├── paper/                      LaTeX source + figures (CSI submission)
├── app/                        Streamlit dashboard (deployed to gbfs-audit.streamlit.app)
├── docs/                       GitHub Pages site (gbfs-audit-catalogue/index)
├── huggingface/                Dataset card + Hub publication instructions
├── requirements.txt            Runtime dependencies
├── Dockerfile                  Bit-exact reproduction environment
├── LICENSE                     MIT (code)
├── LICENSE-DATA                ODbL v1.0 (data)
└── CITATION.cff                Machine-readable citation
```

---

## The seven anomaly classes

| Class | Name | Signature | FR | Global |
|---|---|---|---|---|
| A1 | Out-of-domain inclusion | car-sharing labelled as BSS | 14 | 46 |
| A2 | Placeholder capacity | constant non-zero `c` on all stations | 3 | 48 |
| A3 | Structural over-capacity | conditional averaging on free-floating | 8 | 33 |
| A4 | Geospatial error | transposed coords or >3σ outliers | 3.8 % stns | 81 |
| A5 | Out-of-perimeter | system area >50,000 km² or overseas | 5 | 17 |
| A6 | Zero-capacity dock | ≥1 % stations declare `c = 0` | 0 | 14 |
| A7 | Null capacity field | ≥50 % stations declare `c = NaN` | 19 (FF) | 215 |

---

## 46-column schema

- **5 identifiers** — `uid`, `station_id`, `system_id`, `system_name`, `source`
- **5 spatial / admin** — `lat`, `lon`, `city`, `commune_name`, `code_commune`, `region_id`
- **4 station description** — `station_name`, `address`, `capacity`, `n_stations_system`
- **11 audit pipeline** — `station_type`, `capacity_raw`, `capacity_audited`, `flag_A1`…`flag_A7`, `operator_name`, `audit_confidence`, `fetched_at`
- **5 network geometry** — KNN distances, density within buffers
- **2 topography** — `elevation_m`, `topography_roughness_index`
- **2 cycling infrastructure** — `infra_cyclable_km`, `infra_cyclable_pct`
- **1 safety** — `baac_accidents_cyclistes`
- **2 multimodal access** — `gtfs_heavy_stops_300m`, `gtfs_stops_within_300m_pct`
- **5 socio-economic context** — `revenu_median_uc`, `gini_revenu`, `revenu_d1`, `ecart_interquar`, `part_menages_voit0`
- **1 modal share** — `part_velo_travail`

The machine-readable schema (JSON Schema, DCAT-AP, Frictionless Data Package, Croissant JSON-LD) ships with the Zenodo deposit.

---

## Reproduce the audit

```bash
git clone https://github.com/rohanfosse/gbfs-audit-catalogue.git
cd gbfs-audit-catalogue
pip install -r requirements.txt
python -c "from audit_pipeline import load_catalogue; print(load_catalogue().shape)"
```

For bit-exact reproduction in a container:

```bash
docker build -t gbfs-audit:1.0 .
docker run --rm gbfs-audit:1.0 \
  python -c "from audit_pipeline import load_catalogue; print(load_catalogue().shape)"
```

---

## Citation

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

---

## Licences

- **Data** (`catalogue/`, Zenodo deposit, Hugging Face dataset): Open Data Commons Open Database License (ODbL) v1.0 — share-alike, attribution required.
- **Code** (`audit_pipeline/`, `app/`, `notebooks/`, `paper/`): MIT.

---

## Contact

Rohan Fossé — `rfosse@cesi.fr` — CESI LINEACT, Montpellier, France.

Issues and contributions: <https://github.com/rohanfosse/gbfs-audit-catalogue/issues>.

This repository is the focused publication of one paper in a larger research programme on French micromobility data quality. The broader programme (IMD composite indicator, IES equity diagnostic, urban-scale extensions) lives at <https://github.com/rohanfosse/bikeshare-data-explorer>.
