# Human-Validation Annotation Protocol (Campaign v2) - Pre-Registration

**Purpose.** Re-run the human construct-validity check of the GBFS audit with a
one-question-at-a-time decision-tree instrument, to obtain inter-rater
agreement that is defensible per node and a per-rule ground truth with honest
confidence intervals.

**Protocol version.** human-validation v2.1 (2026-06-08).

**Status: PRE-REGISTRATION.** This document, the locked codebook, the frozen
sample (`sample.csv` + its SHA-256), and the unmodified analysis scripts
(`sample_extractor.py`, `compute_reliability.py`) are timestamped on Zenodo/OSF
**before any label is recorded**. After the freeze, no change to the tree, the
codebook, the strata, the predicates or the analysis is permitted; any
post-freeze change is reported as a separate, clearly labelled exploratory
analysis.

## 1. Why v2, and the statistical lesson from v1

Campaign v1 asked four parallel factual questions of every station and two of
them collapsed:

| v1 question | Cohen's kappa | Verdict |
|---|---|---|
| is a bike-share system? | 0.70 | concrete, documentary - held |
| capacity physical? | **0.17** | interpretive, asked off-context - collapsed |
| infrastructure on the ground? | 0.62 | observable - held |
| coherent network position? | **0.13** | subjective - collapsed |

Two failure modes: off-context questions (capacity asked on dockless stations)
and interpretive phrasing with no shared criterion. v2 fixes both: one question
at a time, each with an explicit evidential criterion, posed only when the path
makes it meaningful.

A second lesson is statistical. Because the sample is stratified by the
pipeline's predicted class, several strata have an extreme class prevalence
(e.g. an A1 stratum that is almost entirely car-sharing). On such marginals,
Cohen's kappa and Krippendorff's alpha collapse even when raw agreement is near
perfect (the prevalence paradox). v2 therefore pre-registers **Gwet's AC1 as
the primary chance-corrected coefficient**, with raw agreement (Po) and the
modal-class share always reported alongside.

This is **not** an external gold standard: both annotators are the paper's
authors (Section 7). v2 is an instrument-quality upgrade to the same internal
construct-validity check, made credible by pre-registration rather than by
independence.

## 2. The instrument (one question at a time, infrastructure-first)

The first node is a 5-way classification of the **physical infrastructure**
(not the ephemeral presence of vehicles), which maps 1:1 onto the audit
classes. Each subsequent node is posed only when the path makes it meaningful.
Every node offers an explicit **indeterminate** escape (recorded, excluded from
the agreement coefficients, reported as a rate).

```
Q0  What is physically present at this location?  (one answer)
    1 Docks for bikes (fixed anchor hardware)     -> Q2 -> Q3a, Q3b   [DOCK-VALID]
    2 Ground parking zone, no dock (free-floating)-> Q3a, Q3b         [= A3]
    3 Scooters only                               -> Q3a, Q3b         [out-of-domain]
    4 Car-sharing bay (cars)                       -> Q3a, Q3b         [= A1]
    5 No service infrastructure visible            -> STOP             [zombie]
    6 Indeterminate (blurred, indoors, blocked)    -> STOP

Q2  How many anchor points (docks) do you count?  raw integer, or
    "count impossible" -> indeterminate.          (only if Q0 = 1)

Q3a Is the location geographically coherent?  yes / no / indeterminate
    = on land, right country/metro, not in a forbidden zone.   [no => A5]

Q3b Is the location connected to its network?  yes / no / indeterminate
    = within 1 km of a sibling station, or inside the network hull.  [no => A4]
```

Q3a/Q3b are posed for **any object found** (types 1-4), so an out-of-domain
object (scooter, car-sharing) can still be scored for placement. Types 5 and 6
stop immediately.

**Predicates (derived a posteriori; the annotator never judges the pipeline).**

| Rule | "anomaly is real" iff | Level |
|---|---|---|
| A1 | Q0 = car-sharing | per-station |
| A2 | counted docks inconsistent with declared capacity (+/-50%) | per-station (mono-operator caveat) |
| A3 | Q0 = ground/free-floating (no dock) | per-station |
| A4 | Q3b = no | per-station |
| A5 | Q3a = no | per-station |
| A6 | Q0 = docks AND feed capacity = 0 | per-station |
| A7 | not imagery-validatable | system-level only |

## 3. Codebook (frozen)

Worked examples (3 positive / 3 negative per node) live in
`codebook_examples.md`, filled during calibration (Section 5) and frozen with
this document.

| Node | criterion | indeterminate iff | tie-break |
|---|---|---|---|
| Q0=1 Docks | fixed terminal / anchor rack / branded painted bay visible in satellite or street view | hardware not assessable (occluded, &gt;24 mo, absent) | require hardware visible in at least one source; else indeterminate |
| Q0=2 Ground | bikes of the operator parked with no fixed anchor hardware (free-floating drop zone, generic stand) | cannot tell dock vs no-dock | judge the hardware, not the bikes present |
| Q0=3 Scooters | operator runs scooters only | mixed/unclear | a mixed bike+scooter operator with bikes present is not "scooters only" |
| Q0=4 Car-sharing | car-sharing bay (e.g. Citiz) | unclear vehicle class | brand + bay markings |
| Q0=5 Nothing | no service infrastructure at the exact point | imagery stale/blocked -> indeterminate, not "nothing" | demolished/empty bay counts as nothing only if imagery is current |
| Q2 count | raw count of anchor points, empties included | docks present but not countable | use the top-down (satellite) tab for large stations |
| Q3a perimeter | on land, declared country, plausibly in the metro service area | borderline coastal/admin edge | operator service-area bbox is the reference |
| Q3b proximity | within the convex hull of siblings OR <= 1 km from the nearest sibling | siblings not loadable | the 1 km / hull rule is the criterion; "feels off" is not enough |

Imagery, in priority order: Google Street View (ground truth for Q0/Q2);
satellite (Esri World Imagery) and CyclOSM/OSM with an `amenity=bicycle_rental`
overlay and a 1 km ring (for Q2 counting and Q3 placement). The sibling-station
overlay is pre-rendered per station. The Street View capture date is fetched
from the Street View Metadata API and stored per row.

## 4. Sampling (frozen sample, n = 422; SEED = 42)

Two purposes, kept separate, because the variance that matters lives at the
operator level, not the station level (stations within one operator are not
i.i.d.).

**(a) Random prevalence sample (SRS), n = 300.** A simple random sample of the
46,307-station catalogue. It estimates catalogue-level prevalence of each class
(+/-5.7% at 95% on any proportion) and, because the common classes are abundant
under random sampling, it also validates them (free-floating/A3, docked). To
reach +/-5.0%, raise `SRS_N` to 384 (total ~506).

**(b) Operator-balanced booster strata** for the rare or decisive classes an SRS
cannot cover. Each stratum is drawn round-robin across distinct systems
(`_balanced_pick`, hard cap per system) to maximise operator diversity; the SRS
keys are removed first so the two sets do not overlap.

| Booster stratum | N | distinct systems | role |
|---|---|---|---|
| A4_discordant_legacy | 40 | ~40 | core: confirm the legacy centroid FP |
| A4_discordant_composite | 40 | ~40 | core: are the new composite flags real? |
| A1_carsharing | 30 | 17 (all FR car-sharing systems) | Q0 = car-sharing |
| A5_out_of_perimeter | ~8 | rare (4 FR systems) | Q3a = no |
| A2_placeholder | ~4 | 1 (mono-operator) | parser fidelity only |

The two A4 discordant strata are the decisive ones: they adjudicate the 8,005
stations on which the legacy centroid and the topology-aware detector disagree.
Car-sharing (`flag_A1`) is excluded from the A4/A5 strata (it terminates at Q0
and never reaches the geospatial node).

**Mono-operator / rare strata** (A2 = one operator; A5 = 4 systems; A7 absent
per-station, validated at system level). These confirm parser fidelity for that
operator, not the rule's universality (Section 7). No station count fixes this;
it is a property of the French corpus, stated as a limitation.

## 5. Procedure

**Phase 0 - Calibration (excluded from all statistics).** Both annotators
jointly label about 24 calibration stations, fill `codebook_examples.md`,
reconcile every disagreement, and **lock** the codebook before the freeze.

**Phase 1 - Independent blind annotation.** Each annotator answers the tree on
every station, blind to (i) the pipeline output (never displayed) and (ii) the
co-annotator. No stratum name is shown. Per-station time, the Street View
capture date, and a timestamp are logged. A test-retest second round (about two
weeks later, order re-randomised per round) measures intra-rater stability.

**Phase 2 - Adjudication by deterministic rule (not discretion).** No third
independent adjudicator exists, so we do **not** negotiate a consensus. For each
contested node we jointly re-apply the locked codebook criterion to re-fetched
imagery; if it resolves the case, that is the gold value; if the evidence is
genuinely ambiguous, the node is marked **INDETERMINATE** and excluded from
precision/recall (never forced to a majority, never defaulted for or against
the pipeline). The full **raw inter-rater confusion matrix** (before
adjudication) and all per-annotator labels are released, so any reviewer can
recompute alternative bounds (including a pessimistic one).

## 6. Analysis plan (frozen)

Run `compute_reliability.py` unmodified on the two label files.

**Primary reliability endpoint: Gwet's AC1** (nominal), per question on the
co-routed set, with **indeterminate pairs excluded** from the coefficient.
Reported jointly: raw agreement Po, modal-class share (to expose prevalence),
Krippendorff's alpha and Cohen's kappa (for comparability), and the
indeterminate rate (instrument-quality metric). Pre-registered success target:
**AC1 >= 0.70** per question (vs the 0.17 / 0.13 of v1's collapsed questions);
a node below 0.60 is flagged as an instrument weakness (the codebook is not
changed post-freeze). The composite verdict is a secondary, descriptive
endpoint.

**Catalogue prevalence** of each class is estimated on the
`random_prevalence` stratum ONLY (the SRS), with a Wilson 95% interval; the
booster strata are excluded from prevalence because they over-represent rare
classes by design. This is the only number that speaks to "how common is each
anomaly in the catalogue".

**Per-rule precision/recall**, derived a posteriori from adjudicated node
answers (never from a pipeline-referencing verdict), pools the SRS and the
relevant booster stratum (more assessable stations), and is reported with
**both** a naive Wilson 95% interval **and a cluster-robust 95% interval
bootstrapped over systems** (2000 resamples, seed 42), because stations within
an operator are not i.i.d. The cluster interval is the one cited in the
manuscript. For mono-operator / rare classes (A2, A5, A7), only the
system-level / parser-fidelity reading is reported; no generalisation CI.

**A4 ablation endpoint.** On `A4_discordant_legacy`, the legacy centroid
false-positive rate = share judged in-network (Q3b = yes). Direct successor to
v1's "are the 8,005 discordant stations true FP?" number.

**Street View staleness sensitivity.** Per-rule P/R is recomputed on the subset
whose imagery is within 2 years of the audit year; stale-imagery disagreements
are an instrument error, not a pipeline FP, so both the full and the
recent-imagery numbers are reported.

**Routing-divergence audit.** For each station, the first node where the two
annotators diverge is recorded (expected hot spot: the docks vs free-floating
boundary).

**Attention-drift / fatigue.** Mann-Whitney on per-station duration, first vs
last quartile of each annotator's chronological sequence; reported per
annotator and per round.

## 7. Honest limitations (restated for the manuscript)

- **No external annotator; shared prior.** Both annotators are authors and
  co-built the pipeline, so they may share systematic blind spots a locked
  codebook cannot remove. Mitigations: pre-registration freeze, locked codebook,
  blinding (to pipeline and to each other), deterministic adjudication, release
  of raw labels and the raw confusion matrix. An external multi-institution
  annotation remains future work.
- **Mono-operator strata** (A2, A7) reflect one operator's data quality, not
  the rule's universality.
- **Confidence-interval width.** At about 50 assessable stations per rule, a
  Wilson half-width is roughly 9 points at precision 0.90 and roughly 14 points
  at 0.50: enough to show a rule works, not to finely separate two close
  algorithm variants.
- **Imagery currency.** Satellite/street-view lag can mislabel recently changed
  stations; such cases route to indeterminate and the Street-View-date
  sensitivity analysis quantifies the residual effect.

## 8. Output files

- `PROTOCOL.md` - this pre-registration
- `codebook_examples.md` - worked examples per node (filled at calibration, frozen)
- `sample.csv` - frozen stratified sample (+ `sample.sha256`)
- `labels_<annotator>.csv` - per-annotator node answers + evidence log
- `gold_labels.csv` - adjudicated node answers + derived verdict
- `reliability_report.json` - per-question AC1/alpha/kappa/Po/modal/indeterminate,
  raw inter-rater confusion, per-rule P/R with Wilson and cluster-robust CIs,
  A4 FP rate, Street-View-staleness sensitivity, fatigue test

---

## 9. Post-freeze amendment log (added 2026-07-06, after label collection)

Sections 1-8 above are the frozen pre-registration and are unchanged. Per the
freeze rule of this document, every deviation observed during or after the
campaign is logged here, dated, and clearly separated from the frozen text.
The paired analysis notes live in `RESULTS.md`.

**A9.1 - A2 predicate defect (analysis correction, disclosed).** The frozen
`compute_reliability.py` mishandles missing adjudicated dock counts in
`_pred_A2` (a rater disagreement yields a NaN gold value; `not nan` is falsy
and NaN comparisons return False, so the predicate returns True). All 47
nominally "assessable" A2 stations in the frozen script's output arise from
this path; the true count of stations with a concordant dock count is 0. The
frozen script's A2 precision/recall output is therefore discarded, and the
manuscript reports A2 as **not per-station assessable**, keeping only the
pre-registered system-level parser-fidelity reading. The frozen script itself
is left unmodified, as required by the freeze.

**A9.2 - Q2 agreement metric (exploratory recomputation).** The frozen script
compares Q2 answers as strings, which is degenerate for a raw count ("24" vs
"24.0"). The manuscript reports the exploratory numeric recomputation instead:
exact agreement 33%, within +/-20% 40%, Spearman 0.03 (n = 30 co-routed
pairs). Both computations are reproducible from the released labels.

**A9.3 - Street-View staleness sensitivity: not computable.** The Street View
Metadata API key was unavailable during the campaign (`sv_status = NO_KEY` on
all 844 rows), so capture dates were never recorded and the pre-specified
staleness sensitivity (Section 6) returns an empty subset. The imagery-currency
mitigation of Section 7 therefore rests on the codebook's indeterminate
routing alone, and the ghost-station estimates carry this caveat.

**A9.4 - Intra-rater test-retest round: not conducted.** The second annotation
round pre-specified in Section 5 (`revisit_round`) was not run before
manuscript integration. It remains possible on the frozen sample and would be
reported as a dated addendum here.

**A9.5 - Success-gate outcome (recorded, no threshold change).** Against the
pre-registered gates of Section 6 (AC1 >= 0.70 per node; < 0.60 = instrument
weakness): Q3a = 0.983 and Q3b = 0.946 pass; Q0 = 0.559 is recorded as an
instrument weakness, as pre-specified; Q2 is covered by A9.2. The gates
themselves are unchanged.

**A9.6 - Phase 2 adjudication: pending.** All published numbers use
concordant judgements only (gold = agreement); the 212 stations with at least
one contested node are excluded from the affected quantities. The deterministic
codebook re-application of Section 5 (Phase 2) has not yet been held; it can
only add assessable stations to the per-rule counts and does not alter the
inter-rater coefficients, which are final by construction.

**A9.7 - Reporting split.** The manuscript reports the pre-registered
endpoints (per-node AC1, per-rule P/R with cluster CIs, the A4 ablation
endpoint, SRS prevalence). The robustness items affected by A9.3-A9.4 and the
corrections A9.1-A9.2 are documented in this log and in `RESULTS.md`, released
with the raw per-annotator labels and the frozen script's full output
(`reliability_report.json`), so every alternative bound remains recomputable.

**A9.8 - Exploratory OSM cross-validation (added 2026-07-06, not
pre-registered).** Because the Street View capture dates are unrecoverable
without credentials (A9.3), an independent-source corroboration replaces the
staleness sensitivity: the adjudicated physical-existence judgements are
cross-checked against OpenStreetMap via two credential-free Overpass sweeps
(`amenity=bicycle_rental` and `amenity=car_sharing`, nodes and ways, nearest
distance per station of the frozen sample), with concordance reported at three
radii (50 / 100 / 150 m) so the radius choice is visibly not doing the work.
This is a different construct from imagery staleness (community mapping
coverage instead of imagery currency) and is reported as exploratory,
clearly separated from the pre-registered endpoints. Script:
`osm_crosscheck.py`; output: `osm_crosscheck.csv`.
