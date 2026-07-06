"""Exploratory OSM cross-validation of the human-adjudicated judgements.

NOT pre-registered (logged as amendment A9.8 in PROTOCOL.md): an independent
corroboration of the physical-existence judgements using OpenStreetMap, which
requires no credentials and is reproducible by any reviewer.

Rationale. The campaign could not log Street View capture dates (A9.3), so the
pre-registered staleness sensitivity is not computable. OSM offers an
independent modality instead: French dock-based VLS stations are extensively
mapped as ``amenity=bicycle_rental`` and car-sharing bays as
``amenity=car_sharing``. If a station the annotators judged real has an OSM
object nearby, and a station they judged a ghost has none, two independent
observation channels (imagery + community mapping) agree.

Method. Two Overpass bulk queries (bicycle_rental, car_sharing; nodes + ways,
metropolitan-France bbox), then local nearest-neighbour matching against the
frozen 422-station sample at 50 / 100 / 150 m (three radii, so the choice of
radius is visibly not doing the work). Output: ``osm_crosscheck.csv`` with
per-station nearest distances, and a concordance summary against the
adjudicated Q0 (concordant answers only, as everywhere in the campaign).

Usage:
    python -m experiments.human_validation.osm_crosscheck            # fetch + report
    python -m experiments.human_validation.osm_crosscheck --offline  # re-report from CSV
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

_DIR = Path(__file__).resolve().parent
OUT = _DIR / "osm_crosscheck.csv"
MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
RADII = (50, 100, 150)
FETCH_RADIUS = 200  # m; superset of every reported radius
BATCH = 25
AMENITIES = ("bicycle_rental", "car_sharing")


def _overpass_batch(points: list[tuple[float, float]], amenity: str) -> list[tuple[float, float]]:
    clauses = "".join(
        f'node["amenity"="{amenity}"](around:{FETCH_RADIUS},{lat},{lon});'
        f'way["amenity"="{amenity}"](around:{FETCH_RADIUS},{lat},{lon});'
        for lat, lon in points
    )
    q = f"[out:json][timeout:90];({clauses});out center;"
    last_err: Exception | None = None
    for attempt in range(6):
        url = MIRRORS[attempt % len(MIRRORS)]
        try:
            req = urllib.request.Request(
                url,
                data=urllib.parse.urlencode({"data": q}).encode(),
                headers={"User-Agent": "gbfs-audit-catalogue/osm-crosscheck"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                d = json.loads(resp.read().decode("utf-8"))
            pts = []
            for el in d.get("elements", []):
                lat = el.get("lat") or (el.get("center") or {}).get("lat")
                lon = el.get("lon") or (el.get("center") or {}).get("lon")
                if lat is not None:
                    pts.append((float(lat), float(lon)))
            return pts
        except Exception as e:  # noqa: BLE001 - back off, then retry on the next mirror
            last_err = e
            time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"Overpass failed after retries: {last_err}")


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _nearest_m(lat, lon, pts_sorted, lats):
    """Nearest distance via a latitude-window scan (adequate for 422 x ~30k)."""
    import bisect

    # 150 m ~ 0.0014 deg latitude; scan a +/-0.05 deg window, fall back to full
    for window in (0.05, 90.0):
        lo = bisect.bisect_left(lats, lat - window)
        hi = bisect.bisect_right(lats, lat + window)
        best = min(
            (_haversine_m(lat, lon, la, lo_) for la, lo_ in pts_sorted[lo:hi]),
            default=None,
        )
        if best is not None:
            return best
    return None


def fetch() -> None:
    import pandas as pd

    sample = pd.read_csv(_DIR / "sample.csv")
    stations = [(float(r.lat), float(r.lon)) for r in sample.itertuples()]
    cache_path = _DIR / "osm_overpass_cache.jsonl"
    cache: dict[tuple[str, int], list] = {}
    if cache_path.exists():
        for line in cache_path.open(encoding="utf-8"):
            rec = json.loads(line)
            cache[(rec["amenity"], rec["batch"])] = rec["pts"]
    cols = {}
    with cache_path.open("a", encoding="utf-8") as cf:
        for am in AMENITIES:
            n_batches = -(-len(stations) // BATCH)
            print(f"Overpass: {am} ({len(stations)} stations, {n_batches} batches) ...", flush=True)
            pts: list[tuple[float, float]] = []
            for i in range(0, len(stations), BATCH):
                b = i // BATCH
                if (am, b) in cache:
                    got = [tuple(p) for p in cache[(am, b)]]
                else:
                    got = _overpass_batch(stations[i : i + BATCH], am)
                    cf.write(json.dumps({"amenity": am, "batch": b, "pts": got}) + "\n")
                    cf.flush()
                    time.sleep(8)
                pts.extend(got)
                print(f"  batch {b + 1}/{n_batches}: {len(pts)} objects so far", flush=True)
            pts = sorted(set(pts))
            lats = [p[0] for p in pts]
            print(f"  {len(pts)} unique OSM objects")
            cols[am] = [_nearest_m(lat, lon, pts, lats) for lat, lon in stations]
    out = sample[["system_id", "station_id", "stratum", "lat", "lon"]].copy()
    for am in AMENITIES:
        out[f"d_{am}_m"] = [None if v is None else round(v, 1) for v in cols[am]]
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT.name} ({len(out)} stations)")


def report() -> None:
    import pandas as pd

    sys.path.insert(0, str(_DIR.parent.parent))
    from experiments.human_validation.compute_reliability import (
        merge_annotations,
        adjudicate,
        wilson_ci,
    )

    l1 = pd.read_csv(_DIR / "labels_rohan.csv")
    l2 = pd.read_csv(_DIR / "labels_gael.csv")
    gold = adjudicate(merge_annotations(l1, l2))
    osm = pd.read_csv(OUT)
    g = gold.merge(osm, on=["system_id", "station_id", "stratum"], how="left")

    print("\n=== OSM presence rate by adjudicated Q0 (concordant labels only) ===")
    for radius in RADII:
        print(f"\n-- radius {radius} m --")
        for q0, col in [
            ("vls_borne", "d_bicycle_rental_m"),
            ("vls_sans_borne", "d_bicycle_rental_m"),
            ("rien", "d_bicycle_rental_m"),
            ("autopartage", "d_car_sharing_m"),
        ]:
            sub = g[g["gold_Q0_type"] == q0]
            if not len(sub):
                continue
            hit = (sub[col] <= radius).sum()
            p, lo, hi = wilson_ci(int(hit), len(sub))
            print(
                f"  {q0:<15} {hit:>3}/{len(sub):<3} = {p:5.1%}  Wilson [{lo:.1%}, {hi:.1%}]"
            )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="re-report from the existing CSV")
    args = ap.parse_args()
    if not args.offline:
        fetch()
    report()


if __name__ == "__main__":
    main()
