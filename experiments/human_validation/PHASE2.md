# Phase 2 playbook: the three levers that improve the published numbers

All three actions are pre-specified in `PROTOCOL.md` (Sections 5-6) or logged
as amendments (Section 9), so their results go straight into the manuscript
without weakening the pre-registration claim.

## 1. Joint adjudication session (`adjudication_phase2.csv`, 212 stations)

Deterministic re-application of the locked codebook to re-fetched imagery
(PROTOCOL.md Phase 2). Never negotiate a consensus: cite the codebook line
that decides, or mark INDETERMINATE. Fill the three empty columns
(`gold_decision`, `gold_Q2_count`, `decided_by_codebook_rule`) during the
session; the `codebook_hint` column quotes the relevant tie-break.

Priorities (the file is already sorted):

| Priority | n | What it feeds |
|---|---|---|
| P1 | 44 | the two A4 discordant strata: every resolved Q3b grows the decisive ablation endpoint (currently 14/14; ceiling 40/40 per stratum) |
| P2 | 54 | A1 precision/recall (car-sharing stratum) + the 32 dock-count divergences (any concordant count makes A2 per-station assessable for the first time) |
| P3 | 108 | SRS: prevalence CIs, ghost-station rate, A3/A1 pooled P-R |
| P4 | 6 | A5/A2 strata leftovers |

Expected session cost: the three dominant classes (trot_vs_float,
carshare_vs_rien, float_vs_rien = 90 stations) each have an explicit codebook
tie-break, so most of P1-P3 should resolve in one pass (~2-3 h at 45 s per
station). After the session, append the adjudicated golds to the analysis by
re-running `compute_reliability.py` (reliability coefficients do not change;
per-rule counts and the ablation numerator/denominator grow).

## 2. Independent-source corroboration (no credentials needed)

Without a Google key the capture dates are unrecoverable (A9.3), so the
imagery-currency check is replaced by an OSM cross-validation (amendment
A9.8), reproducible by any reviewer with zero credentials:

```bash
python -m experiments.human_validation.osm_crosscheck            # Overpass fetch + report
python -m experiments.human_validation.osm_crosscheck --offline  # re-report from CSV
```

Reports the share of adjudicated stations with an `amenity=bicycle_rental`
(or `car_sharing` for A1) OSM object within 50 / 100 / 150 m, per adjudicated
class. Concordance corroborates the existence judgements through a second,
independent observation channel. `fetch_sv_dates.py` is kept in the tree for
the day a Maps key is available (the metadata endpoint is free); it would then
populate the pre-registered `sv_date_sensitivity` block as originally
specified.

## 3. Intra-rater test-retest round (`retest_sample.csv`, n = 60)

Proportional allocation across strata (43 SRS / 6 + 6 A4 discordant / 4 A1 /
1 A5), drawn with seed 4242, order re-shuffled. Both annotators, >= 2 weeks
after round 0 (i.e. any time from late June 2026), in the app:

```bash
export HV_SAMPLE_PATH=experiments/human_validation/retest_sample.csv
streamlit run experiments/human_validation/annotator_app.py
# pick round "Re-test" in the sidebar; order is auto-re-randomised per round
```

Storage keys on (annotator, station, revisit_round), so round 0 labels are
untouched. Analysis: per-node intra-rater AC1 on the 60 pairs (same
`compute_reliability.py` primitives, labels round 0 vs round 1 of the same
annotator); one extra line in the reliability table. Restore `sample.csv` as
the app default afterwards (unset `HV_SAMPLE_PATH`).
