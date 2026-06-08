"""Inter-rater reliability + per-rule P/R for the human-validation campaign (v3).

Instrument (PROTOCOL.md / QUESTIONS.md), one routed question at a time:

    Q0  type de station — 5 entrées (VLS à borne / vélos sans borne /
        trottinettes / autopartage / rien)  -> A1, A3, hors-domaine, zombie
    Q2  combien de docks ? (ordinal, anti-ancrage; si VLS à borne)
    Q3a périmètre géographique valide ?   (si VLS à/sans borne)
    Q3b au contact du réseau ?            (si VLS à/sans borne)

Per-rule "anomaly is real" is decided by **predicate functions** of the
adjudicated ground truth AND the feed-declared attributes (capacity), never
from the raw physical fact alone — so a legitimate free-floating point
(no dock, small declared capacity) is NOT counted as a missed A3, and a
zero-capacity dock is A6 only when docks are actually present. This is the
correction raised in methodological review.

Usage:
    python -m experiments.human_validation.compute_reliability \
        --labels1 experiments/human_validation/labels_rohan.csv \
        --labels2 experiments/human_validation/labels_gael.csv \
        --output  experiments/human_validation/reliability_report.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_DIR = Path(__file__).resolve().parent

NODE_COLS = ["Q0_type", "Q2_nb_docks_classe", "Q3a_perimetre", "Q3b_proximite"]

# Q0 type canonical values (mirror annotator_app.TYPE_OPTIONS); "indéterminé"
# is normalised to "indet" by _norm.
TYPE_VALUES = {"vls_borne", "vls_sans_borne", "trottinettes", "autopartage", "rien"}

# Ordinal dock-count classes -> numeric (lo, hi). Accept en-dash and hyphen.
DOCK_RANGE = {
    "0": (0, 0),
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
    """Car-sharing labelled as bike-share: real iff the type is autopartage."""
    t = g.get("Q0_type")
    return (t == "autopartage") if t in TYPE_VALUES else None


def _pred_A3(g, feed):
    """No physical dock on the ground (genuine free-floating).

    With the 5-way type node, A3 is real exactly when the annotator typed the
    station as free-floating bikes (``vls_sans_borne``): the defect is the feed
    presenting that point as a dock with capacity, so flagging it is correct.
    A dock-based station (``vls_borne``) is a true negative."""
    t = g.get("Q0_type")
    return (t == "vls_sans_borne") if t in TYPE_VALUES else None


def _pred_A6(g, feed):
    """Docks present on the ground BUT the feed declares capacity 0."""
    t = g.get("Q0_type")
    if t not in TYPE_VALUES:
        return None
    c = _cap(feed)
    if c is None:
        return None
    return bool(t == "vls_borne" and c == 0)


def _pred_A2(g, feed):
    """Observed dock count inconsistent with the declared capacity (+/-50%).

    Q2 is now a raw numeric estimate (string of an int) or 'indet'."""
    v = g.get("Q2_nb_docks_classe")
    if not v or v == "indet":
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    c = _cap(feed)
    if c is None:
        return None
    return not (0.5 * c <= n <= 1.5 * c)


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


def gwet_ac1(pairs) -> float:
    """Gwet's AC1 (nominal). Robust to the prevalence/marginal paradox that
    deflates kappa/alpha on stratified samples where one category dominates
    (e.g. an A1 stratum that is ~96% car-sharing). Reported as the primary
    chance-corrected coefficient alongside raw agreement Po."""
    units = [(a, b) for a, b in pairs if a not in (None, "") and b not in (None, "")]
    n = len(units)
    if n < 2:
        return float("nan")
    cats = sorted({v for pr in units for v in pr})
    q = len(cats)
    po = sum(1 for a, b in units if a == b) / n
    if q < 2:
        return 1.0 if po == 1.0 else float("nan")
    pi = {c: sum((a == c) + (b == c) for a, b in units) / (2 * n) for c in cats}
    pe = sum(p * (1 - p) for p in pi.values()) / (q - 1)
    if pe >= 1.0:
        return 1.0 if po == 1.0 else 0.0
    return float((po - pe) / (1 - pe))


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
    t = ans.get("Q0_type")
    found = t in ("vls_borne", "vls_sans_borne", "trottinettes", "autopartage")
    return {
        "Q0_type": True,
        "Q2_nb_docks_classe": t == "vls_borne",
        "Q3a_perimetre": found,
        "Q3b_proximite": found,
    }


def verdict(ans: dict) -> str:
    t = ans.get("Q0_type")
    if t == "rien":
        return "ZOMBIE"
    if t not in ("vls_borne", "vls_sans_borne", "trottinettes", "autopartage"):
        return "INDET"
    type_part = {"vls_borne": "DOCK", "vls_sans_borne": "FLOAT",
                 "trottinettes": "TROT", "autopartage": "A1"}[t]
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
    """Per-node inter-rater reliability on co-routed units.

    Pairs where either rater answered 'indet' are EXCLUDED from the
    chance-corrected coefficients (agreeing on "we can't tell" is not agreement
    on the station); the indeterminate rate is reported separately as an
    instrument-quality metric. Gwet's AC1 is the primary coefficient (robust to
    the prevalence paradox); kappa/alpha and the modal-class share are reported
    alongside so the paradox is visible."""
    out = {}
    for node in NODE_COLS:
        corouted, decidable = 0, []
        for _, r in merged.iterrows():
            a1, a2 = _answers(r, "_a1"), _answers(r, "_a2")
            if reached(a1).get(node) and reached(a2).get(node) and a1[node] and a2[node]:
                corouted += 1
                if a1[node] != "indet" and a2[node] != "indet":
                    decidable.append((a1[node], a2[node]))
        if len(decidable) < 2:
            out[node] = {"n_corouted": corouted, "n_decidable": len(decidable),
                         "note": "insufficient decidable co-routed units"}
            continue
        a = [x for x, _ in decidable]
        b = [y for _, y in decidable]
        modal = max(Counter(a + b).values()) / (2 * len(decidable))
        out[node] = {
            "n_corouted": corouted,
            "n_decidable": len(decidable),
            "indeterminate_rate": round((corouted - len(decidable)) / corouted, 3),
            "raw_agreement": round(float(np.mean([x == y for x, y in decidable])), 3),
            "modal_class_share": round(modal, 3),
            "gwet_ac1": round(gwet_ac1(decidable), 3),
            "krippendorff_alpha": round(krippendorff_alpha_nominal(decidable), 3),
            "cohens_kappa": round(cohens_kappa(a, b), 3),
        }
    return out


def verdict_agreement(merged: pd.DataFrame) -> dict:
    pairs = [(verdict(_answers(r, "_a1")), verdict(_answers(r, "_a2")))
             for _, r in merged.iterrows()]
    flat = [v for pr in pairs for v in pr]
    modal = (max(Counter(flat).values()) / len(flat)) if flat else float("nan")
    return {
        "n": len(pairs),
        "raw_agreement": round(float(np.mean([a == b for a, b in pairs])), 3),
        "modal_class_share": round(modal, 3),
        "gwet_ac1": round(gwet_ac1(pairs), 3),
        "krippendorff_alpha": round(krippendorff_alpha_nominal(pairs), 3),
        "cohens_kappa": round(cohens_kappa([a for a, _ in pairs], [b for _, b in pairs]), 3),
        "note": "descriptive secondary endpoint; per-question AC1 is primary",
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


def _pr_from_records(records):
    """records: list of (flagged: bool, real: bool) -> (precision, recall, tp, fp, fn)."""
    tp = sum(1 for f, r in records if f and r)
    fp = sum(1 for f, r in records if f and not r)
    fn = sum(1 for f, r in records if (not f) and r)
    prec = tp / (tp + fp) if (tp + fp) else float("nan")
    rec = tp / (tp + fn) if (tp + fn) else float("nan")
    return prec, rec, tp, fp, fn


def cluster_bootstrap_pr(sys_records, n_boot=2000, seed=42):
    """Cluster-robust 95% CIs for precision/recall, resampling whole SYSTEMS
    with replacement (stations within a system are not i.i.d.: they share the
    operator's encoding logic). Returns None if fewer than 2 systems."""
    systems = list(sys_records.keys())
    if len(systems) < 2:
        return None
    rng = np.random.default_rng(seed)
    precs, recs = [], []
    for _ in range(n_boot):
        idx = rng.integers(0, len(systems), size=len(systems))
        boot = []
        for j in idx:
            boot.extend(sys_records[systems[j]])
        p, r, _, _, _ = _pr_from_records(boot)
        if not np.isnan(p):
            precs.append(p)
        if not np.isnan(r):
            recs.append(r)

    def _ci(vals):
        if len(vals) < 2:
            return [None, None]
        return [round(float(np.percentile(vals, 2.5)), 3),
                round(float(np.percentile(vals, 97.5)), 3)]
    return {"precision_cluster_ci": _ci(precs), "recall_cluster_ci": _ci(recs)}


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
        records = []                      # (flagged, real)
        sys_records = defaultdict(list)   # system_id -> [(flagged, real)] for clustering
        for _, r in m.iterrows():
            g = {n: r.get(f"gold_{n}") for n in NODE_COLS}
            real = pred(g, r)
            if real is None:
                continue
            flagged = bool(r[flag_col])
            records.append((flagged, real))
            sys_records[str(r.get("system_id"))].append((flagged, real))
        if not records:
            results[rule] = {"note": "no assessable stations"}
            continue
        prec, rec, tp, fp, fn = _pr_from_records(records)
        tn = sum(1 for f, rl in records if (not f) and (not rl))
        _, plo, phi = wilson_ci(tp, tp + fp)
        _, rlo, rhi = wilson_ci(tp, tp + fn)
        f1 = (2 * prec * rec / (prec + rec)
              if (not np.isnan(prec) and not np.isnan(rec) and (prec + rec)) else 0.0)
        entry = {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "n_systems": len(sys_records),
            "precision": None if np.isnan(prec) else round(prec, 3),
            "precision_wilson_ci": [round(plo, 3), round(phi, 3)],
            "recall": None if np.isnan(rec) else round(rec, 3),
            "recall_wilson_ci": [round(rlo, 3), round(rhi, 3)],
            "f1": round(f1, 3),
        }
        cb = cluster_bootstrap_pr(sys_records)
        if cb:
            entry.update(cb)
        results[rule] = entry

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


def raw_confusion(merged: pd.DataFrame) -> dict:
    """Per-node raw inter-rater confusion BEFORE adjudication, released so any
    reviewer can recompute alternative bounds (e.g. a pessimistic one)."""
    out = {}
    for node in NODE_COLS:
        cells = defaultdict(int)
        for _, r in merged.iterrows():
            a1, a2 = _answers(r, "_a1"), _answers(r, "_a2")
            if reached(a1).get(node) and reached(a2).get(node) and a1[node] and a2[node]:
                cells[f"{a1[node]} | {a2[node]}"] += 1
        if cells:
            out[node] = dict(sorted(cells.items(), key=lambda kv: -kv[1]))
    return out


def fatigue_drift(l1: pd.DataFrame, l2: pd.DataFrame) -> dict:
    """Attention-drift check: Mann-Whitney on per-station duration, first vs
    last quartile of each annotator's chronological sequence."""
    out = {}
    for name, df in (("a1", l1), ("a2", l2)):
        if "duration_s" not in df.columns or "created_at" not in df.columns:
            out[name] = {"note": "no timing data"}
            continue
        d = df.dropna(subset=["duration_s", "created_at"]).sort_values("created_at")
        d = d[d["duration_s"] > 0]
        if len(d) < 8:
            out[name] = {"note": "insufficient data", "n": int(len(d))}
            continue
        qn = len(d) // 4
        q1 = d["duration_s"].iloc[:qn].to_numpy()
        q4 = d["duration_s"].iloc[-qn:].to_numpy()
        try:
            p = float(stats.mannwhitneyu(q1, q4, alternative="two-sided").pvalue)
        except Exception:  # noqa: BLE001
            p = float("nan")
        out[name] = {"n": int(len(d)),
                     "median_q1_s": round(float(np.median(q1)), 1),
                     "median_q4_s": round(float(np.median(q4)), 1),
                     "mannwhitney_p": None if np.isnan(p) else round(p, 4)}
    return out


def sv_date_sensitivity(merged: pd.DataFrame, sample: pd.DataFrame,
                        audit_year: int, max_gap: int = 2) -> dict:
    """Re-run per-rule P/R on the subset whose Street View imagery is within
    `max_gap` years of the audit, so stale-imagery disagreements (an instrument
    error, not a pipeline FP) do not contaminate the headline numbers."""
    def _recent(r):
        d = str(r.get("sv_date_a1") or r.get("sv_date_a2") or "")
        return d[:4].isdigit() and (audit_year - int(d[:4])) <= max_gap
    mask = merged.apply(_recent, axis=1)
    sub = merged[mask]
    res = {"audit_year": audit_year, "max_gap_years": max_gap,
           "n_total": int(len(merged)), "n_recent": int(len(sub)),
           "n_excluded_stale": int(len(merged) - len(sub))}
    if len(sub) >= 2:
        res["precision_recall_recent"] = precision_recall(adjudicate(sub), sample)
    return res


def prevalence_srs(sample: pd.DataFrame) -> dict:
    """Catalogue-level prevalence of each flag, on the random_prevalence (SRS)
    stratum ONLY, with Wilson 95% intervals. The booster strata over-represent
    rare classes by design and must not enter this estimate."""
    if "stratum" not in sample.columns:
        return {"note": "no stratum column"}
    srs = sample[sample["stratum"] == "random_prevalence"]
    n = int(len(srs))
    if n == 0:
        return {"n_srs": 0, "note": "no random_prevalence stratum in sample"}
    rates = {}
    for i in range(1, 8):
        c = f"flag_A{i}"
        if c in srs.columns:
            k = int(srs[c].astype(bool).sum())
            p, lo, hi = wilson_ci(k, n)
            rates[f"A{i}"] = {"k": k, "rate": round(p, 3),
                              "wilson_ci": [round(lo, 3), round(hi, 3)]}
    return {"n_srs": n, "flag_prevalence": rates}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--labels1", required=True)
    p.add_argument("--labels2", required=True)
    p.add_argument("--sample", default=str(_DIR / "sample.csv"))
    p.add_argument("--audit-year", type=int, default=2026,
                   help="Flux/audit reference year for the Street-View staleness filter.")
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
        "raw_interrater_confusion": raw_confusion(merged),
        "catalogue_prevalence_srs": prevalence_srs(sample),
        "precision_recall": precision_recall(adjudicate(merged), sample),
        "sv_date_sensitivity": sv_date_sensitivity(merged, sample, args.audit_year),
        "fatigue_drift": fatigue_drift(l1, l2),
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Human-validation reliability ({len(merged)} co-rated stations)\n")
    v = report["verdict_agreement"]
    print(f"Composite verdict (secondary): AC1={v['gwet_ac1']:.3f} "
          f"alpha={v['krippendorff_alpha']:.3f} Po={v['raw_agreement']:.0%} (n={v['n']})\n")
    print("Per question (co-routed) — PRIMARY = Gwet AC1 (Po and modal share shown "
          "so the kappa paradox is visible):")
    for node, info in report["per_question_agreement"].items():
        if "gwet_ac1" in info:
            print(f"  {node}: AC1={info['gwet_ac1']:.3f} alpha={info['krippendorff_alpha']:.3f} "
                  f"kappa={info['cohens_kappa']:.3f} | Po={info['raw_agreement']:.0%} "
                  f"modal={info['modal_class_share']:.0%} indet={info['indeterminate_rate']:.0%} "
                  f"(n={info['n_decidable']}/{info['n_corouted']})")
        else:
            print(f"  {node}: {info['note']} (n={info['n_corouted']})")
    print("\nPer-rule P/R:")
    for rule in [f"A{i}" for i in range(1, 8)]:
        info = report["precision_recall"].get(rule)
        if info and info.get("precision") is not None and info.get("recall") is not None:
            cc = info.get("precision_cluster_ci")
            cc_s = f" clusterCI={cc}" if cc else ""
            print(f"  {rule}: P={info['precision']:.2f} R={info['recall']:.2f} "
                  f"F1={info['f1']:.2f} (TP={info['tp']} FP={info['fp']} FN={info['fn']}, "
                  f"{info['n_systems']} systèmes){cc_s}")
    print(f"\nReport saved to {out}")


if __name__ == "__main__":
    main()
