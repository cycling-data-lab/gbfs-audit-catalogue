"""Extract a stratified 200-station sample for human annotation.

Usage:
    python -m experiments.annotation.sample_extractor \
        --catalogue catalogue/stations_gold_standard_final.parquet \
        --ablation results/xp2/xp2_ablation.parquet \
        --output experiments/annotation/sample_200.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


STRATA = {
    "clean_docked": {"n": 30, "desc": "No flag, high confidence, dock-based"},
    "A1_carsharing": {"n": 20, "desc": "flag_A1 = True"},
    "A2_placeholder": {"n": 15, "desc": "flag_A2 = True"},
    "A3_freefloating": {"n": 25, "desc": "flag_A3 = True"},
    "A4_agree_flag": {"n": 20, "desc": "Both detectors flag"},
    "A4_discordant_legacy": {"n": 30, "desc": "Legacy centroid flags, composite does not"},
    "A4_discordant_composite": {"n": 15, "desc": "Composite flags, legacy does not"},
    "A6_zero_capacity": {"n": 10, "desc": "flag_A6 = True"},
    "A7_null_capacity": {"n": 20, "desc": "flag_A7 = True"},
    "A3_boundary": {"n": 15, "desc": "Capacity ratio in [2, 5] (threshold zone)"},
}

SEED = 42


def extract_sample(
    catalogue: pd.DataFrame,
    ablation: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rng_state = SEED
    samples = []

    def _sample(pool: pd.DataFrame, n: int, stratum: str) -> pd.DataFrame:
        k = min(n, len(pool))
        s = pool.sample(k, random_state=rng_state)
        s = s.copy()
        s["stratum"] = stratum
        return s

    cat = catalogue.copy()

    # Clean dock-based
    clean = cat[
        (cat["station_type"] == "docked_bike")
        & (cat["audit_confidence"] == "high")
    ]
    samples.append(_sample(clean, 30, "clean_docked"))

    # A1
    a1 = cat[cat["flag_A1"] == True]
    samples.append(_sample(a1, 20, "A1_carsharing"))

    # A2
    a2 = cat[cat["flag_A2"] == True]
    samples.append(_sample(a2, 15, "A2_placeholder"))

    # A3
    a3 = cat[(cat["flag_A3"] == True) & (cat["flag_A2"] == False)]
    samples.append(_sample(a3, 25, "A3_freefloating"))

    # A4 strata (requires ablation data)
    if ablation is not None:
        agree_flag = ablation[ablation["discordance_class"] == "AGREE_FLAG"]
        disc_legacy = ablation[ablation["discordance_class"] == "FP_LEGACY"]
        disc_composite = ablation[ablation["discordance_class"] == "FN_COMPOSITE"]

        if len(agree_flag) > 0:
            merged = agree_flag.merge(
                cat[["system_id", "station_id", "lat", "lon", "station_type",
                     "capacity", "operator_name", "city", "audit_confidence"]],
                on=["system_id", "station_id"], how="left",
            )
            samples.append(_sample(merged, 20, "A4_agree_flag"))

        if len(disc_legacy) > 0:
            merged = disc_legacy.merge(
                cat[["system_id", "station_id", "lat", "lon", "station_type",
                     "capacity", "operator_name", "city", "audit_confidence"]],
                on=["system_id", "station_id"], how="left",
            )
            samples.append(_sample(merged, 30, "A4_discordant_legacy"))

        if len(disc_composite) > 0:
            merged = disc_composite.merge(
                cat[["system_id", "station_id", "lat", "lon", "station_type",
                     "capacity", "operator_name", "city", "audit_confidence"]],
                on=["system_id", "station_id"], how="left",
            )
            samples.append(_sample(merged, 15, "A4_discordant_composite"))

    # A6
    a6 = cat[cat["flag_A6"] == True]
    samples.append(_sample(a6, 10, "A6_zero_capacity"))

    # A7
    a7 = cat[(cat["flag_A7"] == True) & (cat["flag_A3"] == False)]
    samples.append(_sample(a7, 20, "A7_null_capacity"))

    # A3 boundary (capacity ratio between 2 and 5)
    docked_with_cap = cat[
        (cat["station_type"] == "docked_bike")
        & (cat["capacity"].notna())
        & (cat["capacity"] > 0)
    ]
    if len(docked_with_cap) > 0:
        sys_stats = docked_with_cap.groupby("system_id")["capacity"].agg(["mean", "median"])
        sys_stats["ratio"] = sys_stats["mean"] / sys_stats["median"].clip(lower=0.01)
        boundary_systems = sys_stats[(sys_stats["ratio"] >= 2) & (sys_stats["ratio"] <= 5)].index
        boundary = cat[cat["system_id"].isin(boundary_systems)]
        samples.append(_sample(boundary, 15, "A3_boundary"))

    result = pd.concat(samples, ignore_index=True)

    keep_cols = [
        "stratum", "system_id", "station_id", "lat", "lon",
        "station_type", "capacity", "operator_name", "city",
        "flag_A1", "flag_A2", "flag_A3", "flag_A4", "flag_A5",
        "flag_A6", "flag_A7", "audit_confidence",
    ]
    keep_cols = [c for c in keep_cols if c in result.columns]

    # Add empty annotation columns
    result["Q1_is_bikeshare"] = ""
    result["Q2_capacity_physical"] = ""
    result["Q3_exists_at_coords"] = ""
    result["Q4_within_perimeter"] = ""
    result["Q5_verdict"] = ""
    result["annotator"] = ""
    result["notes"] = ""

    return result[keep_cols + [
        "Q1_is_bikeshare", "Q2_capacity_physical", "Q3_exists_at_coords",
        "Q4_within_perimeter", "Q5_verdict", "annotator", "notes",
    ]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalogue", required=True)
    parser.add_argument("--ablation", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cat = pd.read_parquet(args.catalogue)
    abl = pd.read_parquet(args.ablation) if args.ablation else None

    sample = extract_sample(cat, abl)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(out, index=False)

    print(f"Extracted {len(sample)} stations across {sample['stratum'].nunique()} strata:")
    print(sample["stratum"].value_counts().to_string())
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
