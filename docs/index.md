---
layout: default
title: GBFS Audit Catalogue
description: A reproducible audit of 1,509 open bike-sharing feeds across 48 countries.
---

<div class="badges" markdown="0">
<a href="https://doi.org/10.5281/zenodo.20125460"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.20125460.svg" alt="DOI"></a>
<a href="https://huggingface.co/datasets/rohanfosse/gbfs-audit-catalogue"><img src="https://img.shields.io/badge/Hugging%20Face-Datasets-yellow" alt="Hugging Face"></a>
<a href="https://gbfs-audit.streamlit.app"><img src="https://img.shields.io/badge/Streamlit-Live%20demo-red" alt="Streamlit"></a>
<a href="https://github.com/cycling-data-lab/gbfs-audit-catalogue/actions/workflows/tests.yml"><img src="https://github.com/cycling-data-lab/gbfs-audit-catalogue/actions/workflows/tests.yml/badge.svg" alt="tests"></a>
<img src="https://img.shields.io/badge/data-ODbL%20v1.0-blue" alt="Data: ODbL">
<img src="https://img.shields.io/badge/code-MIT-green" alt="Code: MIT">
</div>

GBFS guarantees that bike-sharing feeds are **syntactically** consistent — not
that they are **semantically** comparable. This project audits 1,509 feeds
across 48 countries, distils a unified taxonomy of **seven data-quality
classes**, and releases a certified, anomaly-flagged reference dataset of
**46,307 French stations** so downstream consumers can filter without
re-running the pipeline.

<div class="cta" markdown="0">
<a class="primary" href="https://gbfs-audit.streamlit.app">Explore the dashboard</a>
<a href="https://github.com/cycling-data-lab/gbfs-audit-catalogue">Source &amp; pipeline</a>
<a href="https://huggingface.co/datasets/rohanfosse/gbfs-audit-catalogue">Download the dataset</a>
<a href="https://doi.org/10.5281/zenodo.20125460">Zenodo DOI</a>
</div>

<div class="stats" markdown="0">
  <div class="stat"><span class="num">46,307</span><span class="lbl">certified stations</span></div>
  <div class="stat"><span class="num">123</span><span class="lbl">French operators</span></div>
  <div class="stat"><span class="num">1,509</span><span class="lbl">systems audited</span></div>
  <div class="stat"><span class="num">48</span><span class="lbl">countries</span></div>
  <div class="stat"><span class="num">7</span><span class="lbl">anomaly classes</span></div>
  <div class="stat"><span class="num">30.9%</span><span class="lbl">stations removed</span></div>
</div>

<figure markdown="0">
  <img src="{{ '/assets/img/visual-abstract.png' | relative_url }}" alt="Visual abstract: from raw GBFS feeds to a certified, anomaly-flagged catalogue">
  <figcaption>From raw GBFS feeds to a certified, anomaly-flagged catalogue: a nine-step idempotent purging protocol screens every feed against seven data-quality classes.</figcaption>
</figure>

## The seven data-quality classes

Five **structural errors** (A1–A5) that violate the implicit semantic contract
of the GBFS field they populate, plus two **semantic warnings** (A6–A7) for
spec-compliant publication patterns whose downstream interpretation is
nevertheless ambiguous.

<div class="tax" markdown="0">
  <div class="cls"><span class="kind">structural</span><div><span class="code">A1</span><span class="nm">Out-of-domain inclusion</span></div><div class="sig">Car-sharing advertised as a bike-sharing system.</div></div>
  <div class="cls"><span class="kind">structural</span><div><span class="code">A2</span><span class="nm">Placeholder capacity</span></div><div class="sig">Constant non-zero capacity across every station of a system.</div></div>
  <div class="cls"><span class="kind">structural</span><div><span class="code">A3</span><span class="nm">Structural over-capacity</span></div><div class="sig">Conditional averaging on free-floating fleet anchors.</div></div>
  <div class="cls"><span class="kind">structural</span><div><span class="code">A4</span><span class="nm">Geospatial outlier</span></div><div class="sig">Transposed coordinates or stations far from the network (topology-aware).</div></div>
  <div class="cls"><span class="kind">structural</span><div><span class="code">A5</span><span class="nm">Out-of-perimeter</span></div><div class="sig">System bounding box &gt; 50,000 km² or out-of-jurisdiction stations.</div></div>
  <div class="cls warn"><span class="kind">warning</span><div><span class="code">A6</span><span class="nm">Zero-capacity dock</span></div><div class="sig">At least 1 % of stations declare capacity = 0.</div></div>
  <div class="cls warn"><span class="kind">warning</span><div><span class="code">A7</span><span class="nm">Null capacity field</span></div><div class="sig">At least 50 % of stations declare capacity = NaN.</div></div>
</div>

## Why it matters: the Bordeaux case

The most extreme case in the French corpus is **Pony Bordeaux**: 2,996 entries
each declaring 12 docks (a nominal 35,952 docks), while the actual mean
capacity per entry is **0.03 bike/entry**. After A3 reclassification,
Bordeaux's dock-based count collapses from 9,921 raw entries to **225**
certified stations — a 98 % collapse, equivalent to a ×52 over-count on any
supply-side metric built on the unaudited feed.

<figure markdown="0">
  <img src="{{ '/assets/img/bordeaux-before-after.png' | relative_url }}" alt="Bordeaux dock-based stations before and after the audit">
  <figcaption>Bordeaux before / after the audit: free-floating anchors published as docks are reclassified, removing a ×52 supply-side over-count.</figcaption>
</figure>

## Quick start

```python
from datasets import load_dataset
gs = load_dataset("rohanfosse/gbfs-audit-catalogue", split="train").to_pandas()

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

No-auth alternative, straight from Zenodo:

```python
import pandas as pd
gs = pd.read_parquet(
    "https://zenodo.org/records/20125460/files/stations_gold_standard_final.parquet"
)
```

<figure markdown="0">
  <img src="{{ '/assets/img/audit-status.png' | relative_url }}" alt="Audit status breakdown across the French corpus">
  <figcaption>Audit verdict across the French corpus: 30.9 % of raw stations removed and a further 61 % relabelled.</figcaption>
</figure>

## Resources

| Resource | Where |
|---|---|
| **Interactive dashboard** | [gbfs-audit.streamlit.app](https://gbfs-audit.streamlit.app) |
| **Dataset (Hugging Face)** | [rohanfosse/gbfs-audit-catalogue](https://huggingface.co/datasets/rohanfosse/gbfs-audit-catalogue) |
| **Zenodo deposit (DOI)** | [10.5281/zenodo.20125460](https://doi.org/10.5281/zenodo.20125460) |
| **Source & audit pipeline** | [github.com/cycling-data-lab/gbfs-audit-catalogue](https://github.com/cycling-data-lab/gbfs-audit-catalogue) |
| **Reproducible recipes** | [notebooks/catalogue_recipes.ipynb](https://github.com/cycling-data-lab/gbfs-audit-catalogue/blob/main/notebooks/catalogue_recipes.ipynb) |
| **Human-validation protocol** | [experiments/annotation/PROTOCOL.md](https://github.com/cycling-data-lab/gbfs-audit-catalogue/blob/main/experiments/annotation/PROTOCOL.md) |
| **Paper (CSI 2026)** | Manuscript in preparation; preprint forthcoming |

## Schema — 46 columns at a glance

- **5 identifiers** — `uid`, `station_id`, `system_id`, `system_name`, `source`
- **6 spatial / admin** — `lat`, `lon`, `city`, `commune_name`, `code_commune`, `region_id`
- **4 station description** — `station_name`, `address`, `capacity`, `n_stations_system`
- **13 audit pipeline** — `station_type`, `capacity_raw`, `capacity_audited`, `flag_A1`–`flag_A7`, `operator_name`, `audit_confidence`, `fetched_at`
- **5 network geometry** — KNN distances and density within buffers
- **2 topography** — `elevation_m`, `topography_roughness_index`
- **2 cycling infrastructure** — `infra_cyclable_km`, `infra_cyclable_pct`
- **1 safety** — `baac_accidents_cyclistes`
- **2 multimodal access** — `gtfs_heavy_stops_300m`, `gtfs_stops_within_300m_pct`
- **5 socio-economic context** — `revenu_median_uc`, `gini_revenu`, `revenu_d1`, `ecart_interquar`, `part_menages_voit0`
- **1 modal share** — `part_velo_travail`

<div class="note" markdown="1">
**FAIR by design.** The catalogue ships with machine-readable descriptors —
a [JSON Schema](https://github.com/cycling-data-lab/gbfs-audit-catalogue/blob/main/catalogue/metadata/schema.json),
a [Frictionless Data Package](https://github.com/cycling-data-lab/gbfs-audit-catalogue/blob/main/catalogue/metadata/datapackage.json),
a [DCAT-AP record](https://github.com/cycling-data-lab/gbfs-audit-catalogue/blob/main/catalogue/metadata/dcat-ap.jsonld)
and a [Croissant manifest](https://github.com/cycling-data-lab/gbfs-audit-catalogue/blob/main/catalogue/metadata/croissant.jsonld) —
plus a Docker image and a 36-test CI suite for byte-level reproducibility.
</div>

## Citation

{% raw %}
```bibtex
@article{Fosse2026gbfs,
  author  = {Foss\'e, Rohan and Pallares, Ga\"el},
  title   = {Auditing GBFS bike-sharing feeds at country and global scale:
             A reproducible anomaly taxonomy for open mobility data},
  journal = {Computer Standards \& Interfaces},
  year    = {2026},
  note    = {Manuscript in preparation; preprint forthcoming}
}

@dataset{Fosse2026gbfsdata,
  author    = {Foss\'e, Rohan and Pallares, Ga\"el},
  title     = {{GBFS Audit Catalogue} v1.0},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.20125460}
}
```
{% endraw %}

## Licence & contact

**Data** under [ODbL v1.0](https://opendatacommons.org/licenses/odbl/1-0/) ·
**Code** under [MIT](https://opensource.org/licenses/MIT).

**Rohan Fossé** (lead contact) · `rfosse@cesi.fr` · CESI École d'Ingénieurs, Montpellier, France.
**Gaël Pallares** · CESI LINEACT (EA 7527), Montpellier, France.

Issues and contributions on [GitHub](https://github.com/cycling-data-lab/gbfs-audit-catalogue/issues).
