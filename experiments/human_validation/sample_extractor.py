"""Extract the stratified sample for the human-validation annotation campaign (v2).

Same sampling philosophy as ``experiments/annotation/sample_extractor.py``
(stratify by the route the pipeline predicts, deduplicate across strata,
shuffle to kill order effects) but resized so every decision-tree node of the
decision-tree instrument (see PROTOCOL.md) receives >= 50 dual-rated stations, and
with a new ``clean_freefloating`` negative-control stratum that v1 lacked.

The output CSV carries one empty column per tree node instead of the v1
Q1..Q5 columns, plus a per-node evidence-log column.

Usage:
    python -m experiments.human_validation.sample_extractor \
        --catalogue catalogue/stations_gold_standard_final.parquet \
        --ablation results/xp2/xp2_ablation.parquet \
        --output experiments/human_validation/sample.csv
"""
from __future__ import annotations

import argparse
import hashlib
import warnings
from pathlib import Path

import pandas as pd

SEED = 42

# Sampling design (PROTOCOL.md Section 4), ~435 stations total:
#   - a random prevalence sample (SRS) of SRS_N stations drawn from the whole
#     catalogue, for catalogue-level prevalence (+/-5.7% at 95% with n=300) and
#     for validating the common classes (docked, free-floating/A3), which are
#     abundant under random sampling;
#   - operator-balanced BOOSTER strata for the rare / decisive classes an SRS
#     cannot cover: the two A4 discordant sets (core ablation), A1, A5, A2.
# A6/A7/A3-boundary are not per-station validatable here (empty or
# system-level) and are validated at the system level instead.
SRS_N = 300
STRATA_N = {
    "A1_carsharing": 30,            # spread across the ~17 car-sharing systems
    "A2_placeholder": 10,           # mono-operator: parser fidelity, system-level
    "A4_discordant_legacy": 40,     # core: confirm the legacy centroid FP
    "A4_discordant_composite": 40,  # core: are the new composite flags real?
    "A5_out_of_perimeter": 15,
}


def _balanced_pick(pool: pd.DataFrame, n: int, seed: int,
                   max_per_system: int | None = None) -> pd.DataFrame:
    """Round-robin pick across distinct systems to maximise operator diversity.

    The publication variance lives at the operator level, not the station level,
    so a flat ``sample(n)`` that returns 50 stations of one operator has an
    effective n close to 1. This spreads the draw across as many systems as
    possible (one per system, then two per system, ...) and optionally caps the
    number of stations per system."""
    if len(pool) <= n and max_per_system is None:
        return pool
    shuffled = pool.sample(frac=1, random_state=seed).reset_index(drop=True)
    sys_order = {s: i for i, s in enumerate(shuffled["system_id"].drop_duplicates())}
    shuffled["_rank"] = shuffled.groupby("system_id").cumcount()
    if max_per_system is not None:
        shuffled = shuffled[shuffled["_rank"] < max_per_system]
    shuffled["_sord"] = shuffled["system_id"].map(sys_order)
    shuffled = shuffled.sort_values(["_rank", "_sord"]).head(n)
    return shuffled.drop(columns=["_rank", "_sord"])


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
        # cap per system so no single operator dominates a stratum (effective n)
        cap = max(4, n // 8)
        s = _balanced_pick(pool, min(n, len(pool)), SEED, max_per_system=cap).copy()
        s["stratum"] = stratum
        n_sys = s["system_id"].nunique()
        if n_sys < 5 and stratum not in ("A2_placeholder", "A7_null_capacity"):
            warnings.warn(
                f"Stratum '{stratum}': only {n_sys} distinct system(s) "
                f"({len(s)} stations) - per-rule CI will be operator-bound.",
                stacklevel=2,
            )
        seen_keys.update(s.apply(_key, axis=1))
        return s

    cat = catalogue.copy()

    # 1) Random prevalence sample (SRS), drawn FIRST so it is a true random
    #    sample of the population; the targeted boosters below come from the
    #    rest, so the two sets do not overlap.
    srs = cat.sample(min(SRS_N, len(cat)), random_state=SEED).copy()
    srs["stratum"] = "random_prevalence"
    srs["_key"] = srs.apply(_key, axis=1)
    seen_keys.update(srs["_key"])
    srs.drop(columns=["_key"], inplace=True)
    samples.append(srs)

    # 2) Operator-balanced boosters for the rare / decisive classes the SRS
    #    cannot cover. Common classes (docked, free-floating/A3) are validated
    #    from the SRS.
    samples.append(_sample(cat[cat["flag_A1"] == True], "A1_carsharing"))  # noqa: E712
    samples.append(_sample(cat[cat["flag_A2"] == True], "A2_placeholder"))  # noqa: E712

    if ablation is not None:
        meta_cols = [
            "system_id", "station_id", "lat", "lon", "station_type",
            "capacity", "operator_name", "city", "audit_confidence",
        ]
        flag_cols = [f"flag_A{i}" for i in range(1, 8) if f"flag_A{i}" in cat.columns]
        join_cols = [c for c in meta_cols + flag_cols if c in cat.columns]
        for cls, name in [
            ("FP_LEGACY", "A4_discordant_legacy"),
            ("FN_COMPOSITE", "A4_discordant_composite"),
        ]:
            pool = ablation[ablation["discordance_class"] == cls]
            if len(pool) > 0:
                merged = pool.merge(
                    cat[join_cols], on=["system_id", "station_id"], how="left",
                )
                # car-sharing terminates at Q0 (= A1) and never reaches the
                # geospatial node, so keep it out of the A4 strata.
                if "flag_A1" in merged.columns:
                    merged = merged[merged["flag_A1"] != True]  # noqa: E712
                samples.append(_sample(merged, name))

    if "flag_A5" in cat.columns:
        samples.append(_sample(
            cat[(cat["flag_A5"] == True) & (cat["flag_A1"] == False)],  # noqa: E712
            "A5_out_of_perimeter",
        ))

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

    # One empty column per decision-tree node (v2 schema, see QUESTIONS.md).
    # The Streamlit app writes answers to the DB, not to these columns; they
    # exist only for an optional manual-CSV workflow and for documentation.
    #   Q0 = 5-way type, Q2 ordinal dock count (si VLS à borne),
    #   Q3a perimeter valid, Q3b within network (si VLS à/sans borne).
    node_cols = [
        "Q0_type",              # vls_borne/vls_sans_borne/trottinettes/autopartage/rien/indéterminé
        "Q2_nb_docks_classe",   # 0/1-5/.../>50/indéterminé  (si Q0=vls_borne)
        "Q3a_perimetre",        # oui/non/indéterminé  (si Q0 vélo)
        "Q3b_proximite",        # oui/non/indéterminé  (si Q0 vélo)
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
