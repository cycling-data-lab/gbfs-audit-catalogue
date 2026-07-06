# Campaign v2 results (labels collected 2026-06)

Full campaign: 2 annotators x 422 stations (844 annotations), frozen sample
verified against `sample.sha256`. `labels_rohan.csv` / `labels_gael.csv` are
the per-annotator exports (columns renamed to the `Q0_type`,
`Q2_nb_docks_classe`, `Q3a_perimetre`, `Q3b_proximite` schema expected by the
frozen script; no value edited). `reliability_report.json` is the output of
the pre-registered script run unmodified:

```
python -m experiments.human_validation.compute_reliability \
    --labels1 experiments/human_validation/labels_rohan.csv \
    --labels2 experiments/human_validation/labels_gael.csv \
    --output  experiments/human_validation/reliability_report.json
```

Headline numbers (manuscript Section "Construct-validity check", tables
tab:irr / tab:perrule / tab:prevalence):

- Reliability (AC1, target >= 0.70): Q0 0.559 (instrument weakness,
  reported as such), Q3a 0.983, Q3b 0.946; composite verdict 0.532
  (secondary).
- A4 ablation: discordant-legacy 14/14 judged in-network (legacy FP rate
  100%, Wilson [78.5, 100]); discordant-composite 1/12 confirmed
  out-of-network + 9 adjudicated ghosts.
- Per-rule: A1 P=0.71 R=0.91; A3 P=0.73 R=0.99 (class-exact) and 183/189
  defect-any; A4 2 TP / 0 FP; A5 0/12 (construct mismatch).
- SRS prevalence: 37/300 ghost stations (12.3%, lower bound).

## Post-freeze corrections (disclosed in the manuscript)

1. **A2 predicate artifact.** The frozen `_pred_A2` mishandles missing
   adjudicated counts: when the two raters disagree on Q2 the gold value is
   NaN, `not nan` is falsy, NaN comparisons return False, and the predicate
   returns True. All 47 "assessable" A2 records in
   `reliability_report.json` arise this way; the true count of stations
   with a concordant dock count is 0. The A2 P/R printed by the script
   (P=1.00, R=0.09) must therefore be discarded; the manuscript reports A2
   as not per-station assessable.
2. **Q2 string-vs-numeric agreement.** The per-question raw agreement of
   0% on Q2 is a dtype artifact ("24" vs "24.0" compared as strings).
   Recomputed numerically: exact 33%, within +/-20% 40%, Spearman 0.03
   (n=30 co-routed numeric pairs). The manuscript reports the numeric
   values.
3. **Street View staleness.** `sv_status = NO_KEY` on all 844 rows (the
   metadata API key was unavailable during the campaign), so `sv_date` was
   never recorded and the pre-registered staleness sensitivity returns an
   empty subset (`n_recent = 0`). Reported as a limitation.

## Still pending

- Phase 2 deterministic adjudication of the 212 stations with at least one
  contested node (can only add assessable stations; reliability
  coefficients are final).
- Intra-rater test-retest round (`revisit_round` is 0 everywhere).
