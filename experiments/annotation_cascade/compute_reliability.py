"""Inter-rater reliability + per-rule P/R for the cascade campaign (v3).

Instrument (PROTOCOL.md / QUESTIONS.md), one routed question at a time:

    Q0  libre-service vélo/trottinette ?  (gate)        -> non => A1
    Q1  docks physiques présents ?        (si Q0=oui)
    Q2  combien de docks ? (échelle ordinale, anti-ancrage; si Q1=oui)
    Q3a périmètre géographique valide ?   (si Q0=oui)
    Q3b au contact du réseau ?            (si Q0=oui)

Per-rule "anomaly is real" is decided by **predicate functions** of the
adjudicated ground truth AND the feed-declared attributes (capacity), never
from the raw physical fact alone — so a legitimate free-floating point
(no dock, small declared capacity) is NOT counted as a missed A3, and a
zero-capacity dock is A6 only when docks are actually present. This is the
correction raised in methodological review.

Usage:
    python -m experiments.annotation_cascade.compute_reliability \
        --labels1 experiments/annotation_cascade/labels_rohan.csv \
        --labels2 experiments/annotation_cascade/labels_gael.csv \
        --output  experiments/annotation_cascade/reliability_report.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_DIR = Path(__file__).resolve().parent

NODE_COLS = ["Q0_libre_service", "Q1_docks_presents", "Q2_nb_docks_classe",
             "Q3a_perimetre", "Q3b_proximite"]

# Ordinal dock-count classes -> numeric (lo, hi). Accept en-dash and hyphen.
DOCK_RANGE = {
    "1–5": (1, 5), "6–10": (6, 10), "11–20": (11, 20), "21–30": (21, 30),
    "31–50": (31, 50), ">50": (51, 10**9),
    "1-5": (1, 5), "6-10": (6, 10), "11-20": (11, 20), "21-30": (21, 30),
    "31-50": (31, 50),
}

_NORM = {
    "oui": "yes", "yes": "yes", "non": "no", "no": "no",
    "indetermine": "indet", "indéterminé": "indet", "indeterminate": "indet",
    "indet": "indet",
}


def _norm(v) -> str:
    """Binary answers -> {yes,no,indet}; ordinal class strings pass through."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return _NORM.get(s.lower(), "" if s.lower() in {"", "nan", "skipped"} else s)


# ---------------------------------------------------------------------------
# Per-rule predicate functions: (gold_answers, feed_row) -> bool | None
#   True  = the flagged anomaly is real on this station
#   None  = not assessable (no usable answer / missing feed value)
# ---------------------------------------------------------------------------

def _cap(feed) -> float | None:
    c = feed.get("capacity")
    try:
        c = float(c)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(c) else c


def _pred_A1(g, feed):
    q0 = g.get("Q0_libre_service")
    return (q0 == "no") if q0 in ("yes", "no") else None


def _pred_A3(g, feed):
    """No physical dock on the ground.

    In this catalogue station_type==free_floating <=> flag_A3, i.e. A3 is the
    systematic re-typing of free-floating fleets: flagging a genuine
    free-floating point is the *correct* behaviour (the defect is the feed
    presenting it as a dock with capacity). So "A3 is real" is exactly
    "no physical dock", validating A3's precision. (If a future rule stops
    auto-flagging all free-floating, re-introduce a feed-declared-capacity
    condition here.)"""
    q1 = g.get("Q1_docks_presents")
    return (q1 == "no") if q1 in ("yes", "no") else None


def _pred_A6(g, feed):
    """Docks present on the ground BUT the feed declares capacity 0."""
    q1 = g.get("Q1_docks_presents")
    if q1 not in ("yes", "no"):
        return None
    c = _cap(feed)
    if c is None:
        return None
    return bool(q1 == "yes" and c == 0)


def _pred_A2(g, feed):
    """Observed dock count inconsistent with declared capacity (±50%)."""
    cls = g.get("Q2_nb_docks_classe")
    if not cls or cls in ("indet",) or cls not in DOCK_RANGE:
        return None
    c = _cap(feed)
    if c is None:
        return None
    lo, hi = DOCK_RANGE[cls]
    match = (0.5 * lo) <= c <= (1.5 * hi)
    return not match


def _pred_A4(g, feed):
    q = g.get("Q3b_proximite")
    return (q == "no") if q in ("yes", "no") else None


def _pred_A5(g, feed):
    q = g.get("Q3a_perimetre")
    return (q == "no") if q in ("yes", "no") else None


RULE_PREDICATES = {
    "A1": _pred_A1, "A2": _pred_A2, "A3": _pred_A3,
    "A4": _pred_A4, "A5": _pred_A5, "A6": _pred_A6,
}
SYSTEM_LEVEL_RULES = ["A7"]


# ---------------------------------------------------------------------------
# Reliability primitives
# ---------------------------------------------------------------------------

def cohens_kappa(y1, y2) -> float:
    classes = sorted(set(y1) | set(y2))
    n = len(y1)
    if n == 0:
        return float("nan")
    idx = {c: i for i, c in enumerate(classes)}
    conf = np.zeros((len(classes), len(classes)), dtype=int)
    for a, b in zip(y1, y2):
        conf[idx[a], idx[b]] += 1
    po = np.diag(conf).sum() / n
    pe = sum((conf[i, :].sum() / n) * (conf[:, i].sum() / n) for i in range(len(classes)))
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return float((po - pe) / (1 - pe))


def krippendorff_alpha_nominal(pairs) -> float:
    units = [(a, b) for a, b in pairs if a not in (None, "") and b not in (None, "")]
    if len(units) < 2:
        return float("nan")
    values = sorted({v for pair in units for v in pair})
    o: dict[tuple[str, str], float] = defaultdict(float)
    for a, b in units:
        o[(a, b)] += 1.0
        o[(b, a)] += 1.0
    n_c = {c: sum(o[(c, k)] for k in values) for c in values}
    n = sum(n_c.values())
    if n <= 1:
        return float("nan")
    do = sum(o[(c, k)] for c in values for k in values if c != k)
    de = sum(n_c[c] * n_c[k] for c in values for k in values if c != k) / (n - 1)
    if de == 0:
        return 1.0
    return float(1 - do / de)


def wilson_ci(succ, total, confidence=0.95):
    if total == 0:
        return 0.0, 0.0, 0.0
    p = succ / total
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    denom = 1 + z ** 2 / total
    center = (p + z ** 2 / (2 * total)) / denom
    half = z * np.sqrt(p * (1 - p) / total + z ** 2 / (4 * total ** 2)) / denom
    return float(p), float(max(0, center - half)), float(min(1, center + half))


# ---------------------------------------------------------------------------
# Routing & composite verdict (mirror annotator_app.derive_verdict)
# ---------------------------------------------------------------------------

def reached(ans: dict) -> dict:
    is_shared = ans.get("Q0_libre_service") == "yes"
    has_docks = ans.get("Q1_docks_presents") == "yes"
    return {
        "Q0_libre_service": True,
        "Q1_docks_presents": is_shared,
        "Q2_nb_docks_classe": is_shared and has_docks,
        "Q3a_perimetre": is_shared,
        "Q3b_proximite": is_shared,
    }


def verdict(ans: dict) -> str:
    q0 = ans.get("Q0_libre_service")
    if q0 == "no":
        return "A1"
    if q0 != "yes":
        return "INDET"
    q1 = ans.get("Q1_docks_presents")
    type_part = {"yes": "DOCK", "no": "NO_DOCKS"}.get(q1, "INDET")
    peri, prox = ans.get("Q3a_perimetre"), ans.get("Q3b_proximite")
    if peri == "no":
        place = "A5"
    elif prox == "no":
        place = "A4"
    elif peri == "yes" and prox == "yes":
        place = "PLACED"
    else:
        place = "PLACE_INDET"
    return f"{type_part}|{place}"


def _answers(row: pd.Series, suffix: str) -> dict:
    return {c: _norm(row.get(f"{c}{suffix}", "")) for c in NODE_COLS}


def merge_annotations(l1: pd.DataFrame, l2: pd.DataFrame) -> pd.DataFrame:
    return l1.merge(l2, on=["system_id", "station_id", "stratum"], suffixes=("_a1", "_a2"))


def per_question_agreement(merged: pd.DataFrame) -> dict:
    out = {}
    for node in NODE_COLS:
        pairs = []
        for _, r in merged.iterrows():
            a1, a2 = _answers(r, "_a1"), _answers(r, "_a2")
            if reached(a1).get(node) and reached(a2).get(node) and a1[node] and a2[node]:
                pairs.append((a1[node], a2[node]))
        if len(pairs) < 2:
            out[node] = {"n_corouted": len(pairs), "note": "insufficient co-routed units"}
            continue
        out[node] = {
            "n_corouted": len(pairs),
            "cohens_kappa": round(cohens_kappa([a for a, _ in pairs], [b for _, b in pairs]), 3),
            "krippendorff_alpha": round(krippendorff_alpha_nominal(pairs), 3),
            "raw_agreement": round(float(np.mean([a == b for a, b in pairs])), 3),
        }
    return out


def verdict_agreement(merged: pd.DataFrame) -> dict:
    pairs = [(verdict(_answers(r, "_a1")), verdict(_answers(r, "_a2")))
             for _, r in merged.iterrows()]
    return {
        "n": len(pairs),
        "cohens_kappa": round(cohens_kappa([a for a, _ in pairs], [b for _, b in pairs]), 3),
        "krippendorff_alpha": round(krippendorff_alpha_nominal(pairs), 3),
        "raw_agreement": round(float(np.mean([a == b for a, b in pairs])), 3),
        "note": "descriptive secondary endpoint; per-question alpha is primary",
    }


def routing_divergence_audit(merged: pd.DataFrame) -> dict:
    counts = defaultdict(int)
    for _, r in merged.iterrows():
        a1, a2 = _answers(r, "_a1"), _answers(r, "_a2")
        ra1, ra2 = reached(a1), reached(a2)
        first = "none"
        for node in NODE_COLS:
            if ra1.get(node) != ra2.get(node):
                first = f"{node} (routing)"
                break
            if ra1.get(node) and a1[node] != a2[node]:
                first = node
                break
        counts[first] += 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def adjudicate(merged: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in merged.iterrows():
        a1, a2 = _answers(r, "_a1"), _answers(r, "_a2")
        rec = {"system_id": r["system_id"], "station_id": r["station_id"],
               "stratum": r["stratum"]}
        for node in NODE_COLS:
            rec[f"gold_{node}"] = a1[node] if a1[node] == a2[node] else None
        rec["gold_verdict"] = verdict({n: rec[f"gold_{n}"] or "" for n in NODE_COLS})
        rows.append(rec)
    return pd.DataFrame(rows)


def precision_recall(gold: pd.DataFrame, sample: pd.DataFrame) -> dict:
    flag_cols = [f"flag_A{i}" for i in range(1, 8) if f"flag_A{i}" in sample.columns]
    join = ["system_id", "station_id", "stratum"]
    extra = [c for c in ["capacity", "station_type"] if c in sample.columns]
    m = gold.merge(sample[join + flag_cols + extra], on=join, how="left")

    results = {}
    for rule, pred in RULE_PREDICATES.items():
        flag_col = f"flag_{rule}"
        if flag_col not in m.columns:
            continue
        tp = fp = fn = tn = 0
        for _, r in m.iterrows():
            g = {n: r.get(f"gold_{n}") for n in NODE_COLS}
            real = pred(g, r)
            if real is None:
                continue
            flagged = bool(r[flag_col])
            if flagged and real:
                tp += 1
            elif flagged and not real:
                fp += 1
            elif (not flagged) and real:
                fn += 1
            else:
                tn += 1
        if tp + fp + fn + tn == 0:
            results[rule] = {"note": "no assessable stations"}
            continue
        prec, plo, phi = wilson_ci(tp, tp + fp)
        rec, rlo, rhi = wilson_ci(tp, tp + fn)
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        results[rule] = {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(prec, 3), "precision_ci": [round(plo, 3), round(phi, 3)],
            "recall": round(rec, 3), "recall_ci": [round(rlo, 3), round(rhi, 3)],
            "f1": round(f1, 3),
        }

    for rule in SYSTEM_LEVEL_RULES:
        flag_col = f"flag_{rule}"
        if flag_col in m.columns:
            fr = m[m[flag_col].astype(bool)]
            results[rule] = {
                "validation": "system-level (not imagery-validatable)",
                "n_flagged_stations_in_sample": int(len(fr)),
                "n_flagged_systems": int(fr["system_id"].nunique()),
            }

    # A4 ablation: legacy detector FP rate on its discordant stratum
    # = share judged at the network (Q3b = yes) by the humans.
    disc = m[(m["stratum"] == "A4_discordant_legacy")
             & (m["gold_Q3b_proximite"].isin(["yes", "no"]))]
    if len(disc) > 0:
        n_fp = int((disc["gold_Q3b_proximite"] == "yes").sum())
        rate, lo, hi = wilson_ci(n_fp, len(disc))
        results["A4_discordant_legacy_fp_rate"] = {
            "n_confirmed_fp": n_fp, "n_usable": int(len(disc)),
            "fp_rate": round(rate, 3), "wilson_ci": [round(lo, 3), round(hi, 3)],
        }
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--labels1", required=True)
    p.add_argument("--labels2", required=True)
    p.add_argument("--sample", default=str(_DIR / "sample.csv"))
    p.add_argument("--output", required=True)
    args = p.parse_args()

    l1, l2 = pd.read_csv(args.labels1), pd.read_csv(args.labels2)
    sample = pd.read_csv(args.sample)
    merged = merge_annotations(l1, l2)

    report = {
        "n_merged": int(len(merged)),
        "verdict_agreement": verdict_agreement(merged),
        "per_question_agreement": per_question_agreement(merged),
        "routing_divergence_first_question": routing_divergence_audit(merged),
        "precision_recall": precision_recall(adjudicate(merged), sample),
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Cascade reliability ({len(merged)} co-rated stations)\n")
    v = report["verdict_agreement"]
    print(f"Composite verdict (secondary): alpha={v['krippendorff_alpha']:.3f} "
          f"agree={v['raw_agreement']:.0%} (n={v['n']})\n")
    print("Per question (co-routed) — PRIMARY:")
    for node, info in report["per_question_agreement"].items():
        if "krippendorff_alpha" in info:
            print(f"  {node}: alpha={info['krippendorff_alpha']:.3f} "
                  f"kappa={info['cohens_kappa']:.3f} (n={info['n_corouted']})")
        else:
            print(f"  {node}: {info['note']} (n={info['n_corouted']})")
    print("\nPer-rule P/R:")
    for rule in [f"A{i}" for i in range(1, 8)]:
        info = report["precision_recall"].get(rule)
        if info and "precision" in info:
            print(f"  {rule}: P={info['precision']:.2f} R={info['recall']:.2f} "
                  f"F1={info['f1']:.2f} (TP={info['tp']} FP={info['fp']} FN={info['fn']})")
    print(f"\nReport saved to {out}")


if __name__ == "__main__":
    main()
