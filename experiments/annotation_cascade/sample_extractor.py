"""Extract the stratified sample for the cascade annotation campaign (v2).

Same sampling philosophy as ``experiments/annotation/sample_extractor.py``
(stratify by the route the pipeline predicts, deduplicate across strata,
shuffle to kill order effects) but resized so every decision-tree node of the
cascade instrument (see PROTOCOL.md) receives >= 50 dual-rated stations, and
with a new ``clean_freefloating`` negative-control stratum that v1 lacked.

The output CSV carries one empty column per tree node instead of the v1
Q1..Q5 columns, plus a per-node evidence-log column.

Usage:
    python -m experiments.annotation_cascade.sample_extractor \
        --catalogue catalogue/stations_gold_standard_final.parquet \
        --ablation results/xp2/xp2_ablation.parquet \
        --output experiments/annotation_cascade/sample.csv
"""
from __future__ import annotations

import argparse
import hashlib
import warnings
from pathlib import Path

import pandas as pd

SEED = 42

# Strata sized for the cascade (PROTOCOL.md Section 4). A4 discordant strata
# stay at 50-60 (core contribution, tightest CI). clean_freefloating is the
# new negative control for the M1.Q2=NO / M1.Q4=NO leaf. A2/A7 are pool-capped
# single-operator strata, validated at the system level.
STRATA_N = {
    "clean_docked": 70,
    "ff_honest_capacity": 60,
    "A1_carsharing": 60,
    "A2_placeholder": 40,
    "A3_freefloating": 70,
    "A4_agree_flag": 40,
    "A4_discordant_legacy": 60,
    "A4_discordant_composite": 60,
    "A5_out_of_perimeter": 40,
    "A6_zero_capacity": 10,
    "A7_null_capacity": 30,
    "A3_boundary": 20,
}


def extract_sample(
    catalogue: pd.DataFrame,
    ablation: pd.DataFrame | None = None,
) -> pd.DataFrame:
    samples: list[pd.DataFrame] = []
    seen_keys: set[str] = set()
    empty_strata: list[str] = []

    def _key(row: pd.Series) -> str:
        return f"{row['system_id']}|{row['station_id']}"

    def _sample(pool: pd.DataFrame, stratum: str) -> pd.DataFrame:
        n = STRATA_N[stratum]
        pool = pool.copy()
        pool["_key"] = pool.apply(_key, axis=1)
        pool = pool[~pool["_key"].isin(seen_keys)]
        if len(pool) == 0:
            empty_strata.append(stratum)
            warnings.warn(
                f"Stratum '{stratum}': 0 eligible stations after dedup "
                f"(target n={n}). Skipped.",
                stacklevel=2,
            )
            return pd.DataFrame()
        s = pool.sample(min(n, len(pool)), random_state=SEED).copy()
        s["stratum"] = stratum
        seen_keys.update(s.apply(_key, axis=1))
        return s

    cat = catalogue.copy()

    clean = cat[(cat["station_type"] == "docked_bike")
                & (cat["audit_confidence"] == "high")]
    samples.append(_sample(clean, "clean_docked"))

    # Hardest case for A3: free-floating with a small, honest declared
    # capacity (1-3). In this catalogue every free_floating is flagged A3,
    # so this stratum tests whether imagery still confirms "no physical dock"
    # (A3 precision) even when the declared capacity is not inflated.
    ff_honest = cat[(cat["station_type"] == "free_floating")
                    & (cat["capacity"].fillna(0).between(1, 3))]
    samples.append(_sample(ff_honest, "ff_honest_capacity"))

    samples.append(_sample(cat[cat["flag_A1"] == True], "A1_carsharing"))  # noqa: E712
    samples.append(_sample(cat[cat["flag_A2"] == True], "A2_placeholder"))  # noqa: E712
    samples.append(_sample(
        cat[(cat["flag_A3"] == True) & (cat["flag_A2"] == False)],  # noqa: E712
        "A3_freefloating",
    ))

    if ablation is not None:
        meta_cols = [
            "system_id", "station_id", "lat", "lon", "station_type",
            "capacity", "operator_name", "city", "audit_confidence",
        ]
        flag_cols = [f"flag_A{i}" for i in range(1, 8) if f"flag_A{i}" in cat.columns]
        join_cols = [c for c in meta_cols + flag_cols if c in cat.columns]
        for cls, name in [
            ("AGREE_FLAG", "A4_agree_flag"),
            ("FP_LEGACY", "A4_discordant_legacy"),
            ("FN_COMPOSITE", "A4_discordant_composite"),
        ]:
            pool = ablation[ablation["discordance_class"] == cls]
            if len(pool) > 0:
                merged = pool.merge(
                    cat[join_cols], on=["system_id", "station_id"], how="left",
                )
                samples.append(_sample(merged, name))

    if "flag_A5" in cat.columns:
        samples.append(_sample(cat[cat["flag_A5"] == True], "A5_out_of_perimeter"))  # noqa: E712
    samples.append(_sample(cat[cat["flag_A6"] == True], "A6_zero_capacity"))  # noqa: E712
    samples.append(_sample(
        cat[(cat["flag_A7"] == True) & (cat["flag_A3"] == False)],  # noqa: E712
        "A7_null_capacity",
    ))

    docked = cat[(cat["station_type"] == "docked_bike")
                 & (cat["capacity"].notna()) & (cat["capacity"] > 0)]
    if len(docked) > 0:
        stats = docked.groupby("system_id")["capacity"].agg(["mean", "median"])
        stats["ratio"] = stats["mean"] / stats["median"].clip(lower=0.01)
        boundary_sys = stats[(stats["ratio"] >= 2) & (stats["ratio"] <= 5)].index
        samples.append(_sample(cat[cat["system_id"].isin(boundary_sys)], "A3_boundary"))

    valid = [s for s in samples if len(s) > 0]
    if not valid:
        raise RuntimeError("No stations extracted — check catalogue/ablation inputs.")
    result = pd.concat(valid, ignore_index=True)
    result.drop(columns=["_key"], errors="ignore", inplace=True)

    keep = [c for c in [
        "stratum", "system_id", "station_id", "lat", "lon",
        "station_type", "capacity", "operator_name", "city",
        "flag_A1", "flag_A2", "flag_A3", "flag_A4", "flag_A5",
        "flag_A6", "flag_A7", "audit_confidence",
    ] if c in result.columns]

    # One empty column per cascade question (v3 schema, see QUESTIONS.md).
    # The Streamlit app writes answers to the DB, not to these columns; they
    # exist only for an optional manual-CSV workflow and for documentation.
    #   Q0 domain gate, Q1 docks present, Q2 ordinal dock count,
    #   Q3a perimeter valid, Q3b within network.
    node_cols = [
        "Q0_libre_service",     # oui/non/indetermine
        "Q1_docks_presents",    # oui/non/indetermine  (si Q0=oui)
        "Q2_nb_docks_classe",   # 1-5/6-10/.../>50/indet  (si Q1=oui)
        "Q3a_perimetre",        # oui/non/indetermine  (si Q0=oui)
        "Q3b_proximite",        # oui/non/indetermine  (si Q0=oui)
        "verdict",              # derived label, left blank (script derives it)
    ]
    for c in node_cols:
        result[c] = ""
    result["evidence"] = ""    # source|date|observation per question, ';'-joined
    result["annotator"] = ""
    result["seconds"] = ""
    result["notes"] = ""

    out = result[keep + node_cols + ["evidence", "annotator", "seconds", "notes"]]
    out = out.sample(frac=1, random_state=SEED).reset_index(drop=True)

    if empty_strata:
        print(f"WARNING: {len(empty_strata)} empty strata: {empty_strata}")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--catalogue", required=True)
    p.add_argument("--ablation", default=None)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    cat = pd.read_parquet(args.catalogue)
    abl = pd.read_parquet(args.ablation) if args.ablation else None
    sample = extract_sample(cat, abl)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(out, index=False)

    # Freeze hash for pre-registration.
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix(".sha256").write_text(f"{digest}  {out.name}\n", encoding="utf-8")

    print(f"Extracted {len(sample)} stations across {sample['stratum'].nunique()} strata:")
    print(sample["stratum"].value_counts().to_string())
    print(f"\nSaved to {out}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
