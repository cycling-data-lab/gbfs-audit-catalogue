"""Compute the A3 capacity-profile ratio
$\\bar c_{\\text{profile}} / \\bar c_{\\text{actual}}$ on the global
MobilityData GBFS catalogue, system by system.

Used to extend Table 4 of the manuscript from the 95 French systems
to the full set of audited systems worldwide, providing
out-of-sample evidence that the bimodality justifying
$\\tau_{A3} = 5$ is not a French artefact.

Output: experiments/e2_threshold_sensitivity/global_a3_ratio.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from pathlib import Path

TIMEOUT = 15.0
USER_AGENT = (
    "GBFS-Audit-Catalogue/1.0.1 (Fossé & Pallares 2026 CSI A3 global sweep)"
)
N_MIN = 20  # minimum stations for the ratio to be meaningful


def _fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def _resolve_station_information_url(disco_url: str) -> str:
    disco = _fetch(disco_url)
    feeds_root = disco.get("data", {})
    for _, val in feeds_root.items():
        feeds = val.get("feeds") if isinstance(val, dict) else None
        if feeds is None and isinstance(val, list):
            feeds = val
        if not feeds:
            continue
        for f in feeds:
            if f.get("name") == "station_information":
                return f["url"]
    raise LookupError("no station_information feed")


def _compute_ratio(stations: list[dict]) -> dict:
    caps_raw = [s.get("capacity") for s in stations]
    caps_positive = [c for c in caps_raw if c is not None and c > 0]
    n = len(stations)
    n_nan = sum(1 for c in caps_raw if c is None)
    n_zero = sum(1 for c in caps_raw if c == 0)
    if not caps_positive:
        return {"n": n, "n_nan": n_nan, "n_zero": n_zero, "ratio": float("nan")}
    c_profile = sum(caps_positive) / len(caps_positive)
    # c_actual = unconditional mean (NaN counted as 0)
    caps_for_actual = [c if c is not None else 0 for c in caps_raw]
    c_actual = sum(caps_for_actual) / n
    if c_actual <= 0:
        return {"n": n, "n_nan": n_nan, "n_zero": n_zero, "ratio": float("nan")}
    return {
        "n": n,
        "n_nan": n_nan,
        "n_zero": n_zero,
        "c_profile": c_profile,
        "c_actual": c_actual,
        "ratio": c_profile / c_actual,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalogue",
        type=Path,
        default=Path("/tmp/mobilitydata_systems.csv"),
        help="MobilityData GBFS catalogue CSV",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("experiments/e2_threshold_sensitivity/global_a3_ratio.csv"),
    )
    parser.add_argument("--limit", type=int, default=0, help="stop after N feeds (0 = all)")
    args = parser.parse_args()

    rows = []
    with args.catalogue.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        feeds = [
            r for r in reader
            if r.get("Auto-Discovery URL") and not r.get("Authentication Type")
        ]
    if args.limit:
        feeds = feeds[: args.limit]

    print(f"sweeping {len(feeds)} feeds (skipping authenticated ones)")
    t0 = time.monotonic()
    for i, r in enumerate(feeds):
        if i % 50 == 0 and i > 0:
            print(f"  [{i}/{len(feeds)}]  elapsed {time.monotonic() - t0:.0f}s")
        country = r.get("Country Code", "")
        name = r.get("Name", "")
        disco = r["Auto-Discovery URL"]
        record = {"country": country, "name": name, "url": disco}
        try:
            si_url = _resolve_station_information_url(disco)
            si = _fetch(si_url)
            stations = si.get("data", {}).get("stations", [])
            if len(stations) < N_MIN:
                record["status"] = f"too_small_n={len(stations)}"
            else:
                record.update(_compute_ratio(stations))
                record["status"] = "ok"
        except Exception as e:  # noqa: BLE001
            record["status"] = f"err:{type(e).__name__}"
        rows.append(record)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Normalize columns
    all_keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in all_keys:
                all_keys.append(k)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # Summary stats
    ok = [r for r in rows if r.get("status") == "ok" and r.get("ratio") == r.get("ratio")]  # NaN check
    print()
    print(f"Total feeds attempted   : {len(rows)}")
    print(f"  successfully audited   : {len(ok)}")
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.get("status", "?")] = by_status.get(r.get("status", "?"), 0) + 1
    for s, c in sorted(by_status.items(), key=lambda x: -x[1])[:8]:
        print(f"    {s}: {c}")

    if ok:
        ratios = [r["ratio"] for r in ok]
        buckets = {
            "[1.00, 1.10]": 0,
            "[1.10, 2.00]": 0,
            "[2.00, 5.00]": 0,
            "[5.00, 20.00]": 0,
            "[20.00, 50.00]": 0,
            "[50.00, inf)": 0,
        }
        for r in ratios:
            if r < 1.10:
                buckets["[1.00, 1.10]"] += 1
            elif r < 2.00:
                buckets["[1.10, 2.00]"] += 1
            elif r < 5.00:
                buckets["[2.00, 5.00]"] += 1
            elif r < 20.00:
                buckets["[5.00, 20.00]"] += 1
            elif r < 50.00:
                buckets["[20.00, 50.00]"] += 1
            else:
                buckets["[50.00, inf)"] += 1
        print()
        print("Empirical distribution of c_profile/c_actual:")
        for k, v in buckets.items():
            print(f"  {k:18s} : {v:4d}  ({100*v/len(ok):.1f}%)")


if __name__ == "__main__":
    main()
