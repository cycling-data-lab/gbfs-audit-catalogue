---
layout: default
title: GBFS Audit Catalogue
description: A reproducible audit of 1,509 open bike-sharing feeds across 48 countries.
---

**A reproducible audit of 1,509 open bike-sharing feeds across 48 countries.**

The General Bikeshare Feed Specification (GBFS) is the open standard that municipal bike-sharing operators publish on national open-data portals. The standard guarantees syntactic interoperability — but not semantic consistency. The audit reported here exposes a unified data-quality taxonomy of seven classes — **five structural errors (A1–A5)** plus **two semantic warnings (A6–A7)** for spec-compliant patterns that nevertheless make a column non-aggregable — and **removes 30.9 %** of the raw French stations from the catalogue while relabelling a further 61 %.

The result is the **GBFS Audit Catalogue v1.0.1**, a 46-column reference dataset for 46,307 certified stations across 123 French operators, with per-row flags and contextual enrichment from INSEE, BAAC, BD TOPO, BD ALTI and the national GTFS aggregator.

---

## Quick start

### Load via Hugging Face Datasets

```python
from datasets import load_dataset
gs = load_dataset("rohanfosse/gbfs-audit-catalogue", split="train").to_pandas()
```

### Load via Zenodo (no auth)

```python
import pandas as pd
gs = pd.read_parquet(
    "https://zenodo.org/records/20125460/files/stations_gold_standard_final.parquet"
)
```

### Inspect the audit

```python
# High-confidence dock-based stations
clean = gs[(gs.station_type == "docked_bike") & (gs.audit_confidence == "high")]
print(len(clean))  # 4,721

# Operator-driven flag hotspots
gs.groupby("operator_name").agg(
    n=("uid", "size"),
    A3_rate=("flag_A3", "mean"),
    A7_rate=("flag_A7", "mean"),
).sort_values("n", ascending=False).head(10)
```

---

## Resources

| Resource | URL |
|---|---|
| **Paper (CSI 2026)** | Manuscript under peer review; preprint forthcoming |
| **Zenodo deposit (DOI)** | [10.5281/zenodo.20125460](https://doi.org/10.5281/zenodo.20125460) |
| **Hugging Face Datasets** | [rohanfosse/gbfs-audit-catalogue](https://huggingface.co/datasets/rohanfosse/gbfs-audit-catalogue) |
| **Interactive dashboard** | [gbfs-audit.streamlit.app](https://gbfs-audit.streamlit.app) |
| **Source code & audit pipeline** | [github.com/cycling-data-lab/gbfs-audit-catalogue](https://github.com/cycling-data-lab/gbfs-audit-catalogue) |
| **Companion notebook (8 recipes)** | [notebooks/catalogue_recipes.ipynb](https://github.com/cycling-data-lab/gbfs-audit-catalogue/blob/main/notebooks/catalogue_recipes.ipynb) |

---

## The seven data-quality classes

Five **structural errors** (A1–A5) plus two **semantic warnings** (A6–A7) for spec-compliant publication patterns whose downstream-consumer interpretation is ambiguous.

| Class | Type | Name | Signature | FR | Global |
|---|---|---|---|---|---|
| A1 | structural | Out-of-domain inclusion | car-sharing advertised as BSS | 17 | 46 |
| A2 | structural | Placeholder capacity | constant non-zero `c` across docked subset | 1 | 48 |
| A3 | structural | Structural over-capacity | conditional averaging on free-floating | 41 | 33 |
| A4 | structural | Geospatial outlier | 3-σ on per-system nearest-neighbour distance | 78 (1.1 % stns) | 81 |
| A5 | structural | Out-of-perimeter | system bbox > 50,000 km² | 4 | 17 |
| A6 | warning | Zero-capacity dock | ≥ 1 % docked stations with `c = 0` | 0 | 14 |
| A7 | warning | Null capacity field | ≥ 50 % stations with `c = NaN` | 32 (FF) | 215 |

---

## Schema (46 columns at a glance)

- **5 identifiers** — `uid`, `station_id`, `system_id`, `system_name`, `source`
- **5 spatial / admin** — `lat`, `lon`, `city`, `commune_name`, `code_commune`, `region_id`
- **4 station description** — `station_name`, `address`, `capacity`, `n_stations_system`
- **11 audit pipeline** — `station_type`, `capacity_raw`, `capacity_audited`, `flag_A1`–`flag_A7`, `operator_name`, `audit_confidence`, `fetched_at`
- **5 network geometry** — KNN distances, density within buffers
- **2 topography** — `elevation_m`, `topography_roughness_index`
- **2 cycling infrastructure** — `infra_cyclable_km`, `infra_cyclable_pct`
- **1 safety** — `baac_accidents_cyclistes`
- **2 multimodal access** — `gtfs_heavy_stops_300m`, `gtfs_stops_within_300m_pct`
- **5 socio-economic context** — `revenu_median_uc`, `gini_revenu`, `revenu_d1`, `ecart_interquar`, `part_menages_voit0`
- **1 modal share** — `part_velo_travail`

The full machine-readable schema ships as a JSON Schema, a Frictionless Data Package descriptor, a DCAT-AP record and a Croissant manifest in the Zenodo deposit.

---

## Citation

```bibtex
@article{Fosse2026gbfs,
  author  = {Foss\'e, Rohan and Pallares, Ga\"el},
  title   = {Auditing GBFS bike-sharing feeds at country and global scale:
             A reproducible anomaly taxonomy for open mobility data},
  journal = {Computer Standards \& Interfaces},
  year    = {2026},
  note    = {Manuscript under peer review; preprint forthcoming}
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

## Licence

- **Data**: Open Data Commons Open Database License (ODbL) v1.0
- **Code**: MIT

## Contact

**Rohan Fossé** (lead contact)  ·  `rfosse@cesi.fr`  ·  CESI École d'Ingénieurs, Montpellier, France.

**Gaël Pallares**  ·  CESI LINEACT (EA 7527), Montpellier, France.

Issues and contributions on [GitHub](https://github.com/cycling-data-lab/gbfs-audit-catalogue/issues).
