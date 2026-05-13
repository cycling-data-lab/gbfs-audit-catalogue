"""A4 robust-3-sigma sensitivity sweep under the released MAD-based
detector. Reports Kendall tau between rankings produced under each
threshold and the reference threshold, plus the number of A4-flagged
stations under each setting.

Two count-level reference rankings are used (no IMD / no companion
data):
- Top-10 cities by certified docked-bike station count
- Top-10 operators by certified docked-bike station count

The sweep covers sigma in {2.0, 2.5, 3.0, 3.5, 4.0}. The reference is
sigma=3.0 (the value reported in the paper).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from audit_pipeline import core  # noqa: E402

ENRICH_OUTPUTS = [
    "capacity_raw", "capacity_audited",
    "flag_A1", "flag_A2", "flag_A3", "flag_A4", "flag_A5",
    "flag_A6", "flag_A7",
    "operator_name", "audit_confidence",
    "dist_to_nearest_station_m", "n_stations_within_500m",
    "n_stations_within_1km", "nearest_system_dist_m",
    "catchment_density_per_km2",
]


def _audit_with_sigma(raw: pd.DataFrame, sigma: float) -> pd.DataFrame:
    saved = core.A4_SIGMA
    try:
        core.A4_SIGMA = sigma
        return core._compute_tier1(raw)
    finally:
        core.A4_SIGMA = saved


def _topk_cities(df: pd.DataFrame, k: int) -> list[str]:
    docked = df[(df.station_type == "docked_bike") & (~df.flag_A4)]
    return (
        docked.groupby("city").size().sort_values(ascending=False).head(k).index.tolist()
    )


def _topk_operators(df: pd.DataFrame, k: int) -> list[str]:
    docked = df[(df.station_type == "docked_bike") & (~df.flag_A4)]
    return (
        docked.groupby("operator_name").size().sort_values(ascending=False).head(k).index.tolist()
    )


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    union = sa | sb
    return len(sa & sb) / len(union) if union else 1.0


def _rank_overlap_tau(ref_order: list[str], test_order: list[str]) -> float:
    """Kendall tau on the symmetric difference + intersection."""
    universe = list(dict.fromkeys(ref_order + test_order))  # ordered union, dedupe
    ref_rank = {x: i for i, x in enumerate(ref_order)}
    test_rank = {x: i for i, x in enumerate(test_order)}
    # absentees get rank len() (worst)
    n = len(universe)
    a = [ref_rank.get(x, n) for x in universe]
    b = [test_rank.get(x, n) for x in universe]
    tau, _ = kendalltau(a, b)
    return float(tau)


def main() -> None:
    print(f"Loading parquet from {core.CATALOGUE_FILE} ...")
    df = pd.read_parquet(core.CATALOGUE_FILE)
    raw = df.drop(columns=[c for c in ENRICH_OUTPUTS if c in df.columns])
    print(f"  {len(raw):,} stations across {raw.system_id.nunique()} systems")

    sigmas = [2.0, 2.5, 3.0, 3.5, 4.0]
    rows = []
    ref_audited = _audit_with_sigma(raw, 3.0)
    ref_top10_cities = _topk_cities(ref_audited, 10)
    ref_top50_cities = _topk_cities(ref_audited, 50)
    ref_top10_ops = _topk_operators(ref_audited, 10)
    ref_top50_ops = _topk_operators(ref_audited, 50)
    print(f"  Reference Top-10 cities (sigma=3.0): {ref_top10_cities}")
    print(f"  Reference Top-10 operators (sigma=3.0): {ref_top10_ops}")

    for sigma in sigmas:
        audited = _audit_with_sigma(raw, sigma)
        n_a4_stations = int(audited.flag_A4.sum())
        n_a4_systems = audited.loc[audited.flag_A4, "system_id"].nunique()
        rows.append(
            {
                "sigma": sigma,
                "A4_stations": n_a4_stations,
                "A4_systems": n_a4_systems,
                "A4_share_pct": round(100.0 * n_a4_stations / len(audited), 2),
                "tau_top10_cities": round(_rank_overlap_tau(ref_top10_cities, _topk_cities(audited, 10)), 3),
                "tau_top10_operators": round(_rank_overlap_tau(ref_top10_ops, _topk_operators(audited, 10)), 3),
                "jaccard_top10_cities": round(_jaccard(ref_top10_cities, _topk_cities(audited, 10)), 3),
                "jaccard_top50_cities": round(_jaccard(ref_top50_cities, _topk_cities(audited, 50)), 3),
                "jaccard_top10_operators": round(_jaccard(ref_top10_ops, _topk_operators(audited, 10)), 3),
                "jaccard_top50_operators": round(_jaccard(ref_top50_ops, _topk_operators(audited, 50)), 3),
            }
        )

    out = pd.DataFrame(rows)
    Path("experiments/e2_threshold_sensitivity").mkdir(parents=True, exist_ok=True)
    out.to_csv("experiments/e2_threshold_sensitivity/a4_sigma_sweep.csv", index=False)
    print()
    print(out.to_string(index=False))
    print()
    print("Saved to experiments/e2_threshold_sensitivity/a4_sigma_sweep.csv")


if __name__ == "__main__":
    main()
