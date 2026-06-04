"""Inter-rater reliability + per-rule precision from the Supabase annotation export.

Adapted from ``compute_reliability.py`` (legacy Q1-Q5 schema) to the current
Streamlit / Supabase schema, while preserving the **strictly pipeline-agnostic**
methodology of PROTOCOL.md v3.0: annotators judge the real-world state of each
station; per-rule TP/FP are derived a posteriori from the adjudicated factual
answers, never from a pipeline-referencing verdict.

Schema mapping (Supabase columns  ->  protocol factual questions)
----------------------------------------------------------------
    ground_reality       -> Q1 (is bikeshare?)  and  Q3 (physical infra exists?)
        station_vls            : bikeshare, station physically present
        autopartage            : car-sharing  (Q1 = no)
        trottinettes           : e-scooters   (Q1 = no)
        aucune_infrastructure  : nothing on site (Q3 = no)
        indetermine            : unusable
    location_assessment  -> Q4 (within operator perimeter / position consistent?)
        integree_reseau, isolee_legitime      : within  (Q4 = yes)
        isolee_suspecte, coordonnees_erronees : aberrant (Q4 = no)
        champ_vide                            : unusable
    capacity_assessment  -> Q2 (capacity coherent?)  [reliability only]
    verdict              -> holistic synthesis (legitime / problematique / indetermine)

Pipeline positive prediction
----------------------------
The validation sample is stratified by the rule that flagged each station
(PROTOCOL.md sampling table), so **stratum membership is the pipeline's positive
prediction** for that rule. The raw flag_a* columns are NOT used for the join:
they overlap across rules (e.g. flag_a4 rarely fires on the A4 strata; A4 rows
mostly carry flag_a3/flag_a7), so joining on them would misattribute predictions.

Per-rule "anomaly is real" predicates (imagery-validatable rules)
-----------------------------------------------------------------
    A1 (out-of-domain)      real <=> ground_reality in {autopartage, trottinettes}
    A3 (free-floating)      real <=> ground_reality == aucune_infrastructure
    A4 (geospatial outlier) real <=> location_assessment in {isolee_suspecte, coordonnees_erronees}
    A5 (out-of-perimeter)   real <=> location_assessment in {isolee_suspecte, coordonnees_erronees}
    A6 (zero-capacity dock) real <=> ground_reality == aucune_infrastructure   (empty in v1.0)

A2 (placeholder capacity) and A7 (null capacity) are structural, system-level
properties (precision = 1 by construction, not imagery-validatable) -> reported
as affected-system counts, per protocol.

Decision: ``isolee_legitime`` counts as a FALSE POSITIVE for A4/A5 (position
"not aberrant"). Per PROTOCOL.md a true positive is a flagged coordinate the
human judges OUT of perimeter (a real error); a station that is geographically
isolated but legitimate is not a data error, so flagging it is a false positive.
Because A4/A5 fire mostly on free-floating operators (no fixed station, where
"coordinate outlier" is ill-posed), per-rule precision is also reported split by
anchor type, and the physically-anchored subset is the well-defined population.

Recall note
-----------
A precision-stratified sample does not support unbiased per-rule recall without
catalogue base rates. We report what IS derivable: per-rule **precision** with
Wilson 95% CIs, plus the false-negative rate on the ``clean_docked`` negative
control (stations the pipeline did NOT flag that the human judges problematic).

capacity_assessment harmonisation
---------------------------------
The two annotators coded capacity on divergent category sets (Gael: binary
coherente/impossible; Rohan: 4-way incl. data-properties champ_vide/placeholder),
so the raw field is not co-validated (kappa ~ 0.08). The only cross-annotator
coherent projection is the **assessable** axis: 'non_assessable' iff the value is
'impossible' (annotator could not judge), else 'assessable'. This is reported as
the capacity reliability figure; no analytic claim is built on the raw field.

Usage:
    python experiments/annotation/compute_reliability_supabase.py \
        --input annotations_supabase_clean.csv \
        --output experiments/annotation/reliability_supabase.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

# --- z for Wilson 95% CI (avoids a scipy dependency) ---
_Z95 = 1.959963984540054

# --- Harmonised binary factual axes -------------------------------------
# The two annotators describe the same reality at different granularity
# (Rohan codes 'autopartage' where Gael codes 'aucune_infrastructure'; both
# mean "no real docked bike station"). Adjudicating on the raw multi-class
# field therefore destroys genuine agreement. We collapse each factual field
# to the binary axis the protocol actually asks about, then adjudicate on
# that. This is the same principled projection used for capacity_assessment.
#
#   bike_station_present (Q1+Q3):  'yes' iff ground_reality == station_vls
#                                  'no'  iff in {autopartage, trottinettes,
#                                                aucune_infrastructure}
#                                  None  iff indetermine (unusable)
#   position_aberrant (Q4):        'yes' iff location in {isolee_suspecte,
#                                                         coordonnees_erronees}
#                                  'no'  iff in {integree_reseau, isolee_legitime}
#                                  None  iff champ_vide (unusable)

def axis_bike_station(ground_reality):
    v = (ground_reality or "").strip()
    if v == "station_vls":
        return "yes"
    if v in {"autopartage", "trottinettes", "aucune_infrastructure"}:
        return "no"
    return None  # indetermine / empty -> unusable


def axis_position_aberrant(location):
    v = (location or "").strip()
    if v in {"isolee_suspecte", "coordonnees_erronees"}:
        return "yes"
    if v in {"integree_reseau", "isolee_legitime"}:
        return "no"
    return None  # champ_vide / empty -> unusable


# Per stratum: (rule, harmonised axis, value-meaning-"anomaly is real").
# Stratum membership is the pipeline's positive prediction (sample design).
STRATUM_PRED = {
    "A1_carsharing":          ("A1", axis_bike_station,      "no"),
    "A3_freefloating":        ("A3", axis_bike_station,      "no"),
    "A5_out_of_perimeter":    ("A5", axis_position_aberrant, "yes"),
    "A4_agree_flag":          ("A4", axis_position_aberrant, "yes"),
    "A4_discordant_composite":("A4", axis_position_aberrant, "yes"),
    "A4_discordant_legacy":   ("A4", axis_position_aberrant, "yes"),
}
SYSTEM_LEVEL_RULES = ["A2", "A7"]


# =====================================================================
# Stats helpers (pure-python, no numpy/scipy/pandas)
# =====================================================================

def cohens_kappa(pairs):
    y1 = [a for a, _ in pairs]
    y2 = [b for _, b in pairs]
    classes = sorted(set(y1) | set(y2))
    n = len(pairs)
    if n == 0:
        return float("nan"), float("nan")
    idx = {c: i for i, c in enumerate(classes)}
    m = [[0] * len(classes) for _ in classes]
    for a, b in pairs:
        m[idx[a]][idx[b]] += 1
    po = sum(m[i][i] for i in range(len(classes))) / n
    pe = sum(
        (sum(m[i]) / n) * (sum(m[j][i] for j in range(len(classes))) / n)
        for i in range(len(classes))
    )
    k = 1.0 if (po == 1.0) else ((po - pe) / (1 - pe) if pe != 1 else 0.0)
    return k, po


def krippendorff_alpha_nominal(pairs):
    units = [(a, b) for a, b in pairs if a is not None and b is not None]
    if len(units) < 2:
        return float("nan")
    values = sorted({v for pair in units for v in pair})
    o = defaultdict(float)
    for a, b in units:
        o[(a, b)] += 1.0
        o[(b, a)] += 1.0
    n_c = {c: sum(o[(c, k)] for k in values) for c in values}
    n = sum(n_c.values())
    if n <= 1:
        return float("nan")
    do = sum(o[(c, k)] for c in values for k in values if c != k)
    de = sum(n_c[c] * n_c[k] for c in values for k in values if c != k) / (n - 1)
    return 1.0 if de == 0 else float(1 - do / de)


def wilson_ci(successes, total, z=_Z95):
    if total == 0:
        return 0.0, 0.0, 0.0
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


# =====================================================================
# Load + pair
# =====================================================================

def harmonise_capacity(value):
    """Only cross-annotator-coherent projection of capacity_assessment."""
    return "non_assessable" if value == "impossible" else "assessable"


def load_pairs(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by = defaultdict(dict)
    for r in rows:
        if r["annotator"] in ("rohan", "gael") and r["verdict"] != "skipped":
            by[(r["system_id"], r["station_id"], r["stratum"])][r["annotator"]] = r
    pairs = [v for v in by.values() if "rohan" in v and "gael" in v]
    return rows, pairs


# =====================================================================
# Reliability + adjudication
# =====================================================================

_IAA_FIELDS = {
    # Raw multi-class fields (reported for transparency).
    "verdict": lambda r: r["verdict"],
    "ground_reality": lambda r: r["ground_reality"],
    "location_assessment": lambda r: r["location_assessment"],
    # Harmonised binary axes (what the per-rule derivation actually uses).
    "bike_station_present": lambda r: axis_bike_station(r["ground_reality"]) or "na",
    "position_aberrant": lambda r: axis_position_aberrant(r["location_assessment"]) or "na",
    "capacity_assessable": lambda r: harmonise_capacity(r["capacity_assessment"]),
}


def compute_agreement(pairs):
    out = {}
    for name, getter in _IAA_FIELDS.items():
        vals = [(getter(v["rohan"]), getter(v["gael"])) for v in pairs]
        k, po = cohens_kappa(vals)
        out[name] = {
            "cohens_kappa": round(k, 3),
            "krippendorff_alpha": round(krippendorff_alpha_nominal(vals), 3),
            "raw_agreement": round(po, 3),
            "n": len(vals),
        }
    return out


def adjudicate_axis(pairs, axis_fn):
    """Consensus gold per station on a harmonised binary axis.

    Returns 'yes'/'no' when both annotators map to the same axis value,
    None on disagreement, and marks unusable when either side is unusable.
    """
    gold = {}
    for v in pairs:
        a = axis_fn(v["rohan"][_AXIS_SOURCE[axis_fn]])
        b = axis_fn(v["gael"][_AXIS_SOURCE[axis_fn]])
        key = (v["rohan"]["system_id"], v["rohan"]["station_id"], v["rohan"]["stratum"])
        if a is None or b is None:
            gold[key] = "unusable"
        else:
            gold[key] = a if a == b else None
    return gold


# Which source column each axis function reads.
_AXIS_SOURCE = {
    axis_bike_station: "ground_reality",
    axis_position_aberrant: "location_assessment",
}


def adjudicate(pairs, field):
    """Consensus gold per station on a raw field: value if both agree, else None."""
    gold = {}
    for v in pairs:
        a, b = v["rohan"][field].strip(), v["gael"][field].strip()
        key = (v["rohan"]["system_id"], v["rohan"]["station_id"], v["rohan"]["stratum"])
        gold[key] = a if a == b else None
    return gold


# =====================================================================
# Per-rule precision (stratum = pipeline positive)
# =====================================================================

def compute_precision(pairs):
    # Adjudicate the two harmonised factual axes once.
    gold_axis = {
        axis_bike_station: adjudicate_axis(pairs, axis_bike_station),
        axis_position_aberrant: adjudicate_axis(pairs, axis_position_aberrant),
    }

    by_stratum = defaultdict(list)
    for v in pairs:
        key = (v["rohan"]["system_id"], v["rohan"]["station_id"], v["rohan"]["stratum"])
        by_stratum[v["rohan"]["stratum"]].append(key)

    results = {}

    # Per-stratum precision (the meaningful unit: A4 sub-strata differ).
    for stratum, (rule, axis_fn, real_value) in STRATUM_PRED.items():
        gold = gold_axis[axis_fn]
        tp = fp = n_un = n_dis = 0
        for key in by_stratum.get(stratum, []):
            g = gold[key]
            if g == "unusable":
                n_un += 1
            elif g is None:
                n_dis += 1
            elif g == real_value:
                tp += 1
            else:
                fp += 1
        p, lo, hi = wilson_ci(tp, tp + fp) if (tp + fp) else (0.0, 0.0, 0.0)
        results[stratum] = {
            "rule": rule,
            "axis": _AXIS_SOURCE[axis_fn],
            "tp": tp, "fp": fp,
            "n_disagree_excluded": n_dis, "n_unusable_excluded": n_un,
            "n_usable": tp + fp,
            "precision": round(p, 3),
            "precision_ci": [round(lo, 3), round(hi, 3)],
        }

    # Anchor breakdown for the geographic rules. A4/A5 detect coordinate
    # outliers, but most flagged stations are free-floating (no fixed station),
    # where "coordinate outlier" is ill-posed. We split each geographic stratum
    # by anchor type (physical docked station vs free-floating) using the
    # adjudicated bike_station_present axis, and report the position-aberrant
    # (true-positive) rate within the *physically anchored* subset -- the
    # population for which the geographic rule is well-defined.
    gb = gold_axis[axis_bike_station]
    gp = gold_axis[axis_position_aberrant]
    geo_strata = [s for s, (r, *_ ) in STRATUM_PRED.items() if r in ("A4", "A5")]
    anchor = {"A4": {"physical": [0, 0], "freefloating": [0, 0]},
              "A5": {"physical": [0, 0], "freefloating": [0, 0]}}  # [tp, fp]
    ff_share = {}
    for stratum in geo_strata:
        rule = STRATUM_PRED[stratum][0]
        n_ff = n_phys = 0
        for key in by_stratum.get(stratum, []):
            anc = gb[key]
            pos = gp[key]
            if anc in (None, "unusable") or pos in (None, "unusable"):
                continue
            bucket = "physical" if anc == "yes" else "freefloating"
            if bucket == "physical":
                n_phys += 1
            else:
                n_ff += 1
            cell = anchor[rule][bucket]
            if pos == "yes":
                cell[0] += 1
            else:
                cell[1] += 1
        ff_share[stratum] = {"n_freefloating": n_ff, "n_physical": n_phys}
    anchor_report = {"freefloating_share_by_stratum": ff_share, "by_rule": {}}
    for rule, buckets in anchor.items():
        rr = {}
        for bucket, (tp, fp) in buckets.items():
            if tp + fp:
                p, lo, hi = wilson_ci(tp, tp + fp)
                rr[bucket] = {"tp": tp, "fp": fp, "n": tp + fp,
                              "precision": round(p, 3),
                              "precision_ci": [round(lo, 3), round(hi, 3)]}
            else:
                rr[bucket] = {"tp": tp, "fp": fp, "n": 0}
        anchor_report["by_rule"][rule] = rr
    results["geographic_anchor_breakdown"] = anchor_report

    # A4 legacy FP-rate ablation (the paper's core claim): a true FP is a
    # legacy-only flag the human judges in-perimeter (position not aberrant).
    n_fp = n_usable = 0
    for key in by_stratum.get("A4_discordant_legacy", []):
        g = gp[key]
        if g in (None, "unusable"):
            continue
        n_usable += 1
        if g == "no":  # not aberrant => within perimeter => true FP
            n_fp += 1
    if n_usable:
        rate, lo, hi = wilson_ci(n_fp, n_usable)
        results["A4_discordant_legacy_fp_rate"] = {
            "n_confirmed_fp": n_fp, "n_usable": n_usable,
            "fp_rate": round(rate, 3), "wilson_ci": [round(lo, 3), round(hi, 3)],
            "interpretation": "legacy-only flags the human judges in-perimeter (true FP).",
        }

    # A2 / A7 system-level counts.
    for rule in SYSTEM_LEVEL_RULES:
        stratum = {"A2": "A2_placeholder", "A7": "A7_null_capacity"}[rule]
        keys = by_stratum.get(stratum, [])
        systems = {k[0] for k in keys}
        results[rule] = {
            "validation": "system-level (not imagery-validatable)",
            "n_stations_in_sample": len(keys),
            "n_systems": len(systems),
            "note": "Structural data-property rule; precision=1 by construction.",
        }

    # Negative control: false negatives on clean_docked (pipeline negative).
    clean = by_stratum.get("clean_docked", [])
    gold_v = adjudicate(pairs, "verdict")
    miss = usable = dis = 0
    for key in clean:
        v = gold_v[key]
        if v is None:
            dis += 1
            continue
        usable += 1
        if v.strip() == "problematique":
            miss += 1
    if usable:
        rate, lo, hi = wilson_ci(miss, usable)
        results["clean_docked_false_negative"] = {
            "n_missed": miss, "n_usable": usable, "n_disagree": dis,
            "fn_rate": round(rate, 3), "wilson_ci": [round(lo, 3), round(hi, 3)],
            "interpretation": "unflagged 'clean' stations the human judges problematic.",
        }

    return results, gold_v


# =====================================================================
# Main
# =====================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="annotations_supabase_clean.csv")
    ap.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "reliability_supabase.json"),
    )
    args = ap.parse_args()

    rows, pairs = load_pairs(args.input)
    agreement = compute_agreement(pairs)
    metrics, gold_v = compute_precision(pairs)

    # Verdict consensus + indeterminate by stratum.
    n_consensus = sum(1 for v in gold_v.values() if v is not None)
    n_disagree = sum(1 for v in gold_v.values() if v is None)
    indet_by_stratum = {}
    by_stratum = defaultdict(list)
    for v in pairs:
        by_stratum[v["rohan"]["stratum"]].append(v)
    for stratum, grp in by_stratum.items():
        n_i = sum(
            1 for v in grp
            if v["rohan"]["verdict"] == v["gael"]["verdict"] == "indetermine"
        )
        if n_i:
            indet_by_stratum[stratum] = {"n_indeterminate": n_i, "n_total": len(grp)}

    report = {
        "input": args.input,
        "n_co_rated_stations": len(pairs),
        "agreement": agreement,
        "verdict_consensus": n_consensus,
        "verdict_disagreement": n_disagree,
        "indeterminate_by_stratum": indet_by_stratum,
        "precision_recall": metrics,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # ASCII-only console summary (Windows cp1252 safe).
    print(f"Inter-rater reliability ({len(pairs)} co-rated stations):")
    for name, info in agreement.items():
        print(f"  {name:20s}: kappa={info['cohens_kappa']:.3f} "
              f"alpha={info['krippendorff_alpha']:.3f} "
              f"agree={info['raw_agreement']:.0%} (n={info['n']})")
    print(f"\nVerdict: {n_consensus} consensus, {n_disagree} disagree")
    print("\nPer-stratum precision (stratum = pipeline positive, harmonised axis):")
    for stratum in STRATUM_PRED:
        info = metrics.get(stratum)
        if not info:
            continue
        ci = info["precision_ci"]
        print(f"  {stratum:26s} [{info['rule']}] P={info['precision']:.2f} "
              f"[{ci[0]:.2f}-{ci[1]:.2f}]  "
              f"(TP={info['tp']} FP={info['fp']}, n_usable={info['n_usable']}; "
              f"excl {info['n_disagree_excluded']}dis/{info['n_unusable_excluded']}un)")
    anc = metrics.get("geographic_anchor_breakdown")
    if anc:
        print("\nGeographic rules by anchor type (TP-rate where rule is well-defined):")
        for rule, buckets in anc["by_rule"].items():
            for bucket in ("physical", "freefloating"):
                b = buckets[bucket]
                if b["n"]:
                    ci = b.get("precision_ci", [0, 0])
                    print(f"  {rule} {bucket:13s}: P={b['precision']:.2f} "
                          f"[{ci[0]:.2f}-{ci[1]:.2f}] (TP={b['tp']} FP={b['fp']}, n={b['n']})")
                else:
                    print(f"  {rule} {bucket:13s}: n=0")
        ffshare = anc["freefloating_share_by_stratum"]
        print("  free-floating share: " + ", ".join(
            f"{s.replace('A4_','').replace('A5_','')}={v['n_freefloating']}/"
            f"{v['n_freefloating']+v['n_physical']}" for s, v in ffshare.items()))

    ab = metrics.get("A4_discordant_legacy_fp_rate")
    if ab:
        ci = ab["wilson_ci"]
        print(f"\n  A4 legacy FP-rate: {ab['fp_rate']:.2f} "
              f"[{ci[0]:.2f}-{ci[1]:.2f}] (FP={ab['n_confirmed_fp']}/{ab['n_usable']})")
    for rule in SYSTEM_LEVEL_RULES:
        info = metrics[rule]
        print(f"  {rule}: system-level, {info['n_stations_in_sample']} stations / "
              f"{info['n_systems']} systems")
    fn = metrics.get("clean_docked_false_negative")
    if fn:
        print(f"  clean control FN-rate: {fn['fn_rate']:.2f} "
              f"(missed {fn['n_missed']}/{fn['n_usable']})")
    print(f"\nReport saved to {out}")


if __name__ == "__main__":
    main()
