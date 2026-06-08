# Cascade Annotation Protocol (Campaign v2) — Pre-Registration

**Purpose**: Re-run the human construct-validity check with a **conditional
binary decision-tree** instrument instead of the four parallel interpretive
questions of campaign v1, to obtain inter-rater agreement that is defensible
at the node level and a per-rule ground truth with tight confidence
intervals.

**Protocol version**: cascade v2.0 (2026-06-08)

**Status**: PRE-REGISTRATION. This document, the codebook, the frozen sample
(`sample.csv` + its SHA-256), and the unmodified analysis scripts
(`sample_extractor.py`, `compute_reliability.py`) are to be timestamped on
Zenodo/OSF **before** any label is recorded. No change to the tree, the
codebook, the strata, or the predicates is permitted after the freeze; any
post-freeze change is reported as a separate exploratory analysis.

## 1. Why v2

Campaign v1 (`experiments/annotation/`) asked four parallel factual questions
of every station and reached:

| v1 question | Cohen's kappa | Verdict |
|---|---|---|
| Q1 — is a bike-share system? | 0.70 | concrete, documentary — held |
| Q2 — capacity physical? | **0.17** | interpretive + asked off-context — collapsed |
| Q3 — infrastructure on the ground? | 0.62 | observable — held |
| Q4 — coherent network position? | **0.13** | subjective — collapsed |

Two failure modes are visible. (i) **Off-context questions**: "is the capacity
physical?" is undefined on a free-floating station (no dock to count), yet v1
posed it to all strata. (ii) **Interpretive phrasing**: "coherent network
position" admits no shared operational criterion. v2 fixes both: every
question is a forced binary with an explicit evidential criterion, and a
question is only ever posed once the path makes it meaningful.

This is **not** a new gold standard — both annotators remain the paper's
authors (Section 7). v2 is an *instrument-quality* upgrade to the same
internal construct-validity check, made credible by pre-registration rather
than by independence.

## 2. The instrument: two conditional binary modules

Each station is evaluated by two modules. Module 2 runs only if Module 1 did
not terminate at A1. Each node is a forced **yes / no**, plus an explicit
**indéterminé** escape that routes the station to an INDETERMINATE bucket
(recorded, excluded from yes/no agreement, reported as a rate).

### Module 1 — Identity & type (mutually exclusive leaves)

```
M1.Q1  Operator is a bike/scooter shared-mobility service (not car-share)?
       NO  -> LEAF A1 (out-of-domain)                       [stop M1 and M2]
       YES -> M1.Q2
M1.Q2  At the coordinates (+/-25 m), is a fixed docking station visible
       (terminal, anchor points, or a branded painted bay)?
       YES -> M1.Q3
       NO  -> M1.Q4
M1.Q3  Does the visible dock count fall within +/-50% of declared capacity?
       YES -> LEAF DOCK-VALID
       NO  -> LEAF A2 (capacity anomaly)
M1.Q4  Is the declared capacity >= 4 (virtual anchor presented as multi-dock)?
       YES -> LEAF A3 (structural over-capacity)
       NO  -> LEAF FLOAT-VALID
```

### Module 2 — Geospatial coherence (independent axis; run if M1 != A1)

```
M2.Q1  Are the coordinates on land, inside the declared country/metro area?
       NO  -> LEAF A5 (out-of-perimeter)                    [stop M2]
       YES -> M2.Q2
M2.Q2  With sibling stations of the same operator displayed, does the station
       sit within/adjacent to the network footprint (not isolated in an
       implausible spot)?
       YES -> geospatially coherent
       NO  -> LEAF A4 (geospatial outlier)
```

### Terminal classification

A station's full label is the pair `(M1 leaf, M2 leaf)`. Examples:
`(A1, —)`, `(DOCK-VALID, coherent)`, `(A3, A4)`, `(FLOAT-VALID, A5)`. The
classes are not mutually exclusive across modules by construction; this is
the design intent, not a defect.

## 3. Codebook (frozen)

Each node has one criterion and a tie-break rule. Worked examples are
maintained in `codebook_examples.md` (3 positive / 3 negative per node),
filled during calibration (Section 5) and frozen with this document.

| Node | YES iff | NO iff | indéterminé iff | Tie-break |
|---|---|---|---|---|
| M1.Q1 | operator listed as bike/scooter share on its site or the national registry | operator is car-share (e.g. Citiz) or non-mobility | operator unidentifiable from coords + brand | default to YES only if a bike/scooter brand is confirmed; else indéterminé |
| M1.Q2 | a fixed terminal / anchor rack / branded painted bay is visible in satellite **or** street view within 25 m | clearly no fixed hardware (free-floating drop zone, bare sidewalk) | imagery older than 24 mo, occluded, or absent | require the hardware to be visible in at least one source; ambiguous shadows -> indéterminé |
| M1.Q3 | visible dock slots are within +/-50% of declared capacity | count is outside +/-50% **or** capacity is a round placeholder (10/20/50/100) with a visibly different rack | docks not countable from imagery | if rack present but uncountable -> indéterminé, not NO |
| M1.Q4 | declared capacity >= 4 | declared capacity in {1,2,3} | capacity NaN/0 (route to A7/A6 system-level, mark indéterminé here) | strictly numeric threshold; no judgement |
| M2.Q1 | point on land within the declared country and plausibly within the metro service area | point in water, in a field far from any town, or in the wrong country | borderline coastal/admin edge | use the operator's declared service-area bbox as the reference |
| M2.Q2 | within the convex hull of sibling stations **or** <= 1 km from the nearest sibling | isolated by > 1 km from every sibling **and** outside the built-up footprint | siblings not loadable for this operator | the 1 km / hull rule is the criterion; "feels off" is not sufficient |

Imagery sources, in priority order: CyclOSM / OSM base map with an Overpass
overlay of `amenity=bicycle_rental`; Google/IGN satellite; Google Street View;
operator site. The sibling-station overlay for M2.Q2 is pre-rendered per
station in the annotation interface.

## 4. Sampling (frozen sample, n ≈ 570)

Stratified random sampling from the 46,307-station certified catalogue,
**stratified by the route the pipeline predicts** so that every tree node
receives >= 50 dual-rated stations despite conditional thinning. Stations are
deduplicated across strata and the final order is shuffled (SEED = 42).

| Stratum (predicted route) | Selection | N | Nodes it exercises |
|---|---|---|---|
| clean_docked | no flag, confidence high, docked | 70 | M1.Q1/Q2/Q3 YES path, M2 |
| clean_freefloating *(new)* | free-floating, capacity in {1,2,3}, no A3 | 60 | M1.Q2 NO, M1.Q4 NO (negative control) |
| A1_carsharing | flag_A1 | 60 | M1.Q1 NO |
| A2_placeholder | flag_A2 (pool-capped, 1 operator) | 40 | M1.Q3 NO |
| A3_freefloating | flag_A3 & !flag_A2 | 70 | M1.Q2 NO, M1.Q4 YES |
| A4_agree_flag | both detectors flag | 40 | M2.Q2 |
| A4_discordant_legacy | legacy centroid only | 60 | M2.Q2 (core: confirm legacy FP) |
| A4_discordant_composite | composite only | 60 | M2.Q2 (core: real new outliers?) |
| A5_out_of_perimeter | flag_A5 | 40 | M2.Q1 NO |
| A6_zero_capacity | flag_A6 (empty in v1.0) | 10 | M1.Q2 NO on docked-declared |
| A7_null_capacity | flag_A7 & !flag_A3 (pool-capped) | 30 | M1.Q4 indéterminé (system-level) |
| A3_boundary | system capacity ratio in [2,5] (empty in v1.0) | 20 | M1.Q3 / M1.Q4 frontier |

Predicted-node traffic (lower bounds, assuming no upstream routing
disagreement): M1.Q1 = 570; M1.Q2 ~= 510 (all but A1); M1.Q3 ~= 130
(clean_docked + A2 + A6); M1.Q4 ~= 250 (A3 + clean_ff + boundary); M2.Q1 ~=
510; M2.Q2 ~= 200 (A4 strata + clean). Every node clears 50 except the
known-empty v1.0 strata (A6, A3_boundary), documented as untestable.

**Pool-capped / mono-operator strata** (A2 = one operator, A7 = one
operator) measure that operator's data quality, not the rule's general
validity; this limitation is restated in the manuscript exactly as in v1.

## 5. Procedure

**Phase 0 — Calibration (excluded from all statistics).** Both annotators
jointly label 24 calibration stations (2 per stratum family), fill the
`codebook_examples.md` worked examples, reconcile every disagreement, and
**lock** the codebook. Calibration happens *before* the pre-registration
freeze; the locked codebook is part of the frozen artefact.

**Phase 1 — Independent blind annotation.** Each annotator runs both modules
on every station, blind to (i) the pipeline output (A1–A7 flags hidden behind
an opt-in panel that stays closed) and (ii) the co-annotator's labels. No
stratum name is shown. Each node answer is logged with the **evidence**
(imagery source + date + one-line observation) so the verdict is auditable
and releasable — this evidence log partially substitutes for the missing
external annotator (Section 7).

**Phase 2 — Adjudication by pre-registered rule (not discretion).** Because
no third independent adjudicator is available, disagreements are resolved by a
**deterministic** procedure fixed here:
1. Re-fetch the imagery for the contested node and re-apply the codebook
   criterion jointly.
2. If the codebook criterion resolves it, that is the gold value.
3. If it does not (genuinely ambiguous evidence), the node is marked
   **INDETERMINATE** — never forced to a majority.
All raw per-annotator labels and the adjudication trace are released so
readers can recompute every number independently.

## 6. Analysis plan (frozen)

Run `compute_reliability.py` unmodified on the two label files.

**Primary endpoint.** Krippendorff's alpha (nominal) on the **terminal Module-1
leaf** and on the **terminal Module-2 leaf**, full n, INDETERMINATE as its own
category. Pre-registered success target: alpha >= 0.70 on each (vs the 0.17 /
0.13 of v1's interpretive questions).

**Per-node agreement.** Cohen's kappa + Krippendorff's alpha computed among
the stations **both annotators routed into that node** (co-routed set); n_node
reported alongside. A node below alpha = 0.60 is flagged as an instrument
weakness in the manuscript (the codebook is NOT changed post-freeze).

**Routing-disagreement audit.** For each station, the *first* node at which the
two annotators diverge is recorded; the divergence count per node localises
where residual ambiguity lives (expected: the A1/A3 frontier, as in v1).

**Per-rule precision/recall**, derived *a posteriori* from adjudicated node
answers (never from a pipeline-referencing verdict), with Wilson 95% CIs:

| Rule | "anomaly is real" iff | Level |
|---|---|---|
| A1 | M1.Q1 = no | per-station |
| A2 | M1.Q3 = no | per-station (system-level caveat) |
| A3 | M1.Q2 = no | per-station |
| A4 | M2.Q2 = no | per-station |
| A5 | M2.Q1 = no | per-station |
| A6 | M1.Q2 = no (docked-declared) | per-station |
| A7 | — | system-level only |

**A4 ablation endpoint.** On the `A4_discordant_legacy` stratum, the
false-positive rate of the legacy centroid = share judged geospatially
coherent (M2.Q2 = yes). This is the direct successor to v1's "are the 8,005
discordant stations true FP?" number.

**QA.** Per-station time recorded; < 10 s flagged. First-half vs second-half
agreement computed per annotator (fatigue/drift). Evidence-log completeness
checked (every non-indéterminé node must cite a source).

## 7. Honest limitations (restated for the manuscript)

- **No external annotator.** Both annotators are authors; v2 is a construct-
  validity check, not independent ground truth. Mitigations: pre-registration
  freeze, locked codebook with worked examples, blinding to pipeline and to
  each other, deterministic adjudication rule, full release of raw labels and
  the per-node evidence log. An external multi-institution annotation remains
  future work.
- **Shared prior.** Two authors of the same paper may share systematic blind
  spots a locked codebook cannot remove; the evidence log is the only external
  check on this and is released for third-party audit.
- **Mono-operator strata** (A2, A7) reflect one operator's data quality.
- **Imagery currency.** Satellite/street-view lag can mislabel recently
  changed stations; routed to indéterminé, rate reported.

## 8. Output files

- `PROTOCOL.md` — this pre-registration
- `codebook_examples.md` — worked examples per node (filled at calibration, frozen)
- `sample.csv` — frozen stratified sample (+ `sample.sha256`)
- `labels_<annotator>.csv` — per-annotator node answers + evidence log
- `gold_labels.csv` — adjudicated node answers + terminal leaves
- `reliability_report.json` — per-node alpha/kappa, terminal-leaf alpha,
  routing-disagreement audit, per-rule P/R, A4 FP rate
