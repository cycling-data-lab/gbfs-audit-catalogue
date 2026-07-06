"""Retro-fetch Street View capture dates for the frozen 422-station sample.

The campaign ran without a Maps key (sv_status = NO_KEY on every row), so the
pre-registered staleness sensitivity could not be computed. The Street View
*Metadata* endpoint is free of charge and only needs a key, so the capture
dates can be recovered a posteriori: the imagery a given (lat, lon) resolves
to is stable, and the metadata call returns the same pano/date the annotators
saw in the embedded viewer.

Usage:
    export GOOGLE_MAPS_API_KEY=...   # metadata calls are free
    python -m experiments.human_validation.fetch_sv_dates          # fetch (resumable)
    python -m experiments.human_validation.fetch_sv_dates --apply  # write dated label copies

--apply writes labels_<annotator>_dated.csv (byte-identical to the released
labels except the sv_date/sv_pano_id/sv_status columns are filled), then
prints the command to re-run the FROZEN analysis script on them, which
re-activates its sv_date_sensitivity block. The released labels and the
frozen script are never modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

_DIR = Path(__file__).resolve().parent
SAMPLE = _DIR / "sample.csv"
OUT = _DIR / "sv_dates.csv"
ENDPOINT = "https://maps.googleapis.com/maps/api/streetview/metadata"
KEY_FIELDS = ["system_id", "station_id", "stratum"]


def fetch_one(lat: float, lon: float, key: str) -> dict:
    qs = urllib.parse.urlencode(
        {"location": f"{lat},{lon}", "source": "outdoor", "key": key}
    )
    with urllib.request.urlopen(f"{ENDPOINT}?{qs}", timeout=15) as resp:
        d = json.loads(resp.read().decode("utf-8"))
    return {
        "sv_status": d.get("status", "UNKNOWN"),
        "sv_date": d.get("date", "") or "",
        "sv_pano_id": d.get("pano_id", "") or "",
    }


def fetch(key: str) -> None:
    import pandas as pd

    sample = pd.read_csv(SAMPLE)
    done: dict[tuple, dict] = {}
    if OUT.exists():
        for r in csv.DictReader(OUT.open(encoding="utf-8")):
            done[tuple(str(r[k]) for k in KEY_FIELDS)] = r
    rows = []
    n_new = 0
    for _, r in sample.iterrows():
        k = tuple(str(r[f]) for f in KEY_FIELDS)
        if k in done and done[k]["sv_status"] not in ("", "ERROR"):
            rows.append(done[k])
            continue
        try:
            meta = fetch_one(float(r["lat"]), float(r["lon"]), key)
        except Exception as e:  # noqa: BLE001 - keep the sweep resumable
            meta = {"sv_status": "ERROR", "sv_date": "", "sv_pano_id": ""}
            print(f"  ! {k}: {e}", file=sys.stderr)
        rows.append({**dict(zip(KEY_FIELDS, k)), **meta})
        n_new += 1
        if n_new % 50 == 0:
            print(f"  fetched {n_new} new / {len(rows)} total")
        time.sleep(0.05)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KEY_FIELDS + ["sv_status", "sv_date", "sv_pano_id"])
        w.writeheader()
        w.writerows(rows)
    ok = sum(1 for r in rows if r["sv_status"] == "OK")
    print(f"{OUT.name}: {len(rows)} rows, {ok} with imagery metadata, {n_new} fetched this run")


def apply_dates() -> None:
    import pandas as pd

    dates = pd.read_csv(OUT, dtype=str)
    outs = []
    for name in ("rohan", "gael"):
        labels = pd.read_csv(_DIR / f"labels_{name}.csv", dtype=str)
        merged = labels.drop(columns=["sv_date", "sv_pano_id", "sv_status"], errors="ignore").merge(
            dates, on=KEY_FIELDS, how="left"
        )
        out = _DIR / f"labels_{name}_dated.csv"
        merged.to_csv(out, index=False)
        outs.append(out)
        n = merged["sv_date"].notna().sum()
        print(f"{out.name}: sv_date filled on {n}/{len(merged)} rows")
    print(
        "\nRe-run the frozen analysis (unchanged) on the dated copies:\n"
        f"  python -m experiments.human_validation.compute_reliability \\\n"
        f"      --labels1 {outs[0]} \\\n"
        f"      --labels2 {outs[1]} \\\n"
        f"      --output  {_DIR / 'reliability_report_dated.json'}\n"
        "The sv_date_sensitivity block of the report is then populated."
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write dated label copies and print the rerun command")
    args = ap.parse_args()
    if args.apply:
        apply_dates()
        return
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        sys.exit("GOOGLE_MAPS_API_KEY is not set (metadata calls are free of charge).")
    fetch(key)


if __name__ == "__main__":
    main()
