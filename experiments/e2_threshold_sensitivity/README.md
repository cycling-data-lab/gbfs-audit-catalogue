# E2 — threshold sensitivity & global sweep

| Artifact | What it is |
|----------|------------|
| `global_audit_snapshot/` | **Canonical manuscript snapshot** of the worldwide sweep (2026-04). Reproduces every global number in the paper. Start here; see its `README.md` and run `verify_snapshot.py`. |
| `global_audit_results_typed.csv` | A **later re-crawl (2026-05-13)**, kept for reference only. Live feeds drifted, so its counts (A6→19, A7→358, 580 reachable) **do not match the manuscript**. Not the paper snapshot. |
| `global_audit_results.csv` | Same later crawl, without `--infer-type`. |
| `global_a3_ratio.csv` | Live A3 capacity-profile-ratio sweep (33 countries) for the τ_A3 = 5 justification. |
| `a4_sigma_sweep.csv` | A4 σ-threshold sensitivity (Table S1). |

**To reproduce the paper's global-projection numbers:**
`python global_audit_snapshot/verify_snapshot.py`
