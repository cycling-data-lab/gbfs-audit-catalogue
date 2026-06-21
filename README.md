# GBFS Audit Catalogue

> A certified, anomaly-flagged reference dataset for 46,307 bike-sharing
> stations across 123 French operators, with the open-source pipeline that
> produced it.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20125460.svg)](https://doi.org/10.5281/zenodo.20125460)
[![tests](https://github.com/cycling-data-lab/gbfs-audit-catalogue/actions/workflows/tests.yml/badge.svg)](https://github.com/cycling-data-lab/gbfs-audit-catalogue/actions/workflows/tests.yml)
[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Datasets-yellow)](https://huggingface.co/datasets/rohanfosse/gbfs-audit-catalogue)
[![Streamlit](https://img.shields.io/badge/Streamlit-Live%20demo-red)](https://gbfs-audit.streamlit.app)
[![Docs](https://img.shields.io/badge/Docs-Project%20page-lightgrey)](https://cycling-data-lab.github.io/gbfs-audit-catalogue)
[![Data: ODbL](https://img.shields.io/badge/data-ODbL%20v1.0-blue)](LICENSE-DATA)
[![Code: MIT](https://img.shields.io/badge/code-MIT-green)](LICENSE)

## What this is

GBFS guarantees that bike-sharing feeds are syntactically consistent — not
that they are semantically comparable. An audit of 1,509 systems across
48 countries surfaces a unified taxonomy of seven data-quality classes
(five structural errors + two semantic warnings) that remove **30.9 %** of
the raw French stations and relabel a further **61 %**. The released
catalogue exposes the verdict per row, so downstream consumers can filter
without rerunning the pipeline.

The methodology is validated by three experiments:

- **A4 v2 (topology-aware detector)** — HDBSCAN + spectral graph analysis
  replaces the naive centroid heuristic; an ablation on 46,307 stations
  eliminates 8,005 discordant legacy flags on anisotropic networks.
- **LOOO cross-validation** — leave-one-operator-out on 7 operators
  confirms rule stability across publishers; clean dock-based operators
  (Vélib', Vélo&Co) show 0 % flag rate on all rules except residual
  GPS noise on A4.
- **Dynamic audit protocol** — a Shannon-entropy zombie detector for
  `station_status` ships as a ready-to-run pipeline for follow-up work.

## Quick start

```python
from datasets import load_dataset
gs = load_dataset("rohanfosse/gbfs-audit-catalogue", split="train").to_pandas()

# High-confidence dock-based stations (4,721)
clean = gs[(gs.station_type == "docked_bike") & (gs.audit_confidence == "high")]
```

The 46-column schema, the seven-class taxonomy and eight reproducible
recipes (anomaly filtering, INSEE join, Bordeaux before/after, etc.) are
documented on the [**project page**](https://cycling-data-lab.github.io/gbfs-audit-catalogue)
and the [**dataset card**](https://huggingface.co/datasets/rohanfosse/gbfs-audit-catalogue).

## Running the experiments

```bash
pip install -e ".[experiments]"

# XP2 (spatial topology ablation) + XP3 (LOOO cross-validation)
python -m experiments.run_all \
    --catalogue catalogue/stations_gold_standard_final.parquet \
    --output results/

# XP1 (dynamic audit — requires 14-day station_status collection)
python -m experiments.xp1_dynamic_audit.run_xp1 collect \
    --feeds feeds.csv --output data/xp1/ --days 14
```

A reviewer-oriented demo notebook is available at
[`notebooks/xp_reviewer_demo.ipynb`](notebooks/xp_reviewer_demo.ipynb).

## Repository structure

```text
audit_pipeline/          Core audit logic (enrich, A1–A7 flags, Tier-2 geometry)
experiments/
├── xp1_dynamic_audit/   Shannon-entropy zombie detector (collector + classifier)
├── xp2_spatial_topology/ HDBSCAN + spectral graph ablation vs. legacy centroid
├── xp3_looo_validation/ Leave-one-operator-out CV with bootstrap CI
├── annotation/          Human ground-truth validation (stratified sample,
│                        Streamlit annotator, inter-rater reliability)
├── e1_holdout/          Retrospective hold-out (12-month MobilityData diff)
├── e2_threshold_sensitivity/  σ_max sweep, A3 KDE threshold, global panel
├── e5_europe/           Cross-country panel (13 systems, 6 technology stacks)
├── config/              Hyperparameters (defaults.yaml)
└── run_all.py           Orchestrator for XP2 + XP3
catalogue/               Certified parquet + per-system audit summary
├── metadata/            FAIR manifests (JSON Schema, Frictionless,
│                        DCAT-AP, Croissant) — generated, validated
scripts/                 Figure + metadata generators
paper/                   Manuscript LaTeX source + 10 figures
notebooks/               8 reproducible recipes + reviewer demo
app/                     Streamlit dashboard (gbfs-audit.streamlit.app)
tests/                   36 tests, Python 3.10–3.12
```

## Learn more

| Resource | Where |
| --- | --- |
| Project page (long-form) | [cycling-data-lab.github.io/gbfs-audit-catalogue](https://cycling-data-lab.github.io/gbfs-audit-catalogue) |
| Dataset card + full schema | [huggingface.co/datasets/rohanfosse/gbfs-audit-catalogue](https://huggingface.co/datasets/rohanfosse/gbfs-audit-catalogue) |
| Live dashboard | [gbfs-audit.streamlit.app](https://gbfs-audit.streamlit.app) |
| Manuscript LaTeX source | [`paper/`](paper/) |
| Reproducible recipes | [`notebooks/catalogue_recipes.ipynb`](notebooks/catalogue_recipes.ipynb) |
| Experiment reproduction | [`notebooks/xp_reviewer_demo.ipynb`](notebooks/xp_reviewer_demo.ipynb) |
| Human validation protocol | [`experiments/annotation/PROTOCOL.md`](experiments/annotation/PROTOCOL.md) |
| FAIR manifests | [`catalogue/metadata/`](catalogue/metadata/) (JSON Schema · Frictionless · DCAT-AP · Croissant) |
| Docker reproduction | `docker build -t gbfs-audit:1.0 . && docker run --rm gbfs-audit:1.0` |
| Tests | `pytest` (36 tests, Python 3.10–3.12) |

## Citation

```bibtex
@article{Fosse2026gbfs,
  author  = {Foss\'e, Rohan and Pallares, Ga\"el},
  title   = {Auditing GBFS bike-sharing feeds at country and global scale:
             A reproducible anomaly taxonomy for open mobility data},
  journal = {Computer Standards \& Interfaces},
  year    = {2026},
  note    = {Manuscript in preparation}
}

@dataset{Fosse2026gbfsdata,
  author    = {Foss\'e, Rohan and Pallares, Ga\"el},
  title     = {{GBFS Audit Catalogue} v1.0},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.20125460}
}
```

A [`CITATION.cff`](CITATION.cff) is also provided for GitHub's citation tooling.

## Licences

Code under [MIT](LICENSE); data under [ODbL v1.0](LICENSE-DATA). Upstream
attributions for the contextual-enrichment sources (INSEE, IGN, ONISR,
GTFS aggregator) are listed in `LICENSE-DATA`.

## Contact

**Rohan Fossé** ([rfosse@cesi.fr](mailto:rfosse@cesi.fr)) — CESI École d'Ingénieurs, Montpellier.
**Gaël Pallares** — CESI LINEACT (EA 7527), Montpellier.

Issues and contributions are welcome on the
[issue tracker](https://github.com/cycling-data-lab/gbfs-audit-catalogue/issues);
see [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md).
