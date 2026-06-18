#!/usr/bin/env python3
"""Verify that the frozen global-sweep snapshot reproduces the manuscript's
global-projection numbers.

This snapshot (massive_audit_results.csv + massive_audit_summary.json) is the
2026-04 MobilityData-catalogue sweep used in the paper. Run:

    python verify_snapshot.py

It re-derives and ASSERTS every reported global number, including the A6 and
A7 semantic-warning counts. A6 and A7-exclusive require classifying each system
as docked / free-floating / car-sharing; this is done with the repository's own
operator-name heuristics (scripts/audit_live_systems.py, --infer-type), copied
verbatim below so the script is self-contained.
"""
import csv
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "massive_audit_results.csv")
SUMMARY = os.path.join(HERE, "massive_audit_summary.json")

N_MIN = 20          # N_MIN_DOCK in massive_audit.py
A7_PCT = 50.0       # capacity_nan_pct >= 50  (percent)
A6_PCT = 1.0        # tau_A6 = 1 % zero-capacity rate among docked stations

# --- operator-name heuristics, verbatim from scripts/audit_live_systems.py ---
_FF = re.compile(
    r"\b(dott|pony|bird|voi|bolt|lime|tier|spin|donkey|cooltra|felyx|whoosh|"
    r"free.?floating|share.?now|free.?now|free2move|ridedott|rideflash|wind|"
    r"circ|jump|e.?scooter|scooter|moped|trottinette)\b", re.I)
_CAR = re.compile(
    r"\b(citiz|carsharing|car.?sharing|car2go|zipcar|stadtmobil|flinkster|"
    r"edrive|car.?ship|teilauto|quickrent|2em|mybuxi|conficars|getaround|"
    r"sixt.?share|miles|cambio|ford.?carsharing|ubeeqo|virtuo|tribu|invers|"
    r"deer)\b", re.I)


def station_type(name, url):
    s = f"{name or ''} {url or ''}"
    if _CAR.search(s):
        return "carsharing"
    if _FF.search(s):
        return "free_floating"
    return "docked_bike"


def truthy(x):
    return str(x).strip().lower() not in ("", "0", "0.0", "false", "none", "nan")


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    rows = list(csv.DictReader(open(CSV)))
    summ = json.load(open(SUMMARY))
    ok = []

    def check(label, got, want):
        good = got == want
        ok.append(good)
        print(f"  [{'OK ' if good else 'XX '}] {label}: {got} (paper {want})")

    print("== Headline global numbers (massive_audit_summary.json) ==")
    check("systems audited", summ["total_audited"], 1509)
    check("reachable", summ["reachable"], 1420)
    check("publish station_information", summ["with_stations"], 917)
    check("flagged by A1-A5", summ["flagged_anomalies"], 204)

    print("\n== Per-country A1-A5 breakdown (Table global-audit / S6) ==")
    fr = summ["by_country"]["FR"]
    check("FR audited/reachable/flagged",
          (fr["audited"], fr["reachable"], fr["flagged"]), (255, 253, 38))
    check("FR (A1,A2,A3,A4,A5)",
          (fr["anomalies"].get("a1_cars", 0), fr["anomalies"].get("a2_placeholder", 0),
           fr["anomalies"].get("a3_overcap_flag", 0), fr["anomalies"].get("a4_perim_flag", 0),
           fr["anomalies"].get("a5_macro_flag", 0)), (17, 14, 4, 3, 3))
    de = summ["by_country"]["DE"]
    check("DE audited/reachable/flagged",
          (de["audited"], de["reachable"], de["flagged"]), (251, 243, 32))
    check("DE (A1,A2,A3)",
          (de["anomalies"].get("a1_cars", 0), de["anomalies"].get("a2_placeholder", 0),
           de["anomalies"].get("a3_overcap_flag", 0)), (21, 4, 9))
    check("US flagged", summ["by_country"]["US"]["flagged"], 0)

    print("\n== A7 base and distribution (Table a7-distribution / S3) ==")
    ge20 = [r for r in rows if (fnum(r["stations"]) or 0) >= N_MIN]
    check("systems with >= 20 stations (A7 base)", len(ge20), 640)
    cross = [r for r in ge20 if (fnum(r["capacity_nan_pct"]) or 0) > A7_PCT]
    check("cross the 50% NaN threshold", len(cross), 365)

    def a7bucket(p):
        if p == 0: return "=0"
        if p < 1: return "(0,1)"
        if p < 10: return "[1,10)"
        if p < 50: return "[10,50)"
        if p < 99: return "[50,99)"
        if p < 100: return "[99,100)"
        return "=100"
    bk = collections.Counter(a7bucket(fnum(r["capacity_nan_pct"]) or 0) for r in ge20)
    paper_s3 = {"=0": 238, "(0,1)": 4, "[1,10)": 11, "[10,50)": 22,
                "[50,99)": 41, "[99,100)": 5, "=100": 319}
    check("A7 distribution buckets", dict(bk), paper_s3)
    extremes = bk["=0"] + bk["=100"]
    check("mass at the two extremes", round(100 * extremes / len(ge20), 1), 87.0)

    print("\n== A6 and A7-exclusive (docked base via --infer-type) ==")
    for r in rows:
        r["_t"] = station_type(r.get("name"), r.get("root_url", ""))
    docked = [r for r in ge20 if r["_t"] == "docked_bike"]
    check("docked systems with >= 20 stations (A6 base)", len(docked), 301)
    a6 = [r for r in docked if (fnum(r["a6_zero_capacity_pct"]) or 0) >= A6_PCT]
    check("A6 flagged (zero-cap rate >= 1%)", len(a6), 22)

    def a1to6(r):
        return (r["_t"] == "carsharing"
                or any(truthy(r[c]) for c in ("a2_placeholder", "a3_overcap_flag",
                                              "a4_perim_flag", "a5_macro_flag"))
                or (r["_t"] == "docked_bike"
                    and (fnum(r["a6_zero_capacity_pct"]) or 0) >= A6_PCT))
    excl = [r for r in cross if not a1to6(r)]
    excl_st = sum(int(fnum(r["stations"]) or 0) for r in excl)
    check("A7 flagged exclusively (not also A1-A6)", len(excl), 245)
    check("stations covered by exclusive-A7 systems", excl_st, 97314)
    dott = [r for r in excl if re.search(r"dott", r["name"] or "", re.I)]
    check("Dott exclusive-A7 systems", len(dott), 147)
    check("Dott share of exclusive-A7 stations (%)",
          round(100 * sum(int(fnum(r["stations"]) or 0) for r in dott) / excl_st), 76)

    print()
    if all(ok):
        print(f"ALL {len(ok)} reproducible checks PASS - snapshot matches the manuscript.")
        return 0
    print(f"{ok.count(False)}/{len(ok)} checks FAILED.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
