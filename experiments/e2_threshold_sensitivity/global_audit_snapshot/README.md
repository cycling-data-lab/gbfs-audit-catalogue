# Global sweep snapshot (manuscript artifact)

This folder is the **frozen snapshot of the worldwide GBFS sweep** used for the
global-projection section of the manuscript (Section "Global scalability
projection", Table `global-audit`/S6, and the A7 distribution Table S3).

| File | Role |
|------|------|
| `massive_audit_results.csv` | Per-system audit of the full MobilityData catalogue (1,509 systems). One row per system; columns include `stations`, `reachable`, the A1–A5 flags, `a6_zero_capacity_pct`, `capacity_nan_pct`. |
| `massive_audit_summary.json` | Aggregated headline + per-country counts. Matches the manuscript exactly. |
| `massive_audit.py` | The generator (live crawl of each operator's auto-discovery + `station_information.json`). Thresholds: `N_MIN_DOCK = 20`, A6 `a6_zero_capacity_pct > 1.0` %, A7 `capacity_nan_pct > 50.0` %. |
| `verify_snapshot.py` | Re-derives and asserts the reproducible manuscript numbers from the two files above. |

## Provenance

- **Snapshot date:** 2026-04 (the crawl that produced every global number in the
  manuscript). Recovered from the predecessor project
  `bikeshare-data-explorer/papers/01_gold_standard/experiments/e5_europe/`; it
  had not been copied into this repository.
- The crawl is **live-network** and therefore not byte-reproducible on re-run
  (operator feeds drift). This folder is the canonical, citeable artifact.

## Reproducibility status

Run `python verify_snapshot.py` (no dependencies beyond the standard library).
All of the following are **exactly reproducible** from the snapshot and are
asserted by the script:

- 1,509 systems audited; 1,420 reachable; 917 publish `station_information`;
  **204** flagged by at least one structural class A1–A5.
- The full **per-country A1–A5 breakdown** (Table `global-audit` / S6), e.g.
  FR 255/253/38 (A1 17, A2 14, A3 4, A4 3, A5 3), DE 251/243/32 (A1 21, A2 4,
  A3 9), US 175/172/0.
- The **A7 distribution** (Table S3): base 640 systems with ≥20 stations,
  365 cross the 50 % NaN threshold, buckets {0:238, (0,1):4, [1,10):11,
  [10,50):22, [50,99):41, [99,100):5, 100:319}, 87.0 % at the two extremes.
- The **A6 and A7-exclusive** semantic-warning counts. A6 is evaluated on the
  **301 docked systems** with ≥20 stations (free-floating systems, where
  `c = 0` is uninformative, are excluded via the repository's own
  `--infer-type` operator-name heuristics, copied verbatim into the script):
  **22** cross τ_A6 = 1 %. A7-exclusive (cross the 50 % NaN threshold and not
  also flagged by A1–A6) = **245** systems / **97,314** stations, of which
  **Dott** alone is 147 systems = 76 % of the exclusive-A7 station mass.

Every number reported in the manuscript's global-projection section is now
re-derived and asserted by `verify_snapshot.py` (19/19 checks). The A6 base and
A7-exclusive definitions are fixed and documented (docked-only via the shipped
type-inference regexes; τ_A6 = 1 %, τ_A7 = 50 %), so the counts regenerate
deterministically from this CSV.

## Note on `../global_audit_results_typed.csv`

That sibling file is a **later re-crawl (2026-05-13)**, not the manuscript
snapshot: it reaches more systems and drifts (e.g. A6→19, A7→358). Do not use it
to reproduce the paper. This `global_audit_snapshot/` folder is canonical.
