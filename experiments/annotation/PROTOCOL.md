# Human Annotation Protocol for Ground-Truth Validation

**Purpose**: Establish a human-annotated ground truth for a stratified
sample of 200 stations to compute precision, recall and F1 of the A1–A7
audit rules and the A4v2 composite detector.

## Sampling strategy

| Stratum | Selection criterion | N | Rationale |
|---|---|---|---|
| Clean dock-based | No flag, confidence = high | 30 | False-negative check |
| A1 (carsharing) | flag_A1 = True | 20 | Is the vehicle a bicycle? |
| A2 (placeholder) | flag_A2 = True | 15 | Is capacity truly constant? |
| A3 (free-floating) | flag_A3 = True | 25 | Physical dock or virtual anchor? |
| A4 AGREE_FLAG | Both detectors flag | 20 | Algorithmic consensus |
| A4 DISCORDANT_LEGACY | Legacy centroid only | 30 | Key stratum: are these true FP? |
| A4 DISCORDANT_COMPOSITE | Composite only | 15 | Does composite find real outliers? |
| A6 (zero-capacity) | flag_A6 = True | 10 | Does a 0-dock station exist? |
| A7 (NaN capacity) | flag_A7 = True | 20 | Trivial verification |
| A3 boundary | capacity_ratio in [2, 5] | 15 | Threshold sensitivity zone |
| **Total** | | **200** | |

## Annotation interface

Each annotator receives per station:
- Raw `station_information` JSON record
- GPS coordinates rendered on an interactive map (OSM tiles)
- Satellite / Street View imagery of the location
- Most recent `station_status` snapshot (if available)
- Operator metadata (fleet type, brand, country)

## Questions (per station)

```
Q1. Does this station represent a bike-sharing system?
    [ yes / no / indeterminate ]
    → Validates A1

Q2. Does the declared capacity reflect a physical dock count?
    [ yes / no / NaN / indeterminate ]
    → Validates A2, A3, A6, A7

Q3. Does this station physically exist at the declared coordinates?
    (satellite / Street View verification)
    [ yes / no / indeterminate ]
    → Validates A4

Q4. Are these coordinates within the reasonable operating perimeter?
    [ yes / no ]
    → Validates A4, A5

Q5. Overall verdict:
    [ clean / anomaly confirmed / pipeline false positive / indeterminate ]
```

## Annotators

- Minimum 2 independent annotators (blind to each other's labels)
- Annotator 1: domain expert (urban mobility researcher)
- Annotator 2: data engineer (familiar with GBFS but not with this audit)
- Disagreements resolved by a third adjudicator

## Inter-rater reliability

- Cohen's kappa on Q5 (4-class) and on each Q1–Q4 (binary)
- Target: kappa >= 0.70 (substantial agreement)
- If kappa < 0.60 on any question, revise the annotation guide

## Metrics to report

For each rule Ai and for the A4v2 composite detector:
- **Precision** = TP / (TP + FP) — "when the pipeline flags, is it right?"
- **Recall** = TP / (TP + FN) — "when there's an anomaly, does the pipeline catch it?"
- **F1** = harmonic mean
- **Wilson 95% CI** on each metric (small-sample correction)

For the A4 ablation specifically:
- Precision of legacy centroid on the DISCORDANT_LEGACY stratum
- Precision of composite on the DISCORDANT_COMPOSITE stratum
- This directly answers "are the 8,005 discordant stations true FP?"

## Practical timeline

| Phase | Duration | Output |
|---|---|---|
| Sample extraction + interface setup | 1 day | 200 station annotation cards |
| Annotator 1 pass | 2 days | 200 labels |
| Annotator 2 pass | 2 days | 200 labels |
| Adjudication + kappa computation | 1 day | Gold labels + reliability report |
| Metrics computation + manuscript update | 1 day | Precision/recall table for paper |
| **Total** | **~7 days** | |

## Output files

- `experiments/annotation/sample_200.csv` — the stratified sample
- `experiments/annotation/labels_annotator1.csv`
- `experiments/annotation/labels_annotator2.csv`
- `experiments/annotation/gold_labels.csv` — adjudicated consensus
- `experiments/annotation/reliability_report.json` — kappa scores
- `experiments/annotation/precision_recall.csv` — per-rule metrics
